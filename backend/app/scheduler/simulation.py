"""Backward-compatible entry point for Phase 3.1 simulation tools."""

from app.simulation.benchmark_runner import BenchmarkResult as IcuBenchmarkResult, run_benchmark as run_icu_benchmark
from app.simulation.dataset_generator import build_snapshot as build_icu_simulation_snapshot

__all__ = ["IcuBenchmarkResult", "build_icu_simulation_snapshot", "run_icu_benchmark"]


if __name__ == "__main__":
    from app.simulation.benchmark_runner import main
    main()
