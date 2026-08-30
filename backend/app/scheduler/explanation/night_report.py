"""Night-shift distribution diagnostics, intentionally separate from optimisation."""

from dataclasses import dataclass
from statistics import fmean

from app.scheduler.contracts import SchedulerSnapshot


@dataclass(frozen=True)
class NightStaffReport:
    staff_id: int
    employee_code: str
    night_count: int
    difference_from_mean: float


@dataclass(frozen=True)
class NightDistributionReport:
    total_night_assignments: int
    mean_nights_per_rn: float
    minimum_nights: int
    maximum_nights: int
    difference: int
    status: str
    staff: tuple[NightStaffReport, ...]


def build_night_report(snapshot: SchedulerSnapshot, assignment_keys: set[tuple[int, object, int]]) -> NightDistributionReport:
    """Count N shifts for RNs only; no night-fairness constraint is added."""
    night_shift_ids = {shift.id for shift in snapshot.shifts if shift.code.upper() == "N"}
    rns = [staff for staff in snapshot.staff if staff.position.upper() == "RN"]
    counts = {staff.id: sum(1 for staff_id, _day, shift_id in assignment_keys if staff_id == staff.id and shift_id in night_shift_ids) for staff in rns}
    values = list(counts.values())
    mean = fmean(values) if values else 0.0
    difference = max(values) - min(values) if values else 0
    status = "GOOD" if difference <= 1 else "ACCEPTABLE" if difference <= 3 else "WARNING"
    return NightDistributionReport(
        sum(values), mean, min(values) if values else 0, max(values) if values else 0, difference, status,
        tuple(NightStaffReport(staff.id, staff.employee_code, counts[staff.id], counts[staff.id] - mean) for staff in rns),
    )
