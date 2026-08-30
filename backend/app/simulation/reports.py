"""Markdown reporting for the internal ICU simulation benchmark."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.simulation.benchmark_runner import BenchmarkResult


DEFAULT_REPORT_PATH = Path(__file__).resolve().parents[3] / "SIMULATION_BENCHMARK.md"


def render_report(result: "BenchmarkResult") -> str:
    """Render an inspectable research/evaluation report without database access."""
    metrics = result.staff_metrics
    workload_range = "n/a" if not metrics else f"{min(item.working_minutes for item in metrics)}–{max(item.working_minutes for item in metrics)} minutes"
    night_range = "n/a" if not metrics else f"{min(item.night_count for item in metrics)}–{max(item.night_count for item in metrics)}"
    lines = [
        "# ICU Simulation Result", "", "## Dataset", "",
        f"- Department: {result.scenario.department_name}",
        f"- Period: {result.scenario.year}-{result.scenario.month:02d} (31 days)",
        f"- RN: {result.scenario.rn_count} (Senior RN: {result.scenario.senior_rn_count})",
        f"- PN/NA: {result.scenario.pn_count + result.scenario.na_count}", "",
        "## Result", "", f"- Solver: `{result.solver_status}`",
        f"- Solve time: {result.solve_time_ms / 1000:.2f} seconds ({result.solve_time_ms:.0f} ms)",
        f"- Objective value: {result.objective_value if result.objective_value is not None else 'n/a'}",
        f"- Generated assignments: {result.assignment_count}", "", "## Validation", "",
        f"- Errors: {result.validation_error_count}", f"- Warnings: {result.validation_warning_count}",
        f"- Coverage pass: {'yes' if result.coverage_pass else 'no'}", f"- OT: {result.total_ot_minutes} minutes", "",
        "## Workload", "", f"- Workload range: {workload_range}", f"- RN Night range: {night_range}", "",
        "| Staff | Shifts | Hours | Workload | N | D | DE | OT min |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    lines.extend(f"| {item.employee_code} | {item.total_shifts} | {item.working_minutes / 60:.1f} | {item.workload_score} | {item.night_count} | {item.d_count} | {item.de_count} | {item.ot_minutes} |" for item in metrics)
    lines.extend(["", "The generated dataset is seeded and the benchmark is in-memory only; it does not write production schedule tables. A time-bounded FEASIBLE CP-SAT result may vary between runs."])
    return "\n".join(lines) + "\n"


def write_report(result: "BenchmarkResult", path: Path = DEFAULT_REPORT_PATH) -> Path:
    """Write a generated Markdown report; caller chooses the output path."""
    path.write_text(render_report(result), encoding="utf-8")
    return path
