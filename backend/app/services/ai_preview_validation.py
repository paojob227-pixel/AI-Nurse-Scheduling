"""Read-only validation adapter for an in-memory AI schedule preview."""

from dataclasses import dataclass
from datetime import date

from app.scheduler.contracts import SchedulerSnapshot
from app.services.schedule_validator import Assignment, Conflict, LeavePeriod, SoftPreference, Window, validate_context


@dataclass(frozen=True)
class PreviewAssignmentInput:
    staff_id: int
    shift_type_id: int
    work_date: date
    is_incharge: bool


def validate_preview(snapshot: SchedulerSnapshot, preview: tuple[PreviewAssignmentInput, ...]) -> list[Conflict]:
    """Use the Manual Schedule ICU validator against ephemeral AI assignments only."""
    staff_by_id = {staff.id: staff for staff in snapshot.staff}
    shift_by_id = {shift.id: shift for shift in snapshot.shifts}
    conflicts: list[Conflict] = []
    assignments: list[Assignment] = []
    for index, item in enumerate(preview, start=1):
        staff = staff_by_id.get(item.staff_id)
        shift = shift_by_id.get(item.shift_type_id)
        if staff is None or shift is None or item.work_date.year != snapshot.year or item.work_date.month != snapshot.month:
            conflicts.append(Conflict(
                "error", "PREVIEW_ASSIGNMENT_OUTSIDE_SNAPSHOT", item.work_date, "Preview", (item.staff_id,), (),
                f"Preview assignment staff={item.staff_id}, shift={item.shift_type_id}, date={item.work_date} is not available in the selected scheduler snapshot",
            ))
            continue
        assignments.append(Assignment(
            index, staff.id, staff.display_name, staff.position, staff.is_senior_rn, item.work_date,
            shift.id, shift.code, shift.start_time, shift.end_time, shift.crosses_midnight,
            item.is_incharge, False, None, None, staff.is_head_nurse,
        ))

    windows = [Window(
        window.code, frozenset(window.shift_type_ids), window.min_rn, window.max_rn,
        window.min_support_staff, window.min_senior_rn,
    ) for window in snapshot.coverage_windows]
    leaves = [LeavePeriod(item.staff_id, item.start_date, item.end_date) for item in snapshot.leave_requests if item.status == "approved"]
    preferences = [SoftPreference(item.staff_id, item.work_date, item.shift_type_id, item.preference, item.weight) for item in snapshot.preferences]
    preferences.extend(SoftPreference(item.staff_id, item.work_date, None, "avoid", 1) for item in snapshot.availability if item.status in {"unavailable", "preferred_off"})
    conflicts.extend(validate_context(assignments, windows, snapshot.rules, leaves, preferences, snapshot.year, snapshot.month))
    return conflicts
