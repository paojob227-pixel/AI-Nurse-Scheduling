"""Phase 2.3.1 workload metrics and a prepared (but not attached) fairness objective."""

from dataclasses import dataclass
from datetime import date
from itertools import combinations

from ortools.sat.python import cp_model

from app.scheduler.contracts import PreflightIssue, SchedulerSnapshot


AssignmentKey = tuple[int, date, int]
WORKLOAD_SCORE_SCALE = 10
SHIFT_BASE_WEIGHTS: dict[str, int] = {"AM": 10, "PM": 10, "N": 10, "D": 15, "DE": 15}


@dataclass(frozen=True)
class FairnessObjectiveModel:
    assigned_shift_counts: dict[int, cp_model.IntVar]
    working_minutes: dict[int, cp_model.IntVar]
    workload_scores: dict[int, cp_model.IntVar]
    pairwise_imbalances: dict[tuple[int, int], cp_model.IntVar]
    total_workload_imbalance: cp_model.IntVar
    fairness_constraint_count: int
    issues: tuple[PreflightIssue, ...]


def build_fairness_objective_model(
    model: cp_model.CpModel,
    assignments: dict[AssignmentKey, cp_model.IntVar],
    snapshot: SchedulerSnapshot,
) -> FairnessObjectiveModel:
    issues, weighted_shifts = _validate_workload_shifts(snapshot)
    staff_ids = [staff.id for staff in snapshot.staff]
    by_staff: dict[int, list[tuple[int, cp_model.IntVar]]] = {staff_id: [] for staff_id in staff_ids}
    for (staff_id, _work_date, shift_id), variable in assignments.items():
        by_staff.setdefault(staff_id, []).append((shift_id, variable))

    assigned_counts: dict[int, cp_model.IntVar] = {}
    minutes: dict[int, cp_model.IntVar] = {}
    scores: dict[int, cp_model.IntVar] = {}
    score_uppers: dict[int, int] = {}
    constraints = 0
    for staff_id in staff_ids:
        variables = by_staff[staff_id]
        count = model.NewIntVar(0, len(variables), f"assigned_shift_count_s{staff_id}")
        model.Add(count == sum(variable for _shift_id, variable in variables))
        assigned_counts[staff_id] = count
        constraints += 1

        minute_upper = sum(weighted_shifts.get(shift_id, (0, 0))[0] for shift_id, _variable in variables)
        minute_value = model.NewIntVar(0, minute_upper, f"working_minutes_s{staff_id}")
        model.Add(minute_value == sum(weighted_shifts.get(shift_id, (0, 0))[0] * variable for shift_id, variable in variables))
        minutes[staff_id] = minute_value
        constraints += 1

        score_upper = sum(weighted_shifts.get(shift_id, (0, 0))[1] for shift_id, _variable in variables)
        score = model.NewIntVar(0, score_upper, f"workload_score_s{staff_id}")
        model.Add(score == sum(weighted_shifts.get(shift_id, (0, 0))[1] * variable for shift_id, variable in variables))
        scores[staff_id] = score
        score_uppers[staff_id] = score_upper
        constraints += 1

    pairwise: dict[tuple[int, int], cp_model.IntVar] = {}
    pairwise_uppers: dict[tuple[int, int], int] = {}
    for first, second in combinations(staff_ids, 2):
        upper = score_uppers[first] + score_uppers[second]
        imbalance = model.NewIntVar(0, upper, f"workload_imbalance_s{first}_s{second}")
        model.AddAbsEquality(imbalance, scores[first] - scores[second])
        pairwise[(first, second)] = imbalance
        pairwise_uppers[(first, second)] = upper
        constraints += 1
    total_upper = sum(pairwise_uppers.values())
    total = model.NewIntVar(0, total_upper, "total_workload_imbalance")
    model.Add(total == sum(pairwise.values()))
    constraints += 1
    return FairnessObjectiveModel(assigned_counts, minutes, scores, pairwise, total, constraints, tuple(issues))


def _validate_workload_shifts(snapshot: SchedulerSnapshot) -> tuple[list[PreflightIssue], dict[int, tuple[int, int]]]:
    issues: list[PreflightIssue] = []
    weighted: dict[int, tuple[int, int]] = {}
    for shift in snapshot.shifts:
        weight = SHIFT_BASE_WEIGHTS.get(shift.code.upper())
        if weight is None:
            issues.append(PreflightIssue("error", "UNKNOWN_WORKLOAD_SHIFT_WEIGHT", f"Shift {shift.code} has no ICU workload base weight"))
            continue
        if shift.duration_minutes is None or shift.duration_minutes <= 0:
            issues.append(PreflightIssue("error", "INVALID_WORKLOAD_SHIFT_DURATION", f"Shift {shift.code} needs a positive duration for workload hours"))
            continue
        weighted[shift.id] = (shift.duration_minutes, weight)
    return issues, weighted
