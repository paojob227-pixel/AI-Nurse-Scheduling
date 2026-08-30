"""Read-only ICU v1.1 validation for manual schedules.

This module reports conflicts; it never changes assignments and does not use an
optimizer or OR-Tools.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Availability, CoverageWindow, CoverageWindowShiftType, DepartmentRuleSetting,
    LeaveRequest, Schedule, ScheduleDetail, ShiftType, Staff, StaffShiftPreference, User,
)
from app.services.staff_qualification import HEAD_NURSE_ALLOWED_SHIFT_CODES


Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Conflict:
    severity: Severity
    code: str
    work_date: date
    shift: str
    staff_ids: tuple[int, ...]
    staff_names: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class Assignment:
    id: int
    staff_id: int
    staff_name: str
    position: str
    is_senior_rn: bool
    work_date: date
    shift_id: int
    shift_code: str
    start_time: time | None
    end_time: time | None
    crosses_midnight: bool
    is_incharge: bool
    incharge_exception: bool
    exception_reason: str | None
    exception_approved_by_user_id: int | None
    is_head_nurse: bool = False


@dataclass(frozen=True)
class Window:
    code: str
    shift_ids: frozenset[int]
    min_rn: int
    max_rn: int
    min_support: int
    min_senior_rn: int


@dataclass(frozen=True)
class LeavePeriod:
    staff_id: int
    start_date: date
    end_date: date


@dataclass(frozen=True)
class SoftPreference:
    staff_id: int
    work_date: date
    shift_id: int | None
    preference: str
    weight: int


def _conflict(severity: Severity, code: str, work_date: date, shift: str, assignments: list[Assignment], reason: str) -> Conflict:
    return Conflict(severity, code, work_date, shift, tuple(item.staff_id for item in assignments), tuple(item.staff_name for item in assignments), reason)


def _is_rn(assignment: Assignment) -> bool:
    return assignment.position.strip().upper().replace("_", " ") in {"RN", "HEAD NURSE"}


def _is_support(assignment: Assignment) -> bool:
    return assignment.position.strip().upper() in {"PN", "NA"}


def _interval(assignment: Assignment) -> tuple[datetime, datetime] | None:
    if assignment.start_time is None or assignment.end_time is None:
        return None
    start = datetime.combine(assignment.work_date, assignment.start_time)
    end = datetime.combine(assignment.work_date, assignment.end_time)
    if assignment.crosses_midnight or end <= start:
        end += timedelta(days=1)
    return start, end


def _month_dates(year: int, month: int) -> list[date]:
    return [date(year, month, day) for day in range(1, monthrange(year, month)[1] + 1)]


def validate_context(
    assignments: list[Assignment], windows: list[Window], rules: dict[str, int], leaves: list[LeavePeriod], preferences: list[SoftPreference], year: int, month: int,
) -> list[Conflict]:
    """Validate a fully loaded schedule context without writing to the database."""
    conflicts: list[Conflict] = []
    by_date: dict[date, list[Assignment]] = {}
    by_staff: dict[int, list[Assignment]] = {}
    for assignment in assignments:
        by_date.setdefault(assignment.work_date, []).append(assignment)
        by_staff.setdefault(assignment.staff_id, []).append(assignment)

    for assignment in assignments:
        if assignment.is_head_nurse and assignment.shift_code.strip().upper() not in HEAD_NURSE_ALLOWED_SHIFT_CODES:
            conflicts.append(_conflict(
                "error", "HEAD_NURSE_MORNING_ONLY", assignment.work_date, assignment.shift_code, [assignment],
                "Head Nurse may only be assigned to the AM or D shift",
            ))

    min_rn = rules.get("MIN_RN")
    max_rn = rules.get("MAX_RN")
    min_support = rules.get("MIN_SUPPORT")
    for work_date in _month_dates(year, month):
        day_assignments = by_date.get(work_date, [])
        for window in windows:
            covered = [item for item in day_assignments if item.shift_id in window.shift_ids]
            rns = [item for item in covered if _is_rn(item)]
            support = [item for item in covered if _is_support(item)]
            senior_rns = [item for item in rns if item.is_senior_rn]
            required_rn = min_rn if min_rn is not None else window.min_rn
            allowed_rn = max_rn if max_rn is not None else window.max_rn
            required_support = min_support if min_support is not None else window.min_support
            if len(rns) < required_rn:
                conflicts.append(_conflict("error", "MIN_RN", work_date, window.code, covered, f"RN coverage is {len(rns)}; minimum is {required_rn}"))
            if len(rns) > allowed_rn:
                conflicts.append(_conflict("warning", "MAX_RN", work_date, window.code, rns, f"RN coverage is {len(rns)}; configured maximum is {allowed_rn}"))
            if len(support) < required_support:
                conflicts.append(_conflict("error", "MIN_SUPPORT", work_date, window.code, covered, f"PN/NA coverage is {len(support)}; minimum is {required_support}"))
            incharges = [item for item in covered if item.is_incharge]
            approved_exception_present = any(item.incharge_exception and item.exception_reason and item.exception_approved_by_user_id is not None for item in incharges)
            if len(senior_rns) < window.min_senior_rn:
                severity: Severity = "warning" if approved_exception_present else "error"
                code = "SENIOR_RN_EXCEPTION" if approved_exception_present else "SENIOR_RN_REQUIRED"
                conflicts.append(_conflict(severity, code, work_date, window.code, covered, f"Senior RN coverage is {len(senior_rns)}; minimum is {window.min_senior_rn}"))
            if not incharges:
                conflicts.append(_conflict("error", "INCHARGE_REQUIRED", work_date, window.code, covered, "No Incharge is assigned for this coverage window"))
            for incharge in incharges:
                approved_exception = incharge.incharge_exception and incharge.exception_reason and incharge.exception_approved_by_user_id is not None
                if not incharge.is_senior_rn and not approved_exception:
                    conflicts.append(_conflict("error", "INCHARGE_QUALIFICATION", work_date, window.code, [incharge], "Incharge must be a Senior RN or have an approved exception"))
                elif not incharge.is_senior_rn:
                    conflicts.append(_conflict("warning", "INCHARGE_EXCEPTION", work_date, window.code, [incharge], "A non-Senior RN Incharge exception is in use"))

        d_assignments = [item for item in day_assignments if item.shift_code.upper() == "D"]
        de_assignments = [item for item in day_assignments if item.shift_code.upper() == "DE"]
        if d_assignments and not de_assignments:
            conflicts.append(_conflict("error", "D_DE_CONTINUATION", work_date, "D/DE", d_assignments, "D shift requires a DE shift to continue overnight coverage"))
        if {item.staff_id for item in d_assignments} & {item.staff_id for item in de_assignments}:
            involved = [item for item in d_assignments + de_assignments if item.staff_id in {d.staff_id for d in d_assignments} & {de.staff_id for de in de_assignments}]
            conflicts.append(_conflict("error", "D_DE_SAME_PERSON", work_date, "D/DE", involved, "The same person cannot work both D and DE"))

    for leave in leaves:
        for assignment in by_staff.get(leave.staff_id, []):
            if leave.start_date <= assignment.work_date <= leave.end_date:
                conflicts.append(_conflict("error", "APPROVED_LEAVE", assignment.work_date, assignment.shift_code, [assignment], "Staff is assigned during an approved leave period"))

    rest_hours = rules.get("REST_AFTER_NIGHT", 8)
    for staff_assignments in by_staff.values():
        intervals = [(assignment, _interval(assignment)) for assignment in staff_assignments]
        intervals = [(assignment, interval) for assignment, interval in intervals if interval is not None]
        intervals.sort(key=lambda item: item[1][0])
        for index, (current, current_interval) in enumerate(intervals):
            for following, following_interval in intervals[index + 1:]:
                if following_interval[0] >= current_interval[1]:
                    break
                conflicts.append(_conflict("error", "SHIFT_OVERLAP", following.work_date, f"{current.shift_code}/{following.shift_code}", [current, following], "Assigned shifts overlap in time"))
            if current.shift_code.upper() not in {"N", "DE"} and not current.crosses_midnight:
                continue
            for following, following_interval in intervals[index + 1:]:
                if following_interval[0] < current_interval[1]:
                    continue
                gap_hours = (following_interval[0] - current_interval[1]).total_seconds() / 3600
                if gap_hours >= rest_hours:
                    break
                conflicts.append(_conflict("error", "REST_AFTER_NIGHT", following.work_date, f"{current.shift_code}/{following.shift_code}", [current, following], f"Rest after {current.shift_code} is {gap_hours:g} hours; minimum is {rest_hours}"))
                if following.shift_code.upper() in {"AM", "D"}:
                    conflicts.append(_conflict("error", "N_DE_TO_MORNING", following.work_date, f"{current.shift_code}/{following.shift_code}", [current, following], "N/DE cannot continue directly to AM or D"))
                break

    assignment_keys = {(item.staff_id, item.work_date, item.shift_id) for item in assignments}
    for preference in preferences:
        matching = [item for item in assignments if item.staff_id == preference.staff_id and item.work_date == preference.work_date and (preference.shift_id is None or item.shift_id == preference.shift_id)]
        if preference.preference == "avoid" and matching:
            conflicts.append(_conflict("warning", "SOFT_PREFERENCE_AVOID", preference.work_date, matching[0].shift_code, matching, f"A soft avoid preference (weight {preference.weight}) was not met"))
        if preference.preference == "prefer" and (preference.staff_id, preference.work_date, preference.shift_id) not in assignment_keys:
            conflicts.append(Conflict("warning", "SOFT_PREFERENCE_PREFER", preference.work_date, "Preference", (preference.staff_id,), (), f"A soft preferred shift (weight {preference.weight}) was not assigned"))
    return conflicts


def validate_schedule(db: Session, schedule_id: int) -> list[Conflict]:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise LookupError("Schedule not found")
    rows = db.execute(select(ScheduleDetail, Staff, ShiftType, User).join(Staff, ScheduleDetail.staff_id == Staff.id).join(ShiftType, ScheduleDetail.shift_type_id == ShiftType.id).outerjoin(User, Staff.user_id == User.id).where(ScheduleDetail.schedule_id == schedule_id)).all()
    assignments = [Assignment(detail.id, staff.id, f"{staff.first_name} {staff.last_name}", staff.position, staff.is_senior_rn, detail.work_date, shift.id, shift.code, shift.start_time, shift.end_time, shift.crosses_midnight, detail.is_incharge, detail.incharge_exception, detail.exception_reason, detail.exception_approved_by_user_id, user is not None and user.role == "head_nurse") for detail, staff, shift, user in rows]
    window_rows = list(db.scalars(select(CoverageWindow).where(CoverageWindow.department_id == schedule.department_id)))
    linked_shifts = db.execute(select(CoverageWindowShiftType.coverage_window_id, CoverageWindowShiftType.shift_type_id)).all()
    links: dict[int, set[int]] = {}
    for window_id, shift_id in linked_shifts:
        links.setdefault(window_id, set()).add(shift_id)
    windows = [Window(window.code, frozenset(links.get(window.id, set())), window.min_rn, window.max_rn, window.min_support_staff, window.min_senior_rn) for window in window_rows]
    rule_rows = db.scalars(select(DepartmentRuleSetting).where(DepartmentRuleSetting.department_id == schedule.department_id, DepartmentRuleSetting.enabled.is_(True))).all()
    rules = {rule.key: rule.integer_value for rule in rule_rows if rule.integer_value is not None}
    staff_ids = {item.staff_id for item in assignments}
    leaves = [LeavePeriod(item.staff_id, item.start_date, item.end_date) for item in db.scalars(select(LeaveRequest).where(LeaveRequest.status == "approved", LeaveRequest.staff_id.in_(staff_ids))).all()] if staff_ids else []
    preference_rows = db.scalars(select(StaffShiftPreference).where(StaffShiftPreference.staff_id.in_(staff_ids), StaffShiftPreference.work_date >= date(schedule.year, schedule.month, 1), StaffShiftPreference.work_date <= date(schedule.year, schedule.month, monthrange(schedule.year, schedule.month)[1]))).all() if staff_ids else []
    preferences = [SoftPreference(item.staff_id, item.work_date, item.shift_type_id, item.preference, item.weight) for item in preference_rows]
    unavailable_rows = db.scalars(select(Availability).where(Availability.staff_id.in_(staff_ids), Availability.status.in_(("unavailable", "preferred_off")))).all() if staff_ids else []
    preferences.extend(SoftPreference(item.staff_id, item.date, None, "avoid", 1) for item in unavailable_rows)
    conflicts = validate_context(assignments, windows, rules, leaves, preferences, schedule.year, schedule.month)
    if not windows:
        conflicts.insert(0, Conflict("warning", "COVERAGE_WINDOWS_MISSING", date(schedule.year, schedule.month, 1), "Coverage", (), (), "No coverage windows are configured for this department"))
    return conflicts
