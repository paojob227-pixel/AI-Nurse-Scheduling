"""Workload-distribution statistics; these do not alter the solver objective."""

from dataclasses import dataclass
from statistics import fmean, pstdev


@dataclass(frozen=True)
class FairnessReport:
    mean_workload_minutes: float
    minimum_workload_minutes: int
    maximum_workload_minutes: int
    workload_difference_minutes: int
    standard_deviation_minutes: float
    status: str


def build_fairness_report(workload_minutes: dict[int, int]) -> FairnessReport:
    """Classify spread relative to mean without creating a new scheduling rule."""
    values = list(workload_minutes.values())
    if not values:
        return FairnessReport(0.0, 0, 0, 0, 0.0, "IMBALANCED")
    mean = fmean(values)
    deviation = pstdev(values) if len(values) > 1 else 0.0
    ratio = deviation / mean if mean else 0.0
    status = "GOOD" if ratio <= 0.10 else "ACCEPTABLE" if ratio <= 0.25 else "IMBALANCED"
    return FairnessReport(mean, min(values), max(values), max(values) - min(values), deviation, status)
