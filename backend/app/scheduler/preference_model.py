"""Phase 2.3.2A soft preference penalties; these never constrain assignments directly."""

from dataclasses import dataclass
from datetime import date

from ortools.sat.python import cp_model

from app.scheduler.contracts import LockedAssignment, PreflightIssue, SchedulerPreference, SchedulerSnapshot


AssignmentKey = tuple[int, date, int]


@dataclass(frozen=True)
class PreferenceObjectiveModel:
    penalty_variables: dict[tuple[int, date, int, str], cp_model.IntVar]
    preference_penalty_score: cp_model.IntVar
    score_term_count: int
    hard_constraint_count: int
    constraint_count: int
    issues: tuple[PreflightIssue, ...]


def build_preference_objective_model(
    model: cp_model.CpModel,
    assignments: dict[AssignmentKey, cp_model.IntVar],
    snapshot: SchedulerSnapshot,
    locked_assignments: tuple[LockedAssignment, ...] = (),
) -> PreferenceObjectiveModel:
    issues, valid_preferences, hard_keys = _validate_preferences(snapshot, assignments, locked_assignments)
    for key in hard_keys:
        model.Add(assignments[key] == 0)
    penalties: dict[tuple[int, date, int, str], cp_model.IntVar] = {}
    for preference in valid_preferences:
        key = (preference.staff_id, preference.work_date, preference.shift_type_id)
        preference_key = (*key, preference.preference)
        penalty = model.NewBoolVar(
            f"preference_{preference.preference}_penalty_s{preference.staff_id}_d{preference.work_date.isoformat()}_t{preference.shift_type_id}",
        )
        assignment = assignments[key]
        # These equations define a penalty variable only. They do not force assignment x either way.
        if preference.preference == "prefer":
            model.Add(penalty + assignment == 1)
        else:
            model.Add(penalty == assignment)
        penalties[preference_key] = penalty

    score_upper = sum(preference.weight for preference in valid_preferences)
    score = model.NewIntVar(0, score_upper, "preference_penalty_score")
    model.Add(score == sum(preference.weight * penalties[(preference.staff_id, preference.work_date, preference.shift_type_id, preference.preference)] for preference in valid_preferences))
    return PreferenceObjectiveModel(penalties, score, len(valid_preferences), len(hard_keys), len(valid_preferences) + len(hard_keys) + 1, tuple(issues))


def _validate_preferences(
    snapshot: SchedulerSnapshot,
    assignments: dict[AssignmentKey, cp_model.IntVar],
    locked_assignments: tuple[LockedAssignment, ...],
) -> tuple[list[PreflightIssue], tuple[SchedulerPreference, ...], tuple[AssignmentKey, ...]]:
    issues: list[PreflightIssue] = []
    valid: list[SchedulerPreference] = []
    hard_keys: set[AssignmentKey] = set()
    conflicting_keys: set[tuple[int, date, int]] = set()
    by_assignment: dict[tuple[int, date, int], set[str]] = {}
    for preference in snapshot.preferences:
        if preference.preference == "avoid" and preference.weight == 5:
            continue
        if preference.shift_type_id is None:
            continue
        key = (preference.staff_id, preference.work_date, preference.shift_type_id)
        by_assignment.setdefault(key, set()).add(preference.preference)
    for key, values in by_assignment.items():
        if {"prefer", "avoid"}.issubset(values):
            conflicting_keys.add(key)
            issues.append(PreflightIssue("error", "CONFLICTING_SHIFT_PREFERENCES", f"Staff {key[0]} both prefers and avoids shift {key[2]} on {key[1]}"))

    for preference in snapshot.preferences:
        if preference.preference not in {"prefer", "avoid"}:
            issues.append(PreflightIssue("error", "INVALID_PREFERENCE_TYPE", f"Unsupported preference {preference.preference}"))
            continue
        if not 1 <= preference.weight <= 5:
            issues.append(PreflightIssue("error", "INVALID_PREFERENCE_WEIGHT", f"Preference weight for staff {preference.staff_id} must be between 1 and 5"))
            continue
        if preference.preference == "avoid" and preference.weight == 5:
            all_day_keys = tuple(key for key in assignments if key[0] == preference.staff_id and key[1] == preference.work_date)
            if not all_day_keys:
                issues.append(PreflightIssue("error", "PREFERENCE_OUTSIDE_SNAPSHOT", f"Unavailable preference staff={preference.staff_id}, date={preference.work_date} is not available in this snapshot"))
                continue
            hard_keys.update(all_day_keys)
            continue
        if preference.shift_type_id is None:
            issues.append(PreflightIssue("error", "INVALID_ALL_DAY_PREFERENCE", "Only an avoid preference with weight 5 can apply to every shift"))
            continue
        key = (preference.staff_id, preference.work_date, preference.shift_type_id)
        if key not in assignments:
            issues.append(PreflightIssue("error", "PREFERENCE_OUTSIDE_SNAPSHOT", f"Preference staff={preference.staff_id}, date={preference.work_date}, shift={preference.shift_type_id} is not available in this snapshot"))
            continue
        if key in conflicting_keys:
            continue
        valid.append(preference)
    locked_keys = {(item.staff_id, item.work_date, item.shift_type_id) for item in locked_assignments}
    for key in sorted(hard_keys):
        if key in locked_keys:
            issues.append(PreflightIssue("error", "LOCKED_ASSIGNMENT_ON_UNAVAILABLE_PREFERENCE", f"Locked assignment staff={key[0]}, date={key[1]}, shift={key[2]} conflicts with a priority-5 unavailable preference"))
    return issues, tuple(valid), tuple(sorted(hard_keys))
