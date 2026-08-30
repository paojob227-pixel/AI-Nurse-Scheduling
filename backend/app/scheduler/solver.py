"""Read-only CP-SAT feasibility and draft-preview boundary for the ICU scheduler."""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from ortools.sat.python import cp_model

from app.scheduler.assignment_model import AssignmentModel, AssignmentModelBuilder
from app.scheduler.contracts import (
    PreflightIssue, PreviewAssignment, PreviewStaffWorkload, SchedulerPreviewResult,
    SchedulerPreviewSummary, SchedulerSnapshot, SolverDryRunResult,
)


SOLVER_TIME_LIMIT_SECONDS = 10.0
SolverStatus = Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID"]


@dataclass(frozen=True)
class _SolvedModel:
    assignment_model: AssignmentModel
    solver_status: SolverStatus
    objective_value: float | None
    solve_time_seconds: float
    variable_count: int
    constraint_count: int
    diagnostics: tuple[PreflightIssue, ...]
    solver: cp_model.CpSolver | None
    notice: str


class CpSatSchedulerSolver:
    """Solves in memory and never creates, changes, or publishes schedules."""

    def dry_run(self, snapshot: SchedulerSnapshot) -> SolverDryRunResult:
        solved = self._solve(snapshot)
        model = solved.assignment_model
        return SolverDryRunResult(
            solver_status=solved.solver_status, objective_value=solved.objective_value,
            solve_time_seconds=solved.solve_time_seconds, variable_count=solved.variable_count,
            constraint_count=solved.constraint_count, diagnostics=solved.diagnostics,
            candidate_assignments=(), assignment_variable_count=len(model.assignments),
            incharge_variable_count=len(model.incharge_assignments),
            locked_assignment_constraint_count=model.locked_assignment_constraint_count,
            locked_assignment_issues=model.locked_assignment_issues,
            approved_leave_constraint_count=model.approved_leave_constraint_count,
            approved_leave_issues=model.approved_leave_issues,
            availability_constraint_count=model.availability_constraint_count,
            availability_issues=model.availability_issues,
            staffing_constraint_count=model.staffing_constraint_count,
            coverage_constraint_count=model.coverage_constraint_count, coverage_issues=model.coverage_issues,
            senior_rn_constraint_count=model.senior_rn_constraint_count,
            incharge_qualification_constraint_count=model.incharge_qualification_constraint_count,
            incharge_coverage_constraint_count=model.incharge_coverage_constraint_count,
            senior_incharge_issues=model.senior_incharge_issues,
            rest_constraint_count=model.rest_constraint_count, overlap_constraint_count=model.overlap_constraint_count,
            multiple_shift_constraint_count=model.multiple_shift_constraint_count,
            one_shift_per_day_constraint_count=model.one_shift_per_day_constraint_count,
            rest_overlap_issues=model.rest_overlap_issues,
            assigned_shift_count_variable_count=len(model.fairness.assigned_shift_counts),
            working_minutes_variable_count=len(model.fairness.working_minutes),
            workload_score_variable_count=len(model.fairness.workload_scores),
            fairness_imbalance_variable_count=len(model.fairness.pairwise_imbalances),
            fairness_constraint_count=model.fairness.fairness_constraint_count, fairness_issues=model.fairness.issues,
            preference_variable_count=len(model.preferences.penalty_variables),
            preference_score_term_count=model.preferences.score_term_count,
            preference_constraint_count=model.preferences.constraint_count, preference_issues=model.preferences.issues,
            ot_variable_count=len(model.overtime.ot_minutes), ot_penalty_terms=model.overtime.penalty_term_count,
            ot_constraint_count=model.overtime.constraint_count, ot_diagnostics=model.overtime.diagnostics,
            objective_components=tuple((item.key, item.weight, item.score_term_count) for item in model.objective.components),
            objective_weights={item.key: item.weight for item in model.objective.components},
            total_objective_terms=model.objective.total_objective_terms,
            notices=(
                "CP-SAT assignment and incharge variables were created with valid locked assignments fixed to x=1.",
                solved.notice,
                f"Preflight and solver diagnostics contain {sum(item.severity == 'error' for item in solved.diagnostics)} error(s).",
            ),
        )

    def preview(self, snapshot: SchedulerSnapshot) -> SchedulerPreviewResult:
        """Extract a solved assignment preview only when CP-SAT found a solution."""
        solved = self._solve(snapshot)
        if solved.solver is None or solved.solver_status not in {"OPTIMAL", "FEASIBLE"}:
            return SchedulerPreviewResult(
                solved.solver_status, solved.objective_value, solved.solve_time_seconds,
                solved.variable_count, solved.constraint_count, solved.diagnostics, (), None,
                (solved.notice, "No preview is available because CP-SAT did not produce a feasible solution."),
            )
        assignments = _extract_assignments(solved.assignment_model, snapshot, solved.solver)
        summary = _extract_summary(solved.assignment_model, snapshot, solved.solver, assignments, solved.objective_value or 0.0)
        return SchedulerPreviewResult(
            solved.solver_status, solved.objective_value, solved.solve_time_seconds,
            solved.variable_count, solved.constraint_count, solved.diagnostics, assignments, summary,
            (solved.notice, "Preview is read-only; no schedule, schedule detail, or publish state was changed."),
        )

    def _solve(self, snapshot: SchedulerSnapshot) -> _SolvedModel:
        assignment_model = AssignmentModelBuilder().build(snapshot)
        diagnostics = _base_diagnostics(snapshot, assignment_model)
        model = assignment_model.model
        variable_count, constraint_count = len(model.Proto().variables), len(model.Proto().constraints)
        if any(item.severity == "error" for item in diagnostics):
            return _SolvedModel(assignment_model, "MODEL_INVALID", None, 0.0, variable_count, constraint_count, tuple(diagnostics), None, "Solver was not run because blocking snapshot/model diagnostics must be fixed first.")

        model.Minimize(assignment_model.objective.total_objective_cost)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = SOLVER_TIME_LIMIT_SECONDS
        status = _status_name(solver.Solve(model))
        objective_value = solver.ObjectiveValue() if status in {"OPTIMAL", "FEASIBLE"} else None
        if status == "INFEASIBLE":
            diagnostics.extend(_coverage_capacity_diagnostics(snapshot))
            diagnostics.append(PreflightIssue("error", "SOLVER_INFEASIBLE", "No schedule satisfies all configured hard constraints. Review capacity diagnostics, locked assignments, approved leave, and timing rules."))
        elif status == "UNKNOWN":
            diagnostics.append(PreflightIssue("warning", "SOLVER_STATUS_UNKNOWN", f"CP-SAT did not return a feasible result within {SOLVER_TIME_LIMIT_SECONDS:g} seconds."))
        elif status == "MODEL_INVALID":
            diagnostics.append(PreflightIssue("error", "CP_SAT_MODEL_INVALID", "CP-SAT rejected the generated model."))
        return _SolvedModel(assignment_model, status, objective_value, solver.WallTime(), variable_count, constraint_count, tuple(diagnostics), solver if status in {"OPTIMAL", "FEASIBLE"} else None, "Read-only solve completed; no schedule preview, database write, or publish action was performed.")


def _extract_assignments(model: AssignmentModel, snapshot: SchedulerSnapshot, solver: cp_model.CpSolver) -> tuple[PreviewAssignment, ...]:
    staff = {item.id: item for item in snapshot.staff}
    shifts = {item.id: item for item in snapshot.shifts}
    preview = [
        PreviewAssignment(staff_id=staff_id, employee_code=staff[staff_id].employee_code, staff_name=staff[staff_id].display_name, work_date=work_date, shift_type_id=shift_id, shift_code=shifts[shift_id].code, is_incharge=bool(solver.Value(model.incharge_assignments[key])))
        for key, variable in model.assignments.items()
        for staff_id, work_date, shift_id in (key,)
        if solver.Value(variable) == 1
    ]
    return tuple(sorted(preview, key=lambda item: (item.work_date, item.shift_code, item.staff_id)))


def _extract_summary(model: AssignmentModel, snapshot: SchedulerSnapshot, solver: cp_model.CpSolver, assignments: tuple[PreviewAssignment, ...], objective_score: float) -> SchedulerPreviewSummary:
    staff = {item.id: item for item in snapshot.staff}
    workloads = tuple(
        PreviewStaffWorkload(
            staff_id=staff_id, employee_code=staff[staff_id].employee_code, staff_name=staff[staff_id].display_name,
            assigned_shift_count=solver.Value(model.fairness.assigned_shift_counts[staff_id]),
            working_minutes=solver.Value(model.fairness.working_minutes[staff_id]),
            workload_score=solver.Value(model.fairness.workload_scores[staff_id]),
            ot_minutes=0 if staff_id not in model.overtime.ot_minutes else solver.Value(model.overtime.ot_minutes[staff_id]),
        )
        for staff_id in sorted(staff)
    )
    quality_score, fairness_score, preference_score, ot_score = _calculate_quality_scores(
        snapshot, workloads, assignments,
    )
    return SchedulerPreviewSummary(
        total_staff=len(staff), total_assignments=len(assignments),
        total_working_minutes=sum(item.working_minutes for item in workloads),
        total_ot_minutes=sum(item.ot_minutes for item in workloads), objective_score=objective_score,
        staff_workloads=workloads,
        quality_score=quality_score, fairness_score=fairness_score,
        preference_score=preference_score, ot_score=ot_score,
    )


def _calculate_quality_scores(
    snapshot: SchedulerSnapshot,
    workloads: tuple[PreviewStaffWorkload, ...],
    assignments: tuple[PreviewAssignment, ...],
) -> tuple[float, float, float, float]:
    """Return a user-facing 0–10 rating without replacing CP-SAT's technical cost.

    The three normalized parts preserve the objective priority ratio 20:10:10:
    fairness 50%, preference 25%, and OT 25%. Safety remains a separate validator
    result and is deliberately not hidden inside this score.
    """
    workload_values = [item.workload_score for item in workloads]
    maximum_workload = max(workload_values, default=0)
    minimum_workload = min(workload_values, default=0)
    fairness_score = 10.0 if maximum_workload == 0 else 10.0 * (1.0 - ((maximum_workload - minimum_workload) / maximum_workload))

    assignment_keys = {(item.staff_id, item.work_date, item.shift_type_id) for item in assignments}
    preference_weight = sum(item.weight for item in snapshot.preferences)
    satisfied_weight = sum(
        item.weight
        for item in snapshot.preferences
        if (item.preference == "prefer" and (item.staff_id, item.work_date, item.shift_type_id) in assignment_keys)
        or (item.preference == "avoid" and (item.staff_id, item.work_date, item.shift_type_id) not in assignment_keys)
    )
    preference_score = 10.0 if preference_weight == 0 else 10.0 * satisfied_weight / preference_weight

    # An average of one 8-hour OT shift per person maps to zero for this component.
    average_ot_minutes = sum(item.ot_minutes for item in workloads) / max(len(workloads), 1)
    ot_score = 10.0 * max(0.0, 1.0 - (average_ot_minutes / 480.0))

    quality_score = (0.50 * fairness_score) + (0.25 * preference_score) + (0.25 * ot_score)
    return tuple(round(max(0.0, min(10.0, value)), 1) for value in (quality_score, fairness_score, preference_score, ot_score))


def _base_diagnostics(snapshot: SchedulerSnapshot, model: AssignmentModel) -> list[PreflightIssue]:
    return list(snapshot.preflight_issues + model.locked_assignment_issues + model.approved_leave_issues + model.availability_issues + model.coverage_issues + model.senior_incharge_issues + model.rest_overlap_issues + model.fairness.issues + model.preferences.issues + model.overtime.diagnostics)


def _status_name(status_code: int) -> SolverStatus:
    return {cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE", cp_model.INFEASIBLE: "INFEASIBLE", cp_model.UNKNOWN: "UNKNOWN", cp_model.MODEL_INVALID: "MODEL_INVALID"}.get(status_code, "UNKNOWN")


def _coverage_capacity_diagnostics(snapshot: SchedulerSnapshot) -> list[PreflightIssue]:
    min_rn = snapshot.rules.get("MIN_RN")
    if min_rn is None:
        return []
    rn_staff_ids = {staff.id for staff in snapshot.staff if staff.position.strip().upper().replace("_", " ") in {"RN", "HEAD NURSE"}}
    approved_leave_days = {(leave.staff_id, work_date) for leave in snapshot.leave_requests if leave.status == "approved" for work_date in _dates_in_month(leave.start_date, leave.end_date, snapshot.year, snapshot.month)}
    return [
        PreflightIssue("error", "RN_COVERAGE_CAPACITY_SHORTAGE", f"{work_date}: only {available_rn} RN/Head Nurse staff are available after approved leave, but MIN_RN requires {min_rn}.")
        for work_date in _month_dates(snapshot.year, snapshot.month)
        if (available_rn := len(rn_staff_ids - {staff_id for staff_id, leave_date in approved_leave_days if leave_date == work_date})) < min_rn
    ]


def _month_dates(year: int, month: int) -> tuple[date, ...]:
    return tuple(date(year, month, day) for day in range(1, monthrange(year, month)[1] + 1))


def _dates_in_month(start_date: date, end_date: date, year: int, month: int) -> tuple[date, ...]:
    dates = _month_dates(year, month)
    current, end = max(start_date, dates[0]), min(end_date, dates[-1])
    result: list[date] = []
    while current <= end:
        result.append(current)
        current += timedelta(days=1)
    return tuple(result)
