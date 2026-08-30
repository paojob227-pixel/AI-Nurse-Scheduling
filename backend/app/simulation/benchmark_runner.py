"""Internal CLI for repeatable CP-SAT ICU simulation evaluation."""

from dataclasses import asdict, dataclass

from app.scheduler.contracts import SchedulerSnapshot
from app.scheduler.solver import CpSatSchedulerSolver
from app.services.ai_preview_validation import PreviewAssignmentInput, validate_preview
from app.simulation.dataset_generator import build_snapshot
from app.simulation.reports import write_report
from app.simulation.scenarios import DEFAULT_ICU_SCENARIO, IcuSimulationScenario


@dataclass(frozen=True)
class StaffMetric:
    employee_code: str
    total_shifts: int
    working_minutes: int
    workload_score: int
    night_count: int
    d_count: int
    de_count: int
    ot_minutes: int


@dataclass(frozen=True)
class BenchmarkResult:
    scenario: IcuSimulationScenario
    solver_status: str
    solve_time_ms: float
    objective_value: float | None
    assignment_count: int
    validation_error_count: int
    validation_warning_count: int
    coverage_pass: bool
    total_ot_minutes: int
    staff_metrics: tuple[StaffMetric, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def run_benchmark(snapshot: SchedulerSnapshot | None = None, scenario: IcuSimulationScenario = DEFAULT_ICU_SCENARIO) -> BenchmarkResult:
    """Run solver, validate its temporary result, and collect research metrics."""
    current = snapshot or build_snapshot(scenario)
    preview = CpSatSchedulerSolver().preview(current)
    if preview.summary is None:
        return BenchmarkResult(scenario, preview.solver_status, preview.solve_time_seconds * 1000, preview.objective_value, 0, 0, 0, False, 0, ())
    conflicts = validate_preview(current, tuple(PreviewAssignmentInput(item.staff_id, item.shift_type_id, item.work_date, item.is_incharge) for item in preview.assignments))
    code_by_id = {staff.id: staff.employee_code for staff in current.staff}
    metrics = tuple(StaffMetric(
        employee_code=code_by_id[item.staff_id], total_shifts=item.assigned_shift_count,
        working_minutes=item.working_minutes, workload_score=item.workload_score,
        night_count=sum(assignment.staff_id == item.staff_id and assignment.shift_code == "N" for assignment in preview.assignments),
        d_count=sum(assignment.staff_id == item.staff_id and assignment.shift_code == "D" for assignment in preview.assignments),
        de_count=sum(assignment.staff_id == item.staff_id and assignment.shift_code == "DE" for assignment in preview.assignments),
        ot_minutes=item.ot_minutes,
    ) for item in preview.summary.staff_workloads)
    errors = sum(item.severity == "error" for item in conflicts)
    warnings = sum(item.severity == "warning" for item in conflicts)
    return BenchmarkResult(scenario, preview.solver_status, preview.solve_time_seconds * 1000, preview.objective_value, len(preview.assignments), errors, warnings, errors == 0, preview.summary.total_ot_minutes, metrics)


def main() -> None:
    result = run_benchmark()
    report_path = write_report(result)
    print(f"Simulation benchmark report written to {report_path}")


if __name__ == "__main__":
    main()
