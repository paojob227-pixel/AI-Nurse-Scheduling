import unittest
from dataclasses import asdict
from datetime import date, time

from app.scheduler.contracts import SchedulerPreference, SchedulerShift, SchedulerSnapshot, SchedulerStaff
from app.scheduler.explanation import build_schedule_explanation
from app.scheduler.explanation.fairness_report import build_fairness_report
from app.scheduler.explanation.night_report import build_night_report
from app.scheduler.explanation.preference_report import build_preference_report
from app.schemas import SchedulerPreviewExplanationOut
from app.services.ai_preview_validation import PreviewAssignmentInput


class SchedulerExplanationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = SchedulerSnapshot(
            1, 2026, 8,
            (
                SchedulerStaff(1, "RN001", "RN One", "RN", True),
                SchedulerStaff(2, "RN002", "RN Two", "RN", False),
                SchedulerStaff(3, "PN001", "PN One", "PN", False),
            ),
            (
                SchedulerShift(1, "AM", time(7), time(15), 480, False),
                SchedulerShift(2, "N", time(23), time(7), 480, True),
            ),
            (), {"OT_THRESHOLD": 8}, (), (),
            (
                SchedulerPreference(1, date(2026, 8, 1), 2, "prefer", 5),
                SchedulerPreference(2, date(2026, 8, 1), 2, "avoid", 3),
                SchedulerPreference(3, date(2026, 8, 1), 1, "prefer", 2),
            ), (), (),
        )
        self.assignments = (
            PreviewAssignmentInput(1, 2, date(2026, 8, 1), True),
            PreviewAssignmentInput(2, 2, date(2026, 8, 1), False),
            PreviewAssignmentInput(3, 1, date(2026, 8, 1), False),
        )

    def test_fairness_report_calculates_distribution_and_status(self) -> None:
        report = build_fairness_report({1: 480, 2: 480, 3: 960})
        self.assertEqual(report.minimum_workload_minutes, 480)
        self.assertEqual(report.maximum_workload_minutes, 960)
        self.assertEqual(report.workload_difference_minutes, 480)
        self.assertEqual(report.status, "IMBALANCED")

    def test_night_distribution_reports_each_rn_without_creating_a_constraint(self) -> None:
        keys = {(item.staff_id, item.work_date, item.shift_type_id) for item in self.assignments}
        report = build_night_report(self.snapshot, keys)
        self.assertEqual(report.total_night_assignments, 2)
        self.assertEqual(report.mean_nights_per_rn, 1.0)
        self.assertEqual(report.status, "GOOD")
        self.assertEqual([(item.employee_code, item.night_count) for item in report.staff], [("RN001", 1), ("RN002", 1)])

    def test_preference_report_separates_prefer_satisfaction_from_avoid_violation(self) -> None:
        keys = {(item.staff_id, item.work_date, item.shift_type_id) for item in self.assignments}
        report = build_preference_report(self.snapshot, keys)
        self.assertEqual(report.prefer_total, 2)
        self.assertEqual(report.prefer_satisfied, 2)
        self.assertEqual(report.prefer_satisfaction_percent, 100.0)
        self.assertEqual(report.avoid_violations, 1)

    def test_staff_explanation_exposes_workload_nights_ot_and_preference_tradeoffs(self) -> None:
        explanation = build_schedule_explanation(self.snapshot, self.assignments)
        rn_one = explanation.staff_explanations[0]
        self.assertEqual(explanation.summary.total_assignments, 3)
        self.assertEqual(rn_one.shift_counts, {"N": 1})
        self.assertEqual(rn_one.night_count, 1)
        self.assertEqual(rn_one.ot_minutes, 0)
        self.assertIn("Senior RN", rn_one.summary)
        self.assertEqual(explanation.preference.avoid_violations, 1)

    def test_explanation_rejects_assignment_outside_snapshot(self) -> None:
        with self.assertRaises(ValueError):
            build_schedule_explanation(self.snapshot, (PreviewAssignmentInput(99, 1, date(2026, 8, 1), False),))

    def test_explanation_can_be_serialized_as_the_api_response(self) -> None:
        explanation = build_schedule_explanation(self.snapshot, self.assignments)
        response = SchedulerPreviewExplanationOut(
            **asdict(explanation), will_write_schedule=False, will_publish_schedule=False,
        )
        self.assertEqual(response.fairness.status, "GOOD")
        self.assertEqual(len(response.staff_explanations), 3)


if __name__ == "__main__":
    unittest.main()
