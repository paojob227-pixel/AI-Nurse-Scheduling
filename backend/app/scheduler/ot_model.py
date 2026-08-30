"""Phase 2.3.2B overtime soft-penalty variables; no objective is attached or solved."""

from dataclasses import dataclass

from ortools.sat.python import cp_model

from app.scheduler.contracts import PreflightIssue, SchedulerSnapshot
from app.scheduler.fairness_model import FairnessObjectiveModel


@dataclass(frozen=True)
class OtObjectiveModel:
    ot_minutes: dict[int, cp_model.IntVar]
    ot_penalty_score: cp_model.IntVar | None
    penalty_term_count: int
    constraint_count: int
    diagnostics: tuple[PreflightIssue, ...]


def build_ot_objective_model(
    model: cp_model.CpModel,
    fairness: FairnessObjectiveModel,
    snapshot: SchedulerSnapshot,
) -> OtObjectiveModel:
    diagnostics, threshold_minutes = _validate_ot_rules(snapshot)
    if threshold_minutes is None:
        return OtObjectiveModel({}, None, 0, 0, tuple(diagnostics))

    ot_minutes: dict[int, cp_model.IntVar] = {}
    constraints = 0
    for staff_id, working_minutes in fairness.working_minutes.items():
        upper = _maximum_working_minutes(snapshot)
        overtime = model.NewIntVar(0, upper, f"ot_minutes_s{staff_id}")
        # Soft score metric: max(0, working_minutes - OT threshold). It never restricts x.
        model.AddMaxEquality(overtime, [working_minutes - threshold_minutes, 0])
        ot_minutes[staff_id] = overtime
        constraints += 1
    total_upper = _maximum_working_minutes(snapshot) * len(ot_minutes)
    penalty = model.NewIntVar(0, total_upper, "ot_penalty_score")
    model.Add(penalty == sum(ot_minutes.values()))
    constraints += 1
    return OtObjectiveModel(ot_minutes, penalty, len(ot_minutes), constraints, tuple(diagnostics))


def _validate_ot_rules(snapshot: SchedulerSnapshot) -> tuple[list[PreflightIssue], int | None]:
    diagnostics: list[PreflightIssue] = []
    monthly_hours = snapshot.rules.get("MONTHLY_HOURS")
    ot_threshold = snapshot.rules.get("OT_THRESHOLD")
    if monthly_hours is None:
        diagnostics.append(PreflightIssue("error", "MISSING_ICU_RULE", "MONTHLY_HOURS is required for OT diagnostics"))
    if ot_threshold is None:
        diagnostics.append(PreflightIssue("error", "MISSING_ICU_RULE", "OT_THRESHOLD is required for OT calculation"))
    if monthly_hours is None or ot_threshold is None:
        return diagnostics, None
    if monthly_hours <= 0 or ot_threshold <= 0 or ot_threshold < monthly_hours:
        diagnostics.append(PreflightIssue("error", "INVALID_OT_RULES", "OT_THRESHOLD must be greater than or equal to positive MONTHLY_HOURS"))
        return diagnostics, None
    return diagnostics, ot_threshold * 60


def _maximum_working_minutes(snapshot: SchedulerSnapshot) -> int:
    # Every current model day can select each configured shift. This is a safe upper bound,
    # not an assignment decision or a hard work-hours restriction.
    from calendar import monthrange
    return monthrange(snapshot.year, snapshot.month)[1] * sum(max(shift.duration_minutes or 0, 0) for shift in snapshot.shifts)
