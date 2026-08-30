"""Repeatable ICU simulation scenario definitions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class IcuSimulationScenario:
    department_name: str = "ICU รวม"
    department_id: int = 999
    year: int = 2026
    month: int = 8
    seed: int = 26082026
    rn_count: int = 30
    senior_rn_count: int = 6
    pn_count: int = 5
    na_count: int = 5
    leave_rn_count: int = 4
    leave_support_count: int = 2
    unavailable_count: int = 4
    preference_count: int = 18


DEFAULT_ICU_SCENARIO = IcuSimulationScenario()
