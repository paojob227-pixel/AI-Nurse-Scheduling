"""Soft-preference evaluation for an already generated preview."""

from dataclasses import dataclass

from app.scheduler.contracts import SchedulerSnapshot


@dataclass(frozen=True)
class PreferenceReport:
    total_preferences: int
    prefer_total: int
    prefer_satisfied: int
    prefer_satisfaction_percent: float
    avoid_total: int
    avoid_violations: int
    overall_satisfied: int
    overall_satisfaction_percent: float


def build_preference_report(snapshot: SchedulerSnapshot, assignment_keys: set[tuple[int, object, int]]) -> PreferenceReport:
    preferences = snapshot.preferences
    prefer = [item for item in preferences if item.preference == "prefer"]
    avoid = [item for item in preferences if item.preference == "avoid"]
    prefer_satisfied = sum((item.staff_id, item.work_date, item.shift_type_id) in assignment_keys for item in prefer)
    avoid_violations = sum((item.staff_id, item.work_date, item.shift_type_id) in assignment_keys for item in avoid)
    overall_satisfied = prefer_satisfied + (len(avoid) - avoid_violations)
    return PreferenceReport(
        len(preferences), len(prefer), prefer_satisfied,
        (prefer_satisfied / len(prefer) * 100) if prefer else 100.0,
        len(avoid), avoid_violations, overall_satisfied,
        (overall_satisfied / len(preferences) * 100) if preferences else 100.0,
    )
