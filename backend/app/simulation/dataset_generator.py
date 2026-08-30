"""Synthetic but reproducible ICU data generator; it never persists records."""

from datetime import date, time
from random import Random

from app.scheduler.contracts import (
    LockedAssignment, SchedulerAvailability, SchedulerCoverageWindow, SchedulerLeave,
    SchedulerPreference, SchedulerShift, SchedulerSnapshot, SchedulerStaff,
)
from app.simulation.scenarios import DEFAULT_ICU_SCENARIO, IcuSimulationScenario


def build_snapshot(scenario: IcuSimulationScenario = DEFAULT_ICU_SCENARIO) -> SchedulerSnapshot:
    """Build the documented 31-day ICU snapshot in memory only."""
    if (scenario.year, scenario.month) != (2026, 8):
        raise ValueError("The default Phase 3.1 ICU scenario is fixed to August 2026 (31 days)")
    rng = Random(scenario.seed)
    staff: list[SchedulerStaff] = [
        SchedulerStaff(number, f"RN{number:03d}", f"RN {number:03d}", "RN", number <= scenario.senior_rn_count)
        for number in range(1, scenario.rn_count + 1)
    ]
    staff.extend(SchedulerStaff(scenario.rn_count + number, f"PN{number:03d}", f"PN {number:03d}", "PN", False) for number in range(1, scenario.pn_count + 1))
    staff.extend(SchedulerStaff(scenario.rn_count + scenario.pn_count + number, f"NA{number:03d}", f"NA {number:03d}", "NA", False) for number in range(1, scenario.na_count + 1))
    shifts = (
        SchedulerShift(1, "AM", time(7), time(15), 480, False),
        SchedulerShift(2, "PM", time(15), time(23), 480, False),
        SchedulerShift(3, "N", time(23), time(7), 480, True),
    )
    windows = (
        SchedulerCoverageWindow("07:00-15:00", time(7), time(15), False, 3, 4, 1, 1, (1,)),
        SchedulerCoverageWindow("15:00-23:00", time(15), time(23), False, 3, 4, 1, 1, (2,)),
        SchedulerCoverageWindow("23:00-07:00", time(23), time(7), True, 3, 4, 1, 1, (3,)),
    )
    regular_rn_ids = list(range(scenario.senior_rn_count + 1, scenario.rn_count + 1))
    support_start = scenario.rn_count + 1
    support_ids = list(range(support_start, support_start + scenario.pn_count + scenario.na_count))
    leaves = [
        SchedulerLeave(staff_id, date(scenario.year, scenario.month, day), date(scenario.year, scenario.month, day + 1), "approved")
        for staff_id, day in ((staff_id, rng.randint(2, 28)) for staff_id in rng.sample(regular_rn_ids, scenario.leave_rn_count))
    ]
    leaves.extend(SchedulerLeave(staff_id, date(scenario.year, scenario.month, day), date(scenario.year, scenario.month, day), "approved") for staff_id, day in ((staff_id, rng.randint(2, 30)) for staff_id in rng.sample(support_ids, scenario.leave_support_count)))
    availability = tuple(SchedulerAvailability(staff_id, date(scenario.year, scenario.month, rng.randint(1, 31)), "unavailable") for staff_id in rng.sample(regular_rn_ids, scenario.unavailable_count))
    preferences: list[SchedulerPreference] = []
    for staff_id in rng.sample(regular_rn_ids, scenario.preference_count):
        preference_type = rng.choice(("prefer", "avoid"))
        # The scenario intentionally models the common ICU request pattern:
        # prefer day/evening shifts, or avoid a night shift.
        shift_id = rng.choice((1, 2)) if preference_type == "prefer" else 3
        preferences.append(
            SchedulerPreference(
                staff_id,
                date(scenario.year, scenario.month, rng.randint(1, 31)),
                shift_id,
                preference_type,
                rng.randint(1, 5),
            )
        )
    return SchedulerSnapshot(
        department_id=scenario.department_id, year=scenario.year, month=scenario.month,
        staff=tuple(staff), shifts=shifts, coverage_windows=windows,
        rules={"MIN_RN": 3, "MAX_RN": 4, "MIN_SUPPORT": 1, "REST_AFTER_NIGHT": 8, "MONTHLY_HOURS": 160, "OT_THRESHOLD": 168},
        leave_requests=tuple(leaves), availability=availability, preferences=tuple(preferences),
        locked_assignments=(
            LockedAssignment(1, 1, date(scenario.year, scenario.month, 1)),
            LockedAssignment(2, 2, date(scenario.year, scenario.month, 2)),
            LockedAssignment(3, 3, date(scenario.year, scenario.month, 3)),
        ), preflight_issues=(),
    )
