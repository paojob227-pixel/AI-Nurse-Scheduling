import gc
import unittest
from datetime import date, time

from pydantic import ValidationError
from ortools.sat.python import cp_model

from app.core.security import hash_password, verify_password
from app.schemas import LeaveCreate
from app.services.icu_rules import IcuRuleError, validate_rule_set, validate_rule_value
from app.services.staff_qualification import StaffQualificationError, resolve_senior_rn_status
from app.services.staff_preferences import StaffPreferenceError, validate_preference
from app.services.schedule_publish_validation import conflict_snapshot, summarize_for_publish
from app.services.schedule_validator import Assignment, Conflict, LeavePeriod, SoftPreference, Window, validate_context
from app.services.ai_preview_validation import PreviewAssignmentInput, validate_preview
from app.services.ai_draft_approval import AiDraftApprovalError, approve_draft, reject_draft, submit_for_approval
from app.services.ai_draft_conversion import AiDraftConversionError, validate_conversion_eligibility
from app.models import AiScheduleDraft, AiScheduleDraftDetail, User
from app.scheduler.assignment_model import AssignmentModelBuilder
from app.scheduler.contracts import LockedAssignment, SchedulerAvailability, SchedulerCoverageWindow, SchedulerLeave, SchedulerPreference, SchedulerShift, SchedulerSnapshot, SchedulerStaff
from app.pilot_import.service import PilotDataset, validate_dataset
from app.scheduler.snapshot_loader import _preflight
from app.scheduler.solver import CpSatSchedulerSolver


class CoreTests(unittest.TestCase):
    def tearDown(self) -> None:
        # Release CP-SAT protobuf/native allocations between isolated model tests on Python 3.14.
        gc.collect()

    def test_password_hash_is_verified(self) -> None:
        password_hash = hash_password("safe-password")
        self.assertTrue(verify_password("safe-password", password_hash))
        self.assertFalse(verify_password("wrong-password", password_hash))

    def test_leave_end_date_cannot_precede_start_date(self) -> None:
        with self.assertRaises(ValidationError):
            LeaveCreate(leave_type="annual", start_date="2026-08-02", end_date="2026-08-01")

    def test_icu_rule_value_bounds_are_validated(self) -> None:
        validate_rule_value("MIN_RN", 3)
        with self.assertRaises(IcuRuleError):
            validate_rule_value("REST_AFTER_NIGHT", 0)
        with self.assertRaises(IcuRuleError):
            validate_rule_value("NOT_A_RULE", 1)

    def test_icu_rule_cross_validation(self) -> None:
        validate_rule_set({"MIN_RN": 3, "MAX_RN": 4, "MONTHLY_HOURS": 168, "OT_THRESHOLD": 168})
        with self.assertRaises(IcuRuleError):
            validate_rule_set({"MIN_RN": 5, "MAX_RN": 4})
        with self.assertRaises(IcuRuleError):
            validate_rule_set({"MONTHLY_HOURS": 168, "OT_THRESHOLD": 160})

    def test_senior_rn_qualification_rules(self) -> None:
        self.assertTrue(resolve_senior_rn_status("RN", "nurse", True))
        self.assertFalse(resolve_senior_rn_status("RN", "nurse", False))
        self.assertTrue(resolve_senior_rn_status("PN", "head_nurse", False))
        self.assertTrue(resolve_senior_rn_status("Head Nurse", None, False))
        with self.assertRaises(StaffQualificationError):
            resolve_senior_rn_status("PN", "nurse", True)
        with self.assertRaises(StaffQualificationError):
            resolve_senior_rn_status("NA", "nurse_assistant", True)

    def test_preference_soft_constraint_validation(self) -> None:
        validate_preference("prefer", 1)
        validate_preference("avoid", 5)
        with self.assertRaises(StaffPreferenceError):
            validate_preference("required", 1)
        with self.assertRaises(StaffPreferenceError):
            validate_preference("prefer", 6)

    def test_schedule_validator_reports_leave_and_soft_preference(self) -> None:
        assignment = Assignment(1, 10, "RN One", "RN", True, date(2026, 8, 1), 1, "AM", time(7), time(15), False, True, False, None, None)
        window = Window("07-15", frozenset({1}), 1, 4, 0, 1)
        conflicts = validate_context([assignment], [window], {"MIN_RN": 1, "MAX_RN": 4, "MIN_SUPPORT": 0}, [LeavePeriod(10, date(2026, 8, 1), date(2026, 8, 1))], [SoftPreference(10, date(2026, 8, 1), 1, "avoid", 3)], 2026, 8)
        codes = {item.code for item in conflicts}
        self.assertIn("APPROVED_LEAVE", codes)
        self.assertIn("SOFT_PREFERENCE_AVOID", codes)

    def test_schedule_validator_reports_d_de_and_night_rest_rules(self) -> None:
        assignments = [
            Assignment(1, 10, "RN One", "RN", True, date(2026, 8, 1), 1, "D", time(7), time(19), False, True, False, None, None),
            Assignment(2, 11, "RN Two", "RN", True, date(2026, 8, 1), 2, "N", time(23), time(7), True, True, False, None, None),
            Assignment(3, 11, "RN Two", "RN", True, date(2026, 8, 2), 3, "AM", time(7), time(15), False, True, False, None, None),
        ]
        conflicts = validate_context(assignments, [], {"REST_AFTER_NIGHT": 8}, [], [], 2026, 8)
        codes = {item.code for item in conflicts}
        self.assertIn("D_DE_CONTINUATION", codes)
        self.assertIn("REST_AFTER_NIGHT", codes)
        self.assertIn("N_DE_TO_MORNING", codes)

    def test_publish_validation_blocks_errors_and_allows_warnings(self) -> None:
        error = Conflict("error", "APPROVED_LEAVE", date(2026, 8, 1), "AM", (10,), ("RN One",), "Approved leave")
        warning = Conflict("warning", "SOFT_PREFERENCE_AVOID", date(2026, 8, 1), "AM", (10,), ("RN One",), "Preference")
        blocked = summarize_for_publish([error, warning])
        self.assertEqual(blocked.outcome, "blocked")
        self.assertEqual(blocked.approval_state, "rejected")
        allowed = summarize_for_publish([warning])
        self.assertEqual(allowed.outcome, "published_with_warnings")
        self.assertEqual(allowed.approval_state, "approved_with_warnings")
        self.assertEqual(conflict_snapshot([warning])[0]["work_date"], "2026-08-01")

    def test_scheduler_preflight_reports_missing_foundation_data(self) -> None:
        issues = _preflight([], [], [], {}, {})
        codes = {issue.code for issue in issues}
        self.assertIn("NO_ELIGIBLE_STAFF", codes)
        self.assertIn("NO_WORKING_SHIFTS", codes)
        self.assertIn("NO_COVERAGE_WINDOWS", codes)
        self.assertIn("MISSING_ICU_RULE", codes)

    def test_scheduler_dry_run_never_creates_assignments(self) -> None:
        snapshot = SchedulerSnapshot(1, 2026, 8, (), (), (), {}, (), (), (), (), ())
        result = CpSatSchedulerSolver().dry_run(snapshot)
        self.assertEqual(result.solver_status, "MODEL_INVALID")
        self.assertEqual(result.candidate_assignments, ())
        self.assertEqual(result.assignment_variable_count, 0)
        self.assertEqual(result.incharge_variable_count, 0)
        self.assertEqual(result.locked_assignment_constraint_count, 0)
        self.assertEqual(result.locked_assignment_issues, ())
        self.assertEqual(result.approved_leave_constraint_count, 0)
        self.assertEqual(result.approved_leave_issues, ())
        self.assertEqual(result.staffing_constraint_count, 0)
        self.assertEqual(result.coverage_constraint_count, 0)
        self.assertEqual(result.one_shift_per_day_constraint_count, 0)
        self.assertIn("NO_COVERAGE_WINDOWS", {issue.code for issue in result.coverage_issues})
        self.assertIsNone(result.objective_value)
        self.assertEqual(result.solve_time_seconds, 0.0)
        self.assertGreater(result.variable_count, 0)
        self.assertIn("not run", result.notices[1])

    def test_assignment_model_creates_x_and_incharge_variables_from_snapshot(self) -> None:
        staff = (
            SchedulerStaff(10, "RN001", "RN One", "RN", True),
            SchedulerStaff(11, "RN002", "RN Two", "RN", False),
        )
        shifts = (
            SchedulerShift(1, "AM", time(7), time(15), 480, False),
            SchedulerShift(2, "PM", time(15), time(23), 480, False),
        )
        snapshot = SchedulerSnapshot(1, 2026, 2, staff, shifts, (), {}, (), (), (), (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        expected = 2 * 28 * 2
        self.assertEqual(len(assignment_model.assignments), expected)
        self.assertEqual(len(assignment_model.incharge_assignments), expected)
        key = (10, date(2026, 2, 1), 1)
        self.assertIn(key, assignment_model.assignments)
        self.assertIn(key, assignment_model.incharge_assignments)
        self.assertEqual(len(assignment_model.model.Proto().variables), expected * 2 + 10)

    def test_head_nurse_can_only_be_assigned_am_or_d_by_ai(self) -> None:
        staff = (
            SchedulerStaff(10, "RN001", "Head Nurse", "RN", True, True),
            SchedulerStaff(11, "RN002", "RN Two", "RN", True),
        )
        shifts = (
            SchedulerShift(1, "AM", time(7), time(15), 480, False),
            SchedulerShift(2, "D", time(7), time(19), 720, False),
            SchedulerShift(3, "PM", time(15), time(23), 480, False),
            SchedulerShift(4, "N", time(23), time(7), 480, True),
            SchedulerShift(5, "DE", time(15), time(23), 480, False),
        )
        snapshot = SchedulerSnapshot(1, 2026, 2, staff, shifts, (), {}, (), (), (), (), ())
        for prohibited_shift_id in (3, 4, 5):
            assignment_model = AssignmentModelBuilder().build(snapshot)
            assignment_model.model.Add(assignment_model.assignments[(10, date(2026, 2, 1), prohibited_shift_id)] == 1)
            self.assertEqual(cp_model.CpSolver().Solve(assignment_model.model), cp_model.INFEASIBLE)

        allowed_model = AssignmentModelBuilder().build(snapshot)
        allowed_model.model.Add(allowed_model.assignments[(10, date(2026, 2, 1), 2)] == 1)
        allowed_model.model.Add(allowed_model.assignments[(11, date(2026, 2, 1), 5)] == 1)
        self.assertIn(cp_model.CpSolver().Solve(allowed_model.model), (cp_model.OPTIMAL, cp_model.FEASIBLE))

    def test_assignment_model_fixes_valid_locked_assignment(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        lock = LockedAssignment(10, 1, date(2026, 2, 1))
        snapshot = SchedulerSnapshot(1, 2026, 2, staff, shifts, (), {}, (), (), (), (lock,), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        self.assertEqual(assignment_model.locked_assignment_constraint_count, 1)
        self.assertEqual(assignment_model.locked_assignment_issues, ())
        self.assertEqual(assignment_model.incharge_qualification_constraint_count, 28)
        self.assertEqual(len(assignment_model.model.Proto().constraints), 63)

    def test_assignment_model_reports_conflicting_or_unknown_locks(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True),)
        shifts = (
            SchedulerShift(1, "AM", time(7), time(15), 480, False),
            SchedulerShift(2, "PM", time(15), time(23), 480, False),
        )
        locks = (
            LockedAssignment(10, 1, date(2026, 2, 1)),
            LockedAssignment(10, 2, date(2026, 2, 1)),
            LockedAssignment(99, 1, date(2026, 2, 1)),
        )
        snapshot = SchedulerSnapshot(1, 2026, 2, staff, shifts, (), {}, (), (), (), locks, ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        codes = {issue.code for issue in assignment_model.locked_assignment_issues}
        self.assertIn("LOCKED_ASSIGNMENT_CONFLICT", codes)
        self.assertIn("LOCKED_ASSIGNMENT_MULTIPLE_SHIFTS_PER_DAY", codes)
        self.assertIn("LOCKED_ASSIGNMENT_OUTSIDE_MODEL", codes)
        self.assertEqual(assignment_model.locked_assignment_constraint_count, 0)

    def test_all_day_unavailable_blocks_every_shift(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True),)
        shifts = (
            SchedulerShift(1, "AM", time(7), time(15), 480, False),
            SchedulerShift(2, "PM", time(15), time(23), 480, False),
            SchedulerShift(3, "N", time(23), time(7), 480, True),
            SchedulerShift(4, "D", time(7), time(19), 720, False),
            SchedulerShift(5, "DE", time(19), time(7), 720, True),
        )
        unavailable = SchedulerAvailability(10, date(2026, 8, 10), "unavailable")
        snapshot = SchedulerSnapshot(1, 2026, 8, staff, shifts, (), {}, (), (unavailable,), (), (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        self.assertEqual(assignment_model.availability_constraint_count, 5)
        self.assertIn("AVAILABILITY_ALL_DAY", {issue.code for issue in assignment_model.availability_issues})
        for shift in shifts:
            assignment_model.model.Add(assignment_model.assignments[(10, date(2026, 8, 10), shift.id)] == 1)
            self.assertEqual(cp_model.CpSolver().Solve(assignment_model.model), cp_model.INFEASIBLE)

    def test_single_shift_unavailable_blocks_only_that_shift(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False), SchedulerShift(2, "N", time(23), time(7), 480, True))
        unavailable = SchedulerAvailability(10, date(2026, 8, 10), "unavailable", 2)
        snapshot = SchedulerSnapshot(1, 2026, 8, staff, shifts, (), {}, (), (unavailable,), (), (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        self.assertEqual(assignment_model.availability_constraint_count, 1)
        assignment_model.model.Add(assignment_model.assignments[(10, date(2026, 8, 10), 2)] == 1)
        self.assertEqual(cp_model.CpSolver().Solve(assignment_model.model), cp_model.INFEASIBLE)

    def test_d_assignment_requires_de_continuation(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True), SchedulerStaff(11, "RN002", "RN Two", "RN", False))
        shifts = (SchedulerShift(1, "D", time(7), time(19), 720, False), SchedulerShift(2, "DE", time(19), time(7), 720, True))
        snapshot = SchedulerSnapshot(1, 2026, 8, staff, shifts, (), {"REST_AFTER_NIGHT": 8}, (), (), (), (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        work_date = date(2026, 8, 10)
        assignment_model.model.Add(assignment_model.assignments[(10, work_date, 1)] == 1)
        assignment_model.model.Add(assignment_model.assignments[(11, work_date, 2)] == 0)
        assignment_model.model.Add(assignment_model.assignments[(10, work_date, 2)] == 0)
        self.assertEqual(cp_model.CpSolver().Solve(assignment_model.model), cp_model.INFEASIBLE)

    def test_pilot_dataset_validation_accepts_all_and_rejects_unknown_shift(self) -> None:
        rows = {
            "staff": [{"employee_code": "RN001", "position": "RN"}],
            "shift": [{"shift_code": "AM"}],
            "icu_rules": [{"rule_key": "MIN_RN", "rule_value": 1}],
            "leave": [],
            "availability": [{"employee_code": "RN001", "unavailable_date": "2026-08-10", "unavailable_shift": "ALL", "status": "unavailable"}],
            "preferences": [{"employee_code": "RN001", "preference_date": "2026-08-10", "shift_code": "AM", "preference": "prefer", "weight": 5}],
        }
        self.assertTrue(validate_dataset(PilotDataset(rows), 2026, 8).valid)
        rows["availability"][0]["unavailable_shift"] = "BAD"
        self.assertIn("unavailable_shift", {issue.field for issue in validate_dataset(PilotDataset(rows), 2026, 8).issues})

    def test_approved_leave_fixes_every_shift_to_zero(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True),)
        shifts = (
            SchedulerShift(1, "AM", time(7), time(15), 480, False),
            SchedulerShift(2, "PM", time(15), time(23), 480, False),
            SchedulerShift(3, "N", time(23), time(7), 480, True),
        )
        leave = SchedulerLeave(10, date(2026, 8, 10), date(2026, 8, 10), "approved")
        snapshot = SchedulerSnapshot(1, 2026, 8, staff, shifts, (), {}, (leave,), (), (), (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        self.assertEqual(assignment_model.approved_leave_constraint_count, 3)
        self.assertEqual(assignment_model.approved_leave_issues, ())
        constraints = assignment_model.model.Proto().constraints
        for shift in shifts:
            variable = assignment_model.assignments[(10, date(2026, 8, 10), shift.id)]
            self.assertTrue(any(
                list(constraint.linear.vars) == [variable.Index()]
                and list(constraint.linear.coeffs) == [1]
                and list(constraint.linear.domain) == [0, 0]
                for constraint in constraints
            ))

    def test_pending_leave_does_not_create_hard_constraint(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        leave = SchedulerLeave(10, date(2026, 8, 10), date(2026, 8, 10), "pending")
        snapshot = SchedulerSnapshot(1, 2026, 8, staff, shifts, (), {}, (leave,), (), (), (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        self.assertEqual(assignment_model.approved_leave_constraint_count, 0)
        self.assertEqual(assignment_model.approved_leave_issues, ())

    def test_approved_leave_outside_month_reports_issue(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        leave = SchedulerLeave(10, date(2026, 9, 10), date(2026, 9, 10), "approved")
        snapshot = SchedulerSnapshot(1, 2026, 8, staff, shifts, (), {}, (leave,), (), (), (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        self.assertEqual(assignment_model.approved_leave_constraint_count, 0)
        self.assertIn("APPROVED_LEAVE_OUTSIDE_SNAPSHOT", {issue.code for issue in assignment_model.approved_leave_issues})

    def test_leave_prevalidation_reports_inactive_staff_and_invalid_range(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        leaves = (
            SchedulerLeave(99, date(2026, 8, 10), date(2026, 8, 10), "approved"),
            SchedulerLeave(10, date(2026, 8, 11), date(2026, 8, 10), "approved"),
        )
        snapshot = SchedulerSnapshot(1, 2026, 8, staff, shifts, (), {}, leaves, (), (), (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        codes = {issue.code for issue in assignment_model.approved_leave_issues}
        self.assertIn("APPROVED_LEAVE_STAFF_NOT_ELIGIBLE", codes)
        self.assertIn("INVALID_LEAVE_RANGE", codes)

    def test_staffing_and_real_time_coverage_constraints_are_added(self) -> None:
        staff = (
            SchedulerStaff(10, "RN001", "RN One", "RN", True),
            SchedulerStaff(20, "PN001", "PN One", "PN", False),
        )
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        window = SchedulerCoverageWindow("07:00-15:00", time(7), time(15), False, 3, 4, 1, 1, (1,))
        rules = {"MIN_RN": 1, "MAX_RN": 1, "MIN_SUPPORT": 1}
        snapshot = SchedulerSnapshot(1, 2026, 2, staff, shifts, (window,), rules, (), (), (), (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        self.assertEqual(assignment_model.coverage_issues, ())
        self.assertEqual(assignment_model.coverage_constraint_count, 28)
        self.assertEqual(assignment_model.staffing_constraint_count, 84)
        self.assertEqual(assignment_model.senior_rn_constraint_count, 28)
        self.assertEqual(assignment_model.incharge_qualification_constraint_count, 84)
        self.assertEqual(assignment_model.incharge_coverage_constraint_count, 28)
        self.assertEqual(len(assignment_model.model.Proto().constraints), 290)
        rn_variable = assignment_model.assignments[(10, date(2026, 2, 1), 1)]
        rn_domains = [list(item.linear.domain) for item in assignment_model.model.Proto().constraints if list(item.linear.vars) == [rn_variable.Index()]]
        self.assertIn([1, 9223372036854775807], rn_domains)
        self.assertIn([-9223372036854775808, 1], rn_domains)

    def test_coverage_prevalidation_reports_missing_rules_and_invalid_mapping(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        invalid_window = SchedulerCoverageWindow("07:00-15:00", time(7), time(15), False, 3, 4, 1, 1, (99,))
        missing_rules = SchedulerSnapshot(1, 2026, 2, staff, shifts, (invalid_window,), {}, (), (), (), (), ())
        missing_result = AssignmentModelBuilder().build(missing_rules)
        missing_codes = {issue.code for issue in missing_result.coverage_issues}
        self.assertIn("MISSING_ICU_RULE", missing_codes)
        self.assertEqual(missing_result.staffing_constraint_count, 0)

        invalid_mapping = SchedulerSnapshot(1, 2026, 2, staff, shifts, (invalid_window,), {"MIN_RN": 1, "MAX_RN": 2, "MIN_SUPPORT": 0}, (), (), (), (), ())
        mapping_result = AssignmentModelBuilder().build(invalid_mapping)
        self.assertIn("INVALID_COVERAGE_SHIFT_MAPPING", {issue.code for issue in mapping_result.coverage_issues})
        self.assertEqual(mapping_result.coverage_constraint_count, 0)

    def test_senior_rn_and_incharge_constraints_cover_each_window(self) -> None:
        staff = (
            SchedulerStaff(10, "RN001", "Senior RN", "RN", True),
            SchedulerStaff(11, "RN002", "Junior RN", "RN", False),
        )
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        window = SchedulerCoverageWindow("07:00-15:00", time(7), time(15), False, 1, 2, 0, 1, (1,))
        snapshot = SchedulerSnapshot(1, 2026, 2, staff, shifts, (window,), {"REST_AFTER_NIGHT": 8}, (), (), (), (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        self.assertEqual(assignment_model.senior_rn_constraint_count, 28)
        self.assertEqual(assignment_model.incharge_coverage_constraint_count, 28)
        self.assertEqual(assignment_model.incharge_qualification_constraint_count, 84)
        self.assertEqual(assignment_model.senior_incharge_issues, ())
        junior_incharge = assignment_model.incharge_assignments[(11, date(2026, 2, 1), 1)]
        self.assertTrue(any(
            list(constraint.linear.vars) == [junior_incharge.Index()]
            and list(constraint.linear.domain) == [0, 0]
            for constraint in assignment_model.model.Proto().constraints
        ))

    def test_senior_incharge_prevalidation_reports_missing_senior_staff(self) -> None:
        staff = (SchedulerStaff(11, "RN002", "Junior RN", "RN", False),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        window = SchedulerCoverageWindow("07:00-15:00", time(7), time(15), False, 1, 2, 0, 1, (1,))
        snapshot = SchedulerSnapshot(1, 2026, 2, staff, shifts, (window,), {"REST_AFTER_NIGHT": 8}, (), (), (), (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        self.assertIn("NO_SENIOR_RN_ELIGIBLE_STAFF", {issue.code for issue in assignment_model.senior_incharge_issues})

    def test_rest_overlap_and_multiple_shift_compatibility_constraints(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "Senior RN", "RN", True),)
        shifts = (
            SchedulerShift(1, "AM", time(7), time(15), 480, False),
            SchedulerShift(2, "PM", time(15), time(23), 480, False),
            SchedulerShift(3, "N", time(23), time(7), 480, True),
            SchedulerShift(4, "D", time(7), time(19), 720, False),
            SchedulerShift(5, "DE", time(19), time(7), 720, True),
        )
        snapshot = SchedulerSnapshot(1, 2026, 2, staff, shifts, (), {"REST_AFTER_NIGHT": 8}, (), (), (), (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        self.assertEqual(assignment_model.overlap_constraint_count, 112)
        self.assertEqual(assignment_model.multiple_shift_constraint_count, 112)
        self.assertEqual(assignment_model.one_shift_per_day_constraint_count, 28)
        self.assertEqual(assignment_model.rest_constraint_count, 108)
        self.assertEqual(assignment_model.rest_overlap_issues, ())

    def test_one_shift_per_day_makes_adjacent_am_pm_and_pm_n_infeasible(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "Senior RN", "RN", True),)
        shifts = (
            SchedulerShift(1, "AM", time(7), time(15), 480, False),
            SchedulerShift(2, "PM", time(15), time(23), 480, False),
            SchedulerShift(3, "N", time(23), time(7), 480, True),
        )
        snapshot = SchedulerSnapshot(1, 2026, 2, staff, shifts, (), {"REST_AFTER_NIGHT": 8}, (), (), (), (), ())
        for first_shift, second_shift in ((1, 2), (2, 3)):
            assignment_model = AssignmentModelBuilder().build(snapshot)
            self.assertEqual(assignment_model.one_shift_per_day_constraint_count, 28)
            assignment_model.model.Add(assignment_model.assignments[(10, date(2026, 2, 1), first_shift)] == 1)
            assignment_model.model.Add(assignment_model.assignments[(10, date(2026, 2, 1), second_shift)] == 1)
            self.assertEqual(cp_model.CpSolver().Solve(assignment_model.model), cp_model.INFEASIBLE)

    def test_rest_prevalidation_reports_missing_rule_and_incomplete_timing(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "Senior RN", "RN", True),)
        shifts = (SchedulerShift(1, "AM", None, time(15), None, False),)
        snapshot = SchedulerSnapshot(1, 2026, 2, staff, shifts, (), {}, (), (), (), (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        codes = {issue.code for issue in assignment_model.rest_overlap_issues}
        self.assertIn("MISSING_ICU_RULE", codes)
        self.assertIn("INCOMPLETE_SHIFT_TIMING", codes)
        self.assertEqual(assignment_model.rest_constraint_count, 0)

    def test_fairness_model_calculates_shift_count_hours_and_workload_score(self) -> None:
        staff = (
            SchedulerStaff(10, "RN001", "RN One", "RN", True),
            SchedulerStaff(11, "RN002", "RN Two", "RN", True),
        )
        shifts = (
            SchedulerShift(1, "AM", time(7), time(15), 480, False),
            SchedulerShift(2, "D", time(7), time(19), 720, False),
        )
        snapshot = SchedulerSnapshot(1, 2026, 2, staff, shifts, (), {"REST_AFTER_NIGHT": 8}, (), (), (), (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        fairness = assignment_model.fairness
        self.assertEqual(len(fairness.assigned_shift_counts), 2)
        self.assertEqual(len(fairness.working_minutes), 2)
        self.assertEqual(len(fairness.workload_scores), 2)
        self.assertEqual(len(fairness.pairwise_imbalances), 1)
        self.assertEqual(fairness.fairness_constraint_count, 8)
        self.assertEqual(fairness.assigned_shift_counts[10].Name(), "assigned_shift_count_s10")
        self.assertEqual(fairness.working_minutes[10].Name(), "working_minutes_s10")
        self.assertEqual(fairness.workload_scores[10].Name(), "workload_score_s10")
        self.assertEqual(fairness.total_workload_imbalance.Name(), "total_workload_imbalance")

    def test_fairness_prevalidation_reports_unknown_shift_weight(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True),)
        shifts = (SchedulerShift(99, "CUSTOM", time(7), time(15), 480, False),)
        snapshot = SchedulerSnapshot(1, 2026, 2, staff, shifts, (), {"REST_AFTER_NIGHT": 8}, (), (), (), (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        self.assertIn("UNKNOWN_WORKLOAD_SHIFT_WEIGHT", {issue.code for issue in assignment_model.fairness.issues})

    def test_prefer_and_avoid_create_soft_penalty_terms_without_fixing_assignment(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True),)
        shifts = (
            SchedulerShift(1, "AM", time(7), time(15), 480, False),
            SchedulerShift(2, "PM", time(15), time(23), 480, False),
        )
        preferences = (
            SchedulerPreference(10, date(2026, 2, 10), 1, "prefer", 3),
            SchedulerPreference(10, date(2026, 2, 10), 2, "avoid", 2),
        )
        snapshot = SchedulerSnapshot(1, 2026, 2, staff, shifts, (), {"REST_AFTER_NIGHT": 8}, (), (), preferences, (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        preference_model = assignment_model.preferences
        self.assertEqual(len(preference_model.penalty_variables), 2)
        self.assertEqual(preference_model.score_term_count, 2)
        self.assertEqual(preference_model.constraint_count, 3)
        self.assertEqual(preference_model.issues, ())
        self.assertEqual(preference_model.preference_penalty_score.Name(), "preference_penalty_score")
        assignment = assignment_model.assignments[(10, date(2026, 2, 10), 1)]
        self.assertFalse(any(
            list(constraint.linear.vars) == [assignment.Index()]
            and list(constraint.linear.domain) in ([0, 0], [1, 1])
            for constraint in assignment_model.model.Proto().constraints
        ))

    def test_priority_five_avoid_blocks_every_shift_for_the_day(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True),)
        shifts = (
            SchedulerShift(1, "AM", time(7), time(15), 480, False),
            SchedulerShift(2, "PM", time(15), time(23), 480, False),
        )
        preferences = (SchedulerPreference(10, date(2026, 2, 10), None, "avoid", 5),)
        snapshot = SchedulerSnapshot(1, 2026, 2, staff, shifts, (), {"REST_AFTER_NIGHT": 8}, (), (), preferences, (), ())

        assignment_model = AssignmentModelBuilder().build(snapshot)

        self.assertEqual(assignment_model.preferences.hard_constraint_count, 2)
        self.assertEqual(assignment_model.preferences.score_term_count, 0)
        for shift_id in (1, 2):
            constrained_model = AssignmentModelBuilder().build(snapshot)
            constrained_model.model.Add(constrained_model.assignments[(10, date(2026, 2, 10), shift_id)] == 1)
            self.assertEqual(cp_model.CpSolver().Solve(constrained_model.model), cp_model.INFEASIBLE)

    def test_manual_validator_blocks_priority_five_avoid_preference(self) -> None:
        assignment = Assignment(1, 10, "RN One", "RN", True, date(2026, 8, 1), 1, "AM", time(7), time(15), False, True, False, None, None)
        conflicts = validate_context(
            [assignment], [], {}, [], [SoftPreference(10, date(2026, 8, 1), None, "avoid", 5)], 2026, 8,
        )
        self.assertIn("UNAVAILABLE_PREFERENCE", {item.code for item in conflicts})

    def test_preference_prevalidation_reports_outside_and_conflicting_input(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        preferences = (
            SchedulerPreference(10, date(2026, 2, 10), 1, "prefer", 1),
            SchedulerPreference(10, date(2026, 2, 10), 1, "avoid", 1),
            SchedulerPreference(10, date(2026, 3, 1), 1, "prefer", 1),
        )
        snapshot = SchedulerSnapshot(1, 2026, 2, staff, shifts, (), {"REST_AFTER_NIGHT": 8}, (), (), preferences, (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        codes = {issue.code for issue in assignment_model.preferences.issues}
        self.assertIn("CONFLICTING_SHIFT_PREFERENCES", codes)
        self.assertIn("PREFERENCE_OUTSIDE_SNAPSHOT", codes)
        self.assertEqual(len(assignment_model.preferences.penalty_variables), 0)

    def test_ot_model_prepares_minutes_and_penalty_without_hard_assignment_rule(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        rules = {"REST_AFTER_NIGHT": 8, "MONTHLY_HOURS": 160, "OT_THRESHOLD": 168}
        snapshot = SchedulerSnapshot(1, 2026, 2, staff, shifts, (), rules, (), (), (), (), ())
        assignment_model = AssignmentModelBuilder().build(snapshot)
        overtime = assignment_model.overtime
        self.assertEqual(len(overtime.ot_minutes), 1)
        self.assertEqual(overtime.penalty_term_count, 1)
        self.assertEqual(overtime.constraint_count, 2)
        self.assertEqual(overtime.diagnostics, ())
        self.assertEqual(overtime.ot_minutes[10].Name(), "ot_minutes_s10")
        self.assertIsNotNone(overtime.ot_penalty_score)
        self.assertEqual(overtime.ot_penalty_score.Name(), "ot_penalty_score")
        assignment = assignment_model.assignments[(10, date(2026, 2, 10), 1)]
        self.assertFalse(any(
            list(constraint.linear.vars) == [assignment.Index()]
            and list(constraint.linear.domain) in ([0, 0], [1, 1])
            for constraint in assignment_model.model.Proto().constraints
        ))

    def test_ot_prevalidation_reports_missing_or_invalid_rules(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        missing = SchedulerSnapshot(1, 2026, 2, staff, shifts, (), {"REST_AFTER_NIGHT": 8}, (), (), (), (), ())
        missing_model = AssignmentModelBuilder().build(missing)
        self.assertIn("MISSING_ICU_RULE", {issue.code for issue in missing_model.overtime.diagnostics})
        self.assertEqual(len(missing_model.overtime.ot_minutes), 0)

        invalid = SchedulerSnapshot(1, 2026, 2, staff, shifts, (), {"REST_AFTER_NIGHT": 8, "MONTHLY_HOURS": 168, "OT_THRESHOLD": 160}, (), (), (), (), ())
        invalid_model = AssignmentModelBuilder().build(invalid)
        self.assertIn("INVALID_OT_RULES", {issue.code for issue in invalid_model.overtime.diagnostics})

    def test_objective_composition_prepares_weighted_cost_without_minimize_or_solve(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        snapshot = SchedulerSnapshot(
            1, 2026, 2, staff, shifts, (),
            {"MIN_RN": 0, "MAX_RN": 1, "MIN_SUPPORT": 0, "REST_AFTER_NIGHT": 8, "MONTHLY_HOURS": 160, "OT_THRESHOLD": 168},
            (), (), (SchedulerPreference(10, date(2026, 2, 1), 1, "avoid", 3),), (), (),
        )
        assignment_model = AssignmentModelBuilder().build(snapshot)
        objective = assignment_model.objective

        self.assertEqual(objective.total_objective_cost.Name(), "total_objective_cost")
        self.assertEqual(objective.total_objective_terms, 3)
        self.assertEqual({item.key: item.weight for item in objective.components}, {"fairness": 20, "preference": 10, "ot": 10})
        self.assertEqual(objective.constraint_count, 1)

    def test_objective_dry_run_reports_components_and_weights(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "RN One", "RN", True),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        snapshot = SchedulerSnapshot(
            1, 2026, 2, staff, shifts, (),
            {"MIN_RN": 0, "MAX_RN": 1, "MIN_SUPPORT": 0, "REST_AFTER_NIGHT": 8, "MONTHLY_HOURS": 160, "OT_THRESHOLD": 168},
            (), (), (), (), (),
        )
        result = CpSatSchedulerSolver().dry_run(snapshot)

        self.assertEqual(result.objective_weights, {"fairness": 20, "preference": 10, "ot": 10})
        self.assertEqual(result.total_objective_terms, 3)
        self.assertEqual({item[0] for item in result.objective_components}, {"fairness", "preference", "ot"})

    def test_solver_dry_run_solves_valid_model_without_writing_assignments(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "Senior RN", "RN", True),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        windows = (SchedulerCoverageWindow("07-15", time(7), time(15), False, 0, 1, 0, 0, (1,)),)
        snapshot = SchedulerSnapshot(
            1, 2026, 2, staff, shifts, windows,
            {"MIN_RN": 0, "MAX_RN": 1, "MIN_SUPPORT": 0, "REST_AFTER_NIGHT": 8, "MONTHLY_HOURS": 160, "OT_THRESHOLD": 168},
            (), (), (), (), (),
        )

        result = CpSatSchedulerSolver().dry_run(snapshot)

        self.assertIn(result.solver_status, {"OPTIMAL", "FEASIBLE"})
        self.assertIsNotNone(result.objective_value)
        self.assertGreater(result.solve_time_seconds, 0)
        self.assertGreater(result.variable_count, 0)
        self.assertGreater(result.constraint_count, 0)
        self.assertEqual(result.candidate_assignments, ())
        self.assertIn("no schedule preview, database write, or publish", result.notices[1])

    def test_solver_dry_run_reports_infeasible_rn_capacity(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "Senior RN", "RN", True),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        windows = (SchedulerCoverageWindow("07-15", time(7), time(15), False, 0, 2, 0, 0, (1,)),)
        snapshot = SchedulerSnapshot(
            1, 2026, 2, staff, shifts, windows,
            {"MIN_RN": 2, "MAX_RN": 2, "MIN_SUPPORT": 0, "REST_AFTER_NIGHT": 8, "MONTHLY_HOURS": 160, "OT_THRESHOLD": 168},
            (), (), (), (), (),
        )

        result = CpSatSchedulerSolver().dry_run(snapshot)

        self.assertEqual(result.solver_status, "INFEASIBLE")
        self.assertIsNone(result.objective_value)
        self.assertIn("RN_COVERAGE_CAPACITY_SHORTAGE", {item.code for item in result.diagnostics})
        self.assertIn("SOLVER_INFEASIBLE", {item.code for item in result.diagnostics})

    def test_solver_preview_extracts_read_only_assignments_and_summary(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "Senior RN", "RN", True),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        windows = (SchedulerCoverageWindow("07-15", time(7), time(15), False, 0, 1, 0, 0, (1,)),)
        snapshot = SchedulerSnapshot(
            1, 2026, 2, staff, shifts, windows,
            {"MIN_RN": 0, "MAX_RN": 1, "MIN_SUPPORT": 0, "REST_AFTER_NIGHT": 8, "MONTHLY_HOURS": 160, "OT_THRESHOLD": 168},
            (), (), (), (), (),
        )

        result = CpSatSchedulerSolver().preview(snapshot)

        self.assertIn(result.solver_status, {"OPTIMAL", "FEASIBLE"})
        self.assertEqual(len(result.assignments), 28)
        self.assertTrue(all(item.staff_id == 10 and item.shift_code == "AM" and item.is_incharge for item in result.assignments))
        self.assertIsNotNone(result.summary)
        self.assertEqual(result.summary.total_assignments, 28)
        self.assertEqual(result.summary.total_staff, 1)
        self.assertEqual(result.summary.staff_workloads[0].assigned_shift_count, 28)
        self.assertEqual(result.summary.staff_workloads[0].working_minutes, 28 * 480)
        # This synthetic one-person month assigns 224 hours against a 168-hour
        # OT threshold, so fairness/preference are perfect but the OT component is 0.
        self.assertEqual(result.summary.quality_score, 7.5)
        self.assertEqual(result.summary.fairness_score, 10.0)
        self.assertEqual(result.summary.preference_score, 10.0)
        self.assertEqual(result.summary.ot_score, 0.0)
        self.assertIn("read-only", result.notices[1])

    def test_solver_preview_has_no_assignments_when_infeasible(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "Senior RN", "RN", True),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        windows = (SchedulerCoverageWindow("07-15", time(7), time(15), False, 0, 2, 0, 0, (1,)),)
        snapshot = SchedulerSnapshot(
            1, 2026, 2, staff, shifts, windows,
            {"MIN_RN": 2, "MAX_RN": 2, "MIN_SUPPORT": 0, "REST_AFTER_NIGHT": 8, "MONTHLY_HOURS": 160, "OT_THRESHOLD": 168},
            (), (), (), (), (),
        )

        result = CpSatSchedulerSolver().preview(snapshot)

        self.assertEqual(result.solver_status, "INFEASIBLE")
        self.assertEqual(result.assignments, ())
        self.assertIsNone(result.summary)

    def test_ai_preview_validation_reuses_manual_icu_validator(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "Senior RN", "RN", True),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        windows = (SchedulerCoverageWindow("07-15", time(7), time(15), False, 1, 1, 0, 1, (1,)),)
        snapshot = SchedulerSnapshot(
            1, 2026, 2, staff, shifts, windows,
            {"MIN_RN": 1, "MAX_RN": 1, "MIN_SUPPORT": 0, "REST_AFTER_NIGHT": 8},
            (), (), (), (), (),
        )

        conflicts = validate_preview(snapshot, tuple(PreviewAssignmentInput(10, 1, date(2026, 2, day), True) for day in range(1, 29)))

        self.assertEqual(conflicts, [])

    def test_ai_preview_validation_reports_manual_format_conflicts_without_writing(self) -> None:
        staff = (SchedulerStaff(10, "RN001", "Senior RN", "RN", True),)
        shifts = (SchedulerShift(1, "AM", time(7), time(15), 480, False),)
        windows = (SchedulerCoverageWindow("07-15", time(7), time(15), False, 1, 1, 0, 1, (1,)),)
        snapshot = SchedulerSnapshot(
            1, 2026, 2, staff, shifts, windows,
            {"MIN_RN": 1, "MAX_RN": 1, "MIN_SUPPORT": 0, "REST_AFTER_NIGHT": 8},
            (), (), (SchedulerPreference(10, date(2026, 2, 1), 1, "avoid", 3),), (), (),
        )

        conflicts = validate_preview(snapshot, tuple(PreviewAssignmentInput(10, 1, date(2026, 2, day), True) for day in range(1, 29)) + (PreviewAssignmentInput(99, 1, date(2026, 2, 1), False),))

        codes = {item.code for item in conflicts}
        self.assertIn("SOFT_PREFERENCE_AVOID", codes)
        self.assertIn("PREVIEW_ASSIGNMENT_OUTSIDE_SNAPSHOT", codes)

    def test_ai_draft_approval_requires_validation_then_records_head_nurse_approval(self) -> None:
        draft = AiScheduleDraft(id=1, status="GENERATED", approval_status="not_submitted", validation_status="passed")
        submitter = User(id=10, username="admin", role="admin", password_hash="x", is_active=True)
        head_nurse = User(id=11, username="head", role="head_nurse", password_hash="x", is_active=True)

        submit_for_approval(draft, submitter)
        self.assertEqual((draft.status, draft.approval_status, draft.submitted_by_user_id), ("VALIDATED", "pending", 10))
        approve_draft(draft, head_nurse)
        self.assertEqual((draft.status, draft.approval_status, draft.approved_by_user_id), ("APPROVED", "approved", 11))
        self.assertIsNotNone(draft.approved_at)

    def test_ai_draft_rejection_and_invalid_transitions_are_blocked(self) -> None:
        failed = AiScheduleDraft(id=1, status="GENERATED", approval_status="not_submitted", validation_status="failed")
        actor = User(id=10, username="head", role="head_nurse", password_hash="x", is_active=True)
        with self.assertRaises(AiDraftApprovalError):
            submit_for_approval(failed, actor)

        pending = AiScheduleDraft(id=2, status="VALIDATED", approval_status="pending", validation_status="passed")
        reject_draft(pending, actor, "Need to review night coverage")
        self.assertEqual((pending.status, pending.approval_status, pending.rejected_by_user_id), ("REJECTED", "rejected", 10))
        self.assertEqual(pending.rejection_reason, "Need to review night coverage")
        with self.assertRaises(AiDraftApprovalError):
            approve_draft(pending, actor)

    def test_ai_draft_conversion_requires_approved_and_representable_assignments(self) -> None:
        pending = AiScheduleDraft(id=1, status="VALIDATED", approval_status="pending", converted_schedule_id=None)
        with self.assertRaises(AiDraftConversionError):
            validate_conversion_eligibility(pending)

        duplicate = AiScheduleDraft(id=2, status="APPROVED", approval_status="approved", converted_schedule_id=None)
        duplicate.details = [
            AiScheduleDraftDetail(staff_id=10, shift_type_id=1, work_date=date(2026, 2, 1), is_incharge=False),
            AiScheduleDraftDetail(staff_id=10, shift_type_id=2, work_date=date(2026, 2, 1), is_incharge=False),
        ]
        with self.assertRaises(AiDraftConversionError):
            validate_conversion_eligibility(duplicate)

        approved = AiScheduleDraft(id=3, status="APPROVED", approval_status="approved", converted_schedule_id=None)
        approved.details = [AiScheduleDraftDetail(staff_id=10, shift_type_id=1, work_date=date(2026, 2, 1), is_incharge=True)]
        validate_conversion_eligibility(approved)


if __name__ == "__main__":
    unittest.main()
