"""Dry-run CP-SAT model containing ICU hard constraints; it never solves or writes data."""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import combinations

from ortools.sat.python import cp_model

from app.scheduler.contracts import LockedAssignment, PreflightIssue, SchedulerCoverageWindow, SchedulerLeave, SchedulerShift, SchedulerSnapshot
from app.scheduler.fairness_model import FairnessObjectiveModel, build_fairness_objective_model
from app.scheduler.preference_model import PreferenceObjectiveModel, build_preference_objective_model
from app.scheduler.ot_model import OtObjectiveModel, build_ot_objective_model
from app.scheduler.objective_composition import ObjectiveCompositionModel, build_objective_composition
from app.services.staff_qualification import HEAD_NURSE_ALLOWED_SHIFT_CODES


AssignmentKey = tuple[int, date, int]


@dataclass(frozen=True)
class AssignmentModel:
    """Typed CP-SAT model interface for future hard-constraint increments."""

    model: cp_model.CpModel
    assignments: dict[AssignmentKey, cp_model.IntVar]
    incharge_assignments: dict[AssignmentKey, cp_model.IntVar]
    locked_assignment_constraint_count: int
    locked_assignment_issues: tuple[PreflightIssue, ...]
    approved_leave_constraint_count: int
    approved_leave_issues: tuple[PreflightIssue, ...]
    availability_constraint_count: int
    availability_issues: tuple[PreflightIssue, ...]
    staffing_constraint_count: int
    coverage_constraint_count: int
    coverage_issues: tuple[PreflightIssue, ...]
    senior_rn_constraint_count: int
    incharge_qualification_constraint_count: int
    incharge_coverage_constraint_count: int
    senior_incharge_issues: tuple[PreflightIssue, ...]
    rest_constraint_count: int
    overlap_constraint_count: int
    multiple_shift_constraint_count: int
    one_shift_per_day_constraint_count: int
    rest_overlap_issues: tuple[PreflightIssue, ...]
    fairness: FairnessObjectiveModel
    preferences: PreferenceObjectiveModel
    overtime: OtObjectiveModel
    objective: ObjectiveCompositionModel


class AssignmentModelBuilder:
    """Builds typed ICU hard constraints from a read-only scheduler snapshot."""

    def build(self, snapshot: SchedulerSnapshot) -> AssignmentModel:
        model = cp_model.CpModel()
        assignments: dict[AssignmentKey, cp_model.IntVar] = {}
        incharge_assignments: dict[AssignmentKey, cp_model.IntVar] = {}

        for work_date in _month_dates(snapshot.year, snapshot.month):
            for staff in snapshot.staff:
                for shift in snapshot.shifts:
                    key = (staff.id, work_date, shift.id)
                    date_key = work_date.isoformat()
                    assignments[key] = model.NewBoolVar(f"x_s{staff.id}_d{date_key}_t{shift.id}")
                    incharge_assignments[key] = model.NewBoolVar(f"incharge_s{staff.id}_d{date_key}_t{shift.id}")

        locked_issues, valid_locks = _validate_locked_assignments(snapshot.locked_assignments, assignments)
        for lock in valid_locks:
            model.Add(assignments[(lock.staff_id, lock.work_date, lock.shift_type_id)] == 1)
        one_shift_per_day_count = _add_one_shift_per_day_constraints(model, assignments, snapshot)
        leave_issues, leave_keys = _validate_approved_leaves(snapshot.leave_requests, assignments, valid_locks)
        for key in leave_keys:
            model.Add(assignments[key] == 0)
        availability_issues, availability_keys = _validate_unavailable_availability(snapshot, assignments, valid_locks)
        for key in availability_keys:
            model.Add(assignments[key] == 0)
        _add_head_nurse_morning_constraints(model, assignments, snapshot)
        coverage_issues, valid_windows, requirements = _validate_coverage(snapshot)
        staffing_count, coverage_count = _add_staffing_coverage_constraints(
            model, assignments, snapshot, valid_windows, requirements,
        )
        senior_issues, senior_windows = _validate_senior_incharge(snapshot)
        senior_count, qualification_count, incharge_coverage_count = _add_senior_incharge_constraints(
            model, assignments, incharge_assignments, snapshot, senior_windows,
        )
        timing_issues, valid_shifts, rest_hours = _validate_timing(snapshot)
        rest_count, overlap_count, compatibility_count = _add_rest_overlap_constraints(
            model, assignments, snapshot, valid_shifts, rest_hours,
        )
        _add_d_de_continuation_constraints(model, assignments, snapshot)
        fairness = build_fairness_objective_model(model, assignments, snapshot)
        preferences = build_preference_objective_model(model, assignments, snapshot, valid_locks)
        overtime = build_ot_objective_model(model, fairness, snapshot)
        objective = build_objective_composition(model, fairness, preferences, overtime)

        return AssignmentModel(
            model, assignments, incharge_assignments,
            len(valid_locks), tuple(locked_issues), len(leave_keys), tuple(leave_issues), len(availability_keys), tuple(availability_issues),
            staffing_count, coverage_count, tuple(coverage_issues),
            senior_count, qualification_count, incharge_coverage_count, tuple(senior_issues),
            rest_count, overlap_count, compatibility_count, one_shift_per_day_count, tuple(timing_issues),
            fairness,
            preferences,
            overtime,
            objective,
        )


def _month_dates(year: int, month: int) -> tuple[date, ...]:
    return tuple(date(year, month, day) for day in range(1, monthrange(year, month)[1] + 1))


def _add_one_shift_per_day_constraints(
    model: cp_model.CpModel,
    assignments: dict[AssignmentKey, cp_model.IntVar],
    snapshot: SchedulerSnapshot,
) -> int:
    """Keep solver output compatible with Manual Schedule's one staff/date representation."""
    count = 0
    for staff in snapshot.staff:
        for work_date in _month_dates(snapshot.year, snapshot.month):
            variables = [
                assignments[(staff.id, work_date, shift.id)]
                for shift in snapshot.shifts
                if (staff.id, work_date, shift.id) in assignments
            ]
            if variables:
                model.Add(sum(variables) <= 1)
                count += 1
    return count


def _add_head_nurse_morning_constraints(
    model: cp_model.CpModel,
    assignments: dict[AssignmentKey, cp_model.IntVar],
    snapshot: SchedulerSnapshot,
) -> None:
    """A Head Nurse may be off/leave, but can only work AM or D shifts."""
    permitted_shift_ids = {shift.id for shift in snapshot.shifts if shift.code.strip().upper() in HEAD_NURSE_ALLOWED_SHIFT_CODES}
    if not permitted_shift_ids:
        return
    for staff in snapshot.staff:
        if not staff.is_head_nurse:
            continue
        for work_date in _month_dates(snapshot.year, snapshot.month):
            for shift in snapshot.shifts:
                if shift.id not in permitted_shift_ids:
                    model.Add(assignments[(staff.id, work_date, shift.id)] == 0)


def _validate_locked_assignments(
    locks: tuple[LockedAssignment, ...],
    assignments: dict[AssignmentKey, cp_model.IntVar],
) -> tuple[list[PreflightIssue], tuple[LockedAssignment, ...]]:
    """Validate locks before adding them so a malformed snapshot is explainable."""
    issues: list[PreflightIssue] = []
    invalid_indexes: set[int] = set()
    seen: dict[tuple[int, date], tuple[int, int]] = {}
    seen_exact: set[AssignmentKey] = set()

    for index, lock in enumerate(locks):
        key = (lock.staff_id, lock.work_date, lock.shift_type_id)
        if key not in assignments:
            issues.append(PreflightIssue(
                "error",
                "LOCKED_ASSIGNMENT_OUTSIDE_MODEL",
                f"Locked assignment staff={lock.staff_id}, date={lock.work_date}, shift={lock.shift_type_id} is not available in this snapshot",
            ))
            invalid_indexes.add(index)
            continue
        if key in seen_exact:
            issues.append(PreflightIssue(
                "error",
                "DUPLICATE_LOCKED_ASSIGNMENT",
                f"Locked assignment staff={lock.staff_id}, date={lock.work_date}, shift={lock.shift_type_id} appears more than once",
            ))
            invalid_indexes.add(index)
            continue
        seen_exact.add(key)
        staff_day = (lock.staff_id, lock.work_date)
        prior = seen.get(staff_day)
        if prior is not None and prior[0] != lock.shift_type_id:
            issues.append(PreflightIssue(
                "error",
                "LOCKED_ASSIGNMENT_CONFLICT",
                f"Staff {lock.staff_id} has conflicting locked shifts {prior[0]} and {lock.shift_type_id} on {lock.work_date}",
            ))
            issues.append(PreflightIssue(
                "error",
                "LOCKED_ASSIGNMENT_MULTIPLE_SHIFTS_PER_DAY",
                f"Staff {lock.staff_id} cannot keep more than one locked shift on {lock.work_date}; AI allows at most one assignment per staff/date",
            ))
            invalid_indexes.update((prior[1], index))
        else:
            seen[staff_day] = (lock.shift_type_id, index)

    valid = tuple(lock for index, lock in enumerate(locks) if index not in invalid_indexes)
    return issues, valid


def _validate_approved_leaves(
    leaves: tuple[SchedulerLeave, ...],
    assignments: dict[AssignmentKey, cp_model.IntVar],
    valid_locks: tuple[LockedAssignment, ...],
) -> tuple[list[PreflightIssue], tuple[AssignmentKey, ...]]:
    """Turn only approved, valid leave dates into x=0 constraints."""
    issues: list[PreflightIssue] = []
    constrained: set[AssignmentKey] = set()
    staff_ids = {key[0] for key in assignments}
    model_dates = {key[1] for key in assignments}
    shift_ids = {key[2] for key in assignments}
    locked_keys = {(item.staff_id, item.work_date, item.shift_type_id) for item in valid_locks}

    for leave in leaves:
        if leave.end_date < leave.start_date:
            issues.append(PreflightIssue("error", "INVALID_LEAVE_RANGE", f"Leave for staff {leave.staff_id} ends before it starts"))
            continue
        if leave.status not in {"approved", "pending", "rejected", "cancelled"}:
            issues.append(PreflightIssue("error", "INVALID_LEAVE_STATUS", f"Leave for staff {leave.staff_id} has unsupported status {leave.status}"))
            continue
        if leave.status != "approved":
            continue
        if leave.staff_id not in staff_ids:
            issues.append(PreflightIssue("error", "APPROVED_LEAVE_STAFF_NOT_ELIGIBLE", f"Approved leave belongs to staff {leave.staff_id}, who is not active in this snapshot"))
            continue

        leave_dates = tuple(_dates_inclusive(leave.start_date, leave.end_date))
        in_snapshot_dates = tuple(work_date for work_date in leave_dates if work_date in model_dates)
        if len(in_snapshot_dates) != len(leave_dates):
            issues.append(PreflightIssue("error", "APPROVED_LEAVE_OUTSIDE_SNAPSHOT", f"Approved leave for staff {leave.staff_id} includes date(s) outside the generation month"))
        for work_date in in_snapshot_dates:
            for shift_id in shift_ids:
                key = (leave.staff_id, work_date, shift_id)
                constrained.add(key)
                if key in locked_keys:
                    issues.append(PreflightIssue("error", "LOCKED_ASSIGNMENT_ON_APPROVED_LEAVE", f"Locked assignment staff={leave.staff_id}, date={work_date}, shift={shift_id} conflicts with approved leave"))

    return issues, tuple(sorted(constrained))


def _validate_unavailable_availability(
    snapshot: SchedulerSnapshot,
    assignments: dict[AssignmentKey, cp_model.IntVar],
    valid_locks: tuple[LockedAssignment, ...],
) -> tuple[list[PreflightIssue], tuple[AssignmentKey, ...]]:
    """Turn unavailable rows into x=0 constraints; a null shift means ALL shifts."""
    issues: list[PreflightIssue] = []
    constrained: set[AssignmentKey] = set()
    staff_by_id = {staff.id: staff for staff in snapshot.staff}
    model_dates = {key[1] for key in assignments}
    model_shift_ids = {key[2] for key in assignments}
    locked_keys = {(item.staff_id, item.work_date, item.shift_type_id) for item in valid_locks}
    for item in snapshot.availability:
        if item.status != "unavailable":
            continue
        if item.staff_id not in staff_by_id:
            issues.append(PreflightIssue("error", "AVAILABILITY_STAFF_NOT_ELIGIBLE", f"Availability belongs to staff {item.staff_id}, who is not active in this snapshot"))
            continue
        if item.work_date not in model_dates:
            issues.append(PreflightIssue("error", "AVAILABILITY_OUTSIDE_SNAPSHOT", f"Availability for {staff_by_id[item.staff_id].employee_code} on {item.work_date} is outside the generation month"))
            continue
        shift_ids = model_shift_ids if item.shift_type_id is None else {item.shift_type_id}
        if item.shift_type_id is not None and item.shift_type_id not in model_shift_ids:
            issues.append(PreflightIssue("error", "AVAILABILITY_UNKNOWN_SHIFT", f"Availability for {staff_by_id[item.staff_id].employee_code} references unavailable shift id {item.shift_type_id}"))
            continue
        if item.shift_type_id is None:
            issues.append(PreflightIssue("warning", "AVAILABILITY_ALL_DAY", f"All shifts blocked by unavailable availability: {staff_by_id[item.staff_id].employee_code} on {item.work_date}"))
        for shift_id in shift_ids:
            key = (item.staff_id, item.work_date, shift_id)
            constrained.add(key)
            if key in locked_keys:
                issues.append(PreflightIssue("error", "LOCKED_ASSIGNMENT_ON_UNAVAILABLE", f"Locked assignment staff={item.staff_id}, date={item.work_date}, shift={shift_id} conflicts with unavailable availability"))
    return issues, tuple(sorted(constrained))


def _dates_inclusive(start_date: date, end_date: date):
    current = start_date
    while current <= end_date:
        yield current
        current = current.fromordinal(current.toordinal() + 1)


def _validate_coverage(
    snapshot: SchedulerSnapshot,
) -> tuple[list[PreflightIssue], tuple[SchedulerCoverageWindow, ...], tuple[int, int, int] | None]:
    """Validate real-time coverage configuration before adding staffing constraints."""
    issues: list[PreflightIssue] = []
    required_keys = ("MIN_RN", "MAX_RN", "MIN_SUPPORT")
    missing = [key for key in required_keys if key not in snapshot.rules]
    for key in missing:
        issues.append(PreflightIssue("error", "MISSING_ICU_RULE", f"ICU rule {key} is required for staffing coverage"))
    requirements: tuple[int, int, int] | None = None
    if not missing:
        min_rn, max_rn, min_support = (snapshot.rules[key] for key in required_keys)
        requirements = (min_rn, max_rn, min_support)
    if requirements is not None and (min_rn < 0 or max_rn < min_rn or min_support < 0):
        issues.append(PreflightIssue("error", "INVALID_STAFFING_RULES", "MIN_RN, MAX_RN, and MIN_SUPPORT have invalid bounds"))
    if not snapshot.coverage_windows:
        issues.append(PreflightIssue("error", "NO_COVERAGE_WINDOWS", "No coverage windows are configured for this department"))

    known_shift_ids = {shift.id for shift in snapshot.shifts}
    valid_windows: list[SchedulerCoverageWindow] = []
    for window in snapshot.coverage_windows:
        mapped = set(window.shift_type_ids)
        if not mapped:
            issues.append(PreflightIssue("error", "UNMAPPED_COVERAGE_WINDOW", f"Coverage window {window.code} has no mapped working shifts"))
            continue
        unknown_shifts = mapped - known_shift_ids
        if unknown_shifts:
            issues.append(PreflightIssue("error", "INVALID_COVERAGE_SHIFT_MAPPING", f"Coverage window {window.code} maps unavailable shift id(s): {sorted(unknown_shifts)}"))
            continue
        valid_windows.append(window)
    if missing or requirements is None or any(item.code == "INVALID_STAFFING_RULES" for item in issues):
        return issues, (), None
    return issues, tuple(valid_windows), requirements


def _add_staffing_coverage_constraints(
    model: cp_model.CpModel,
    assignments: dict[AssignmentKey, cp_model.IntVar],
    snapshot: SchedulerSnapshot,
    windows: tuple[SchedulerCoverageWindow, ...],
    requirements: tuple[int, int, int] | None,
) -> tuple[int, int]:
    if requirements is None:
        return 0, 0
    min_rn, max_rn, min_support = requirements
    staffing_count = 0
    coverage_count = 0
    rn_staff_ids = {staff.id for staff in snapshot.staff if _is_rn_position(staff.position)}
    support_staff_ids = {staff.id for staff in snapshot.staff if _is_support_position(staff.position)}
    for work_date in _month_dates(snapshot.year, snapshot.month):
        for window in windows:
            rn_variables = [
                variable for (staff_id, key_date, shift_id), variable in assignments.items()
                if key_date == work_date and staff_id in rn_staff_ids and shift_id in window.shift_type_ids
            ]
            support_variables = [
                variable for (staff_id, key_date, shift_id), variable in assignments.items()
                if key_date == work_date and staff_id in support_staff_ids and shift_id in window.shift_type_ids
            ]
            model.Add(sum(rn_variables) >= min_rn)
            model.Add(sum(rn_variables) <= max_rn)
            model.Add(sum(support_variables) >= min_support)
            staffing_count += 3
            coverage_count += 1
    return staffing_count, coverage_count


def _is_rn_position(position: str) -> bool:
    return position.strip().upper().replace("_", " ") in {"RN", "HEAD NURSE"}


def _is_support_position(position: str) -> bool:
    return position.strip().upper() in {"PN", "NA"}


def _validate_senior_incharge(snapshot: SchedulerSnapshot) -> tuple[list[PreflightIssue], tuple[SchedulerCoverageWindow, ...]]:
    issues: list[PreflightIssue] = []
    if not snapshot.coverage_windows:
        issues.append(PreflightIssue("error", "NO_COVERAGE_WINDOWS", "Senior RN and Incharge coverage needs configured coverage windows"))
        return issues, ()
    known_shift_ids = {shift.id for shift in snapshot.shifts}
    valid_windows: list[SchedulerCoverageWindow] = []
    for window in snapshot.coverage_windows:
        if window.min_senior_rn < 0:
            issues.append(PreflightIssue("error", "INVALID_SENIOR_RN_REQUIREMENT", f"Coverage window {window.code} has a negative Senior RN minimum"))
            continue
        if not window.shift_type_ids:
            issues.append(PreflightIssue("error", "UNMAPPED_COVERAGE_WINDOW", f"Coverage window {window.code} has no mapped working shifts"))
            continue
        unknown = set(window.shift_type_ids) - known_shift_ids
        if unknown:
            issues.append(PreflightIssue("error", "INVALID_COVERAGE_SHIFT_MAPPING", f"Coverage window {window.code} maps unavailable shift id(s): {sorted(unknown)}"))
            continue
        valid_windows.append(window)
    if not any(staff.is_senior_rn for staff in snapshot.staff):
        issues.append(PreflightIssue("error", "NO_SENIOR_RN_ELIGIBLE_STAFF", "No active Senior RN is available for Incharge coverage"))
    return issues, tuple(valid_windows)


def _add_senior_incharge_constraints(
    model: cp_model.CpModel,
    assignments: dict[AssignmentKey, cp_model.IntVar],
    incharge_assignments: dict[AssignmentKey, cp_model.IntVar],
    snapshot: SchedulerSnapshot,
    windows: tuple[SchedulerCoverageWindow, ...],
) -> tuple[int, int, int]:
    senior_staff_ids = {staff.id for staff in snapshot.staff if staff.is_senior_rn}
    qualification_count = 0
    for key, incharge_variable in incharge_assignments.items():
        model.Add(incharge_variable <= assignments[key])
        qualification_count += 1
        if key[0] not in senior_staff_ids:
            model.Add(incharge_variable == 0)
            qualification_count += 1

    senior_count = 0
    incharge_coverage_count = 0
    for work_date in _month_dates(snapshot.year, snapshot.month):
        for window in windows:
            senior_assignment_variables = [
                variable for (staff_id, key_date, shift_id), variable in assignments.items()
                if key_date == work_date and staff_id in senior_staff_ids and shift_id in window.shift_type_ids
            ]
            covered_incharge_variables = [
                variable for (staff_id, key_date, shift_id), variable in incharge_assignments.items()
                if key_date == work_date and shift_id in window.shift_type_ids
            ]
            model.Add(sum(senior_assignment_variables) >= window.min_senior_rn)
            model.Add(sum(covered_incharge_variables) >= 1)
            senior_count += 1
            incharge_coverage_count += 1
    return senior_count, qualification_count, incharge_coverage_count


def _validate_timing(snapshot: SchedulerSnapshot) -> tuple[list[PreflightIssue], dict[int, SchedulerShift], int | None]:
    issues: list[PreflightIssue] = []
    valid_shifts: dict[int, SchedulerShift] = {}
    for shift in snapshot.shifts:
        if shift.start_time is None or shift.end_time is None or shift.duration_minutes is None or shift.duration_minutes <= 0:
            issues.append(PreflightIssue("error", "INCOMPLETE_SHIFT_TIMING", f"Shift {shift.code} needs valid start, end, and duration metadata"))
            continue
        if shift.start_time == shift.end_time and not shift.crosses_midnight:
            issues.append(PreflightIssue("error", "INVALID_SHIFT_TIMING", f"Shift {shift.code} has equal start/end without overnight metadata"))
            continue
        valid_shifts[shift.id] = shift
    rest_hours = snapshot.rules.get("REST_AFTER_NIGHT")
    if rest_hours is None:
        issues.append(PreflightIssue("error", "MISSING_ICU_RULE", "ICU rule REST_AFTER_NIGHT is required for rest constraints"))
    elif rest_hours <= 0:
        issues.append(PreflightIssue("error", "INVALID_REST_AFTER_NIGHT", "REST_AFTER_NIGHT must be greater than zero"))
        rest_hours = None
    return issues, valid_shifts, rest_hours


def _add_rest_overlap_constraints(
    model: cp_model.CpModel,
    assignments: dict[AssignmentKey, cp_model.IntVar],
    snapshot: SchedulerSnapshot,
    valid_shifts: dict[int, SchedulerShift],
    rest_hours: int | None,
) -> tuple[int, int, int]:
    overlap_pairs: set[tuple[AssignmentKey, AssignmentKey]] = set()
    compatibility_pairs: set[tuple[AssignmentKey, AssignmentKey]] = set()
    rest_pairs: set[tuple[AssignmentKey, AssignmentKey]] = set()
    by_staff: dict[int, list[tuple[AssignmentKey, datetime, datetime, SchedulerShift]]] = {}
    for key in assignments:
        shift = valid_shifts.get(key[2])
        if shift is None:
            continue
        start, end = _shift_interval(key[1], shift)
        by_staff.setdefault(key[0], []).append((key, start, end, shift))

    for candidates in by_staff.values():
        for first, second in combinations(candidates, 2):
            first_key, first_start, first_end, first_shift = first
            second_key, second_start, second_end, second_shift = second
            ordered = (first, second) if first_start <= second_start else (second, first)
            earlier, later = ordered
            earlier_key, earlier_start, earlier_end, earlier_shift = earlier
            later_key, later_start, later_end, later_shift = later
            pair = (earlier_key, later_key)
            if earlier_start < later_end and later_start < earlier_end:
                overlap_pairs.add(pair)
            if earlier_key[1] == later_key[1] and earlier_end <= later_start:
                codes = {earlier_shift.code.upper(), later_shift.code.upper()}
                if (later_start - earlier_end) > timedelta() or codes == {"D", "DE"}:
                    compatibility_pairs.add(pair)
            if rest_hours is not None and earlier_shift.code.upper() in {"N", "DE"} and later_start >= earlier_end:
                if later_start - earlier_end < timedelta(hours=rest_hours):
                    rest_pairs.add(pair)

    for first_key, second_key in overlap_pairs:
        model.Add(assignments[first_key] + assignments[second_key] <= 1)
    for first_key, second_key in compatibility_pairs:
        model.Add(assignments[first_key] + assignments[second_key] <= 1)
    for first_key, second_key in rest_pairs:
        model.Add(assignments[first_key] + assignments[second_key] <= 1)
    return len(rest_pairs), len(overlap_pairs), len(compatibility_pairs)


def _add_d_de_continuation_constraints(
    model: cp_model.CpModel,
    assignments: dict[AssignmentKey, cp_model.IntVar],
    snapshot: SchedulerSnapshot,
) -> int:
    """Mirror the Manual ICU validator: every D day needs DE overnight coverage."""
    d_shift_ids = {shift.id for shift in snapshot.shifts if shift.code.upper() == "D"}
    de_shift_ids = {shift.id for shift in snapshot.shifts if shift.code.upper() == "DE"}
    if not d_shift_ids or not de_shift_ids:
        return 0
    count = 0
    for work_date in _month_dates(snapshot.year, snapshot.month):
        d_variables = [assignments[(staff.id, work_date, shift_id)] for staff in snapshot.staff for shift_id in d_shift_ids]
        de_variables = [assignments[(staff.id, work_date, shift_id)] for staff in snapshot.staff for shift_id in de_shift_ids]
        if d_variables and de_variables:
            # If any D is used, at least one different staff member must cover DE.
            # One-shift-per-day constraints already prevent a person covering both.
            model.Add(sum(d_variables) <= len(d_variables) * sum(de_variables))
            count += 1
    return count


def _shift_interval(work_date: date, shift: SchedulerShift) -> tuple[datetime, datetime]:
    start = datetime.combine(work_date, shift.start_time)
    end = datetime.combine(work_date, shift.end_time)
    if shift.crosses_midnight or end <= start:
        end += timedelta(days=1)
    return start, end
