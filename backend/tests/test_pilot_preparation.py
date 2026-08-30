import unittest
from datetime import date

from app.pilot_preparation.reports import (
    PilotKpiReport,
    PilotReadinessReport,
    PilotChecklistItem,
    build_pilot_kpi_report,
    render_pilot_readiness_markdown,
)
from app.scheduler.contracts import PreviewAssignment, PreviewStaffWorkload, SchedulerPreviewResult, SchedulerPreviewSummary
from app.simulation.dataset_generator import build_snapshot
from app.services.ai_preview_validation import PreviewAssignmentInput, validate_preview


class PilotPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = build_snapshot()
        self.assignments = (
            PreviewAssignment(1, "RN001", "RN 001", date(2026, 8, 1), 1, "AM", True),
            PreviewAssignment(2, "RN002", "RN 002", date(2026, 8, 1), 2, "PM", False),
            PreviewAssignment(3, "RN003", "RN 003", date(2026, 8, 1), 3, "N", False),
        )
        self.preview = SchedulerPreviewResult(
            "FEASIBLE", 42.0, 1.25, 10, 20, (), self.assignments,
            SchedulerPreviewSummary(
                40, 3, 1440, 0, 42.0,
                (
                    PreviewStaffWorkload(1, "RN001", "RN 001", 1, 480, 10, 0),
                    PreviewStaffWorkload(2, "RN002", "RN 002", 1, 480, 10, 0),
                    PreviewStaffWorkload(3, "RN003", "RN 003", 1, 480, 10, 0),
                ),
            ),
            ("Read-only preview",),
        )

    def test_kpi_report_contains_required_solver_validation_and_quality_metrics(self) -> None:
        preview_inputs = tuple(
            PreviewAssignmentInput(item.staff_id, item.shift_type_id, item.work_date, item.is_incharge)
            for item in self.assignments
        )
        report = build_pilot_kpi_report(self.snapshot, self.preview, validate_preview(self.snapshot, preview_inputs))
        self.assertEqual(report.solver_status, "FEASIBLE")
        self.assertEqual(report.generation_time_seconds, 1.25)
        self.assertEqual(report.total_ot_minutes, 0)
        self.assertIsNotNone(report.fairness_status)
        self.assertIsNotNone(report.night_distribution_status)
        self.assertIsNotNone(report.preference_satisfaction_percent)

    def test_kpi_report_remains_available_when_solver_has_no_preview(self) -> None:
        unavailable = SchedulerPreviewResult("INFEASIBLE", None, 0.5, 5, 10, (), (), None, ())
        report = build_pilot_kpi_report(self.snapshot, unavailable, ())
        self.assertEqual(report.solver_status, "INFEASIBLE")
        self.assertIsNone(report.fairness_status)
        self.assertEqual(report.validation_error_count, 0)

    def test_markdown_report_exposes_checklist_and_kpis(self) -> None:
        report = PilotReadinessReport(
            1, 2026, 8, True,
            (PilotChecklistItem("solver", "Read-only solver", "PASS", "FEASIBLE"),),
            PilotKpiReport(1.25, "FEASIBLE", 0, 2, 0, "GOOD", 60, "GOOD", 1, 80.0, 0),
        )
        markdown = render_pilot_readiness_markdown(report)
        self.assertIn("# ICU Clinical Pilot Readiness Report", markdown)
        self.assertIn("Read-only solver", markdown)
        self.assertIn("AI generation time: 1.25 seconds", markdown)
        self.assertIn("Preference satisfaction: 80.0%", markdown)


if __name__ == "__main__":
    unittest.main()
