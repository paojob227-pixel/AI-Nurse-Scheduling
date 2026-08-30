import tempfile
import unittest
from pathlib import Path

from app.scheduler.contracts import SchedulerSnapshot
from app.simulation.benchmark_runner import BenchmarkResult, StaffMetric, run_benchmark
from app.simulation.dataset_generator import build_snapshot
from app.simulation.reports import render_report, write_report
from app.simulation.scenarios import DEFAULT_ICU_SCENARIO


class IcuSimulationTests(unittest.TestCase):
    def test_documented_icu_simulation_snapshot_shape_is_reproducible(self) -> None:
        snapshot = build_snapshot()
        self.assertEqual((snapshot.year, snapshot.month), (2026, 8))
        self.assertEqual(len(snapshot.staff), 40)
        self.assertEqual(sum(item.position == "RN" for item in snapshot.staff), 30)
        self.assertEqual(sum(item.is_senior_rn for item in snapshot.staff), 6)
        self.assertEqual(sum(item.position in {"PN", "NA"} for item in snapshot.staff), 10)
        self.assertEqual(len(snapshot.coverage_windows), 3)
        self.assertEqual(snapshot.rules["MIN_RN"], 3)
        self.assertEqual(snapshot.rules["MIN_SUPPORT"], 1)
        self.assertEqual(len(snapshot.leave_requests), 6)  # 15% of 40 staff
        self.assertEqual(len(snapshot.availability), 4)  # 10% of 40 staff
        self.assertTrue(all(item.status == "approved" for item in snapshot.leave_requests))
        self.assertTrue(
            all(
                (item.preference == "prefer" and item.shift_type_id in {1, 2})
                or (item.preference == "avoid" and item.shift_type_id == 3)
                for item in snapshot.preferences
            )
        )
        self.assertEqual(len(snapshot.locked_assignments), 3)
        self.assertEqual(snapshot.locked_assignments[0].staff_id, 1)
        self.assertIsInstance(snapshot, SchedulerSnapshot)

    def test_simulation_benchmark_reports_solver_and_quality_metrics(self) -> None:
        result = run_benchmark()
        self.assertIn(result.solver_status, {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID"})
        self.assertGreaterEqual(result.solve_time_ms, 0)
        if result.solver_status in {"OPTIMAL", "FEASIBLE"}:
            self.assertGreater(result.assignment_count, 0)
            self.assertTrue(result.staff_metrics)
            self.assertTrue(result.coverage_pass)

    def test_benchmark_report_contains_dataset_and_staff_metrics(self) -> None:
        result = BenchmarkResult(DEFAULT_ICU_SCENARIO, "FEASIBLE", 10_000, 12.0, 1, 0, 1, True, 0, (StaffMetric("RN001", 1, 480, 10, 0, 0, 0, 0),))
        markdown = render_report(result)
        self.assertIn("# ICU Simulation Result", markdown)
        self.assertIn("| Staff | Shifts | Hours |", markdown)
        with tempfile.TemporaryDirectory() as directory:
            output = write_report(result, Path(directory) / "report.md")
            self.assertTrue(output.exists())
            self.assertIn(result.solver_status, output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
