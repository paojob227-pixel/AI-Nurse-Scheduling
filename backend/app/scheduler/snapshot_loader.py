"""Read-only loader for a reproducible department-month scheduler input snapshot."""

from calendar import monthrange
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Availability, CoverageWindow, CoverageWindowShiftType, Department,
    DepartmentRuleSetting, LeaveRequest, Schedule, ScheduleDetail, ShiftType,
    Staff, StaffShiftPreference, User,
)
from app.services.icu_rules import RULE_LIMITS
from app.scheduler.contracts import (
    LockedAssignment, PreflightIssue, SchedulerAvailability, SchedulerCoverageWindow,
    SchedulerLeave, SchedulerPreference, SchedulerShift, SchedulerSnapshot, SchedulerStaff,
)


def load_snapshot(db: Session, department_id: int, year: int, month: int) -> SchedulerSnapshot:
    if db.get(Department, department_id) is None:
        raise LookupError("Department not found")

    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])
    staff_user_rows = list(db.execute(
        select(Staff, User)
        .outerjoin(User, Staff.user_id == User.id)
        .where(Staff.department_id == department_id, Staff.active.is_(True))
        .order_by(Staff.employee_code)
    ))
    staff_rows = [staff for staff, _ in staff_user_rows]
    shift_rows = list(db.scalars(select(ShiftType).where(ShiftType.is_working_shift.is_(True)).order_by(ShiftType.code)))
    windows = list(db.scalars(select(CoverageWindow).where(CoverageWindow.department_id == department_id).order_by(CoverageWindow.code)))
    mappings = list(db.scalars(select(CoverageWindowShiftType)))
    mapped_shifts: dict[int, list[int]] = {}
    for mapping in mappings:
        mapped_shifts.setdefault(mapping.coverage_window_id, []).append(mapping.shift_type_id)

    rules = {
        row.key: row.integer_value
        for row in db.scalars(select(DepartmentRuleSetting).where(DepartmentRuleSetting.department_id == department_id, DepartmentRuleSetting.enabled.is_(True), DepartmentRuleSetting.key.in_(RULE_LIMITS)))
        if row.integer_value is not None
    }
    staff_ids = [item.id for item in staff_rows]
    # Scope leave data to the selected month; unrelated historical/future
    # leave must not block this month's solver snapshot.
    leaves = list(db.scalars(
        select(LeaveRequest)
        .join(Staff)
        .where(
            Staff.department_id == department_id,
            LeaveRequest.start_date <= month_end,
            LeaveRequest.end_date >= month_start,
        )
        .order_by(LeaveRequest.start_date, LeaveRequest.id)
    ))
    availability = list(db.scalars(select(Availability).where(Availability.staff_id.in_(staff_ids), Availability.date >= month_start, Availability.date <= month_end))) if staff_ids else []
    preferences = list(db.scalars(select(StaffShiftPreference).where(StaffShiftPreference.staff_id.in_(staff_ids), StaffShiftPreference.work_date >= month_start, StaffShiftPreference.work_date <= month_end))) if staff_ids else []
    schedule = db.scalar(select(Schedule).where(Schedule.department_id == department_id, Schedule.year == year, Schedule.month == month))
    locks = list(db.scalars(select(ScheduleDetail).where(ScheduleDetail.schedule_id == schedule.id, ScheduleDetail.locked.is_(True)))) if schedule else []

    issues = _preflight(staff_rows, shift_rows, windows, mapped_shifts, rules)
    return SchedulerSnapshot(
        department_id=department_id,
        year=year,
        month=month,
        staff=tuple(SchedulerStaff(
            row.id, row.employee_code, f"{row.first_name} {row.last_name}", row.position, row.is_senior_rn,
            user is not None and user.role == "head_nurse",
        ) for row, user in staff_user_rows),
        shifts=tuple(SchedulerShift(row.id, row.code, row.start_time, row.end_time, row.duration_minutes, row.crosses_midnight) for row in shift_rows),
        coverage_windows=tuple(SchedulerCoverageWindow(row.code, row.start_time, row.end_time, row.crosses_midnight, row.min_rn, row.max_rn, row.min_support_staff, row.min_senior_rn, tuple(sorted(mapped_shifts.get(row.id, [])))) for row in windows),
        rules=rules,
        leave_requests=tuple(SchedulerLeave(row.staff_id, row.start_date, row.end_date, row.status) for row in leaves),
        availability=tuple(SchedulerAvailability(row.staff_id, row.date, row.status, row.shift_type_id) for row in availability),
        preferences=tuple(SchedulerPreference(row.staff_id, row.work_date, row.shift_type_id, row.preference, row.weight) for row in preferences),
        locked_assignments=tuple(LockedAssignment(row.staff_id, row.shift_type_id, row.work_date) for row in locks),
        preflight_issues=tuple(issues),
    )


def _preflight(staff: list[Staff], shifts: list[ShiftType], windows: list[CoverageWindow], mappings: dict[int, list[int]], rules: dict[str, int]) -> list[PreflightIssue]:
    issues: list[PreflightIssue] = []
    if not staff:
        issues.append(PreflightIssue("error", "NO_ELIGIBLE_STAFF", "No active staff are assigned to this department"))
    if not shifts:
        issues.append(PreflightIssue("error", "NO_WORKING_SHIFTS", "No working shift types are configured"))
    for shift in shifts:
        if shift.start_time is None or shift.end_time is None or not shift.duration_minutes:
            issues.append(PreflightIssue("error", "INCOMPLETE_SHIFT_METADATA", f"Shift {shift.code} needs start time, end time, and duration"))
    if not windows:
        issues.append(PreflightIssue("error", "NO_COVERAGE_WINDOWS", "No ICU coverage windows are configured"))
    for window in windows:
        if not mappings.get(window.id):
            issues.append(PreflightIssue("error", "UNMAPPED_COVERAGE_WINDOW", f"Coverage window {window.code} has no mapped shifts"))
    for key in RULE_LIMITS:
        if key not in rules:
            issues.append(PreflightIssue("error", "MISSING_ICU_RULE", f"ICU rule {key} is not configured"))
    return issues
