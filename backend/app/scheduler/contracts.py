from dataclasses import dataclass
from datetime import date, time
from typing import Literal


IssueSeverity = Literal["error", "warning"]


@dataclass(frozen=True)
class SchedulerStaff:
    id: int
    employee_code: str
    display_name: str
    position: str
    is_senior_rn: bool
    is_head_nurse: bool = False


@dataclass(frozen=True)
class SchedulerShift:
    id: int
    code: str
    start_time: time | None
    end_time: time | None
    duration_minutes: int | None
    crosses_midnight: bool


@dataclass(frozen=True)
class SchedulerCoverageWindow:
    code: str
    start_time: time
    end_time: time
    crosses_midnight: bool
    min_rn: int
    max_rn: int
    min_support_staff: int
    min_senior_rn: int
    shift_type_ids: tuple[int, ...]


@dataclass(frozen=True)
class SchedulerLeave:
    staff_id: int
    start_date: date
    end_date: date
    status: str = "approved"


@dataclass(frozen=True)
class SchedulerAvailability:
    staff_id: int
    work_date: date
    status: str
    shift_type_id: int | None = None


@dataclass(frozen=True)
class SchedulerPreference:
    staff_id: int
    work_date: date
    shift_type_id: int
    preference: Literal["prefer", "avoid"]
    weight: int


@dataclass(frozen=True)
class LockedAssignment:
    staff_id: int
    shift_type_id: int
    work_date: date


@dataclass(frozen=True)
class PreflightIssue:
    severity: IssueSeverity
    code: str
    reason: str


@dataclass(frozen=True)
class SchedulerSnapshot:
    department_id: int
    year: int
    month: int
    staff: tuple[SchedulerStaff, ...]
    shifts: tuple[SchedulerShift, ...]
    coverage_windows: tuple[SchedulerCoverageWindow, ...]
    rules: dict[str, int]
    leave_requests: tuple[SchedulerLeave, ...]
    availability: tuple[SchedulerAvailability, ...]
    preferences: tuple[SchedulerPreference, ...]
    locked_assignments: tuple[LockedAssignment, ...]
    preflight_issues: tuple[PreflightIssue, ...]


@dataclass(frozen=True)
class SolverDryRunResult:
    solver_status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID"]
    objective_value: float | None
    solve_time_seconds: float
    variable_count: int
    constraint_count: int
    diagnostics: tuple[PreflightIssue, ...]
    candidate_assignments: tuple[LockedAssignment, ...]
    assignment_variable_count: int
    incharge_variable_count: int
    locked_assignment_constraint_count: int
    locked_assignment_issues: tuple[PreflightIssue, ...]
    approved_leave_constraint_count: int
    approved_leave_issues: tuple[PreflightIssue, ...]
    availability_constraint_count: int
    availability_issues: tuple[PreflightIssue, ...]
    staffing_constraint_count: int
    coverage_constraint_count: int
    coverage_issues: tuple[PreflightIssue, ...]
    senior_rn_constraint_count: int
    incharge_qualification_constraint_count: int
    incharge_coverage_constraint_count: int
    senior_incharge_issues: tuple[PreflightIssue, ...]
    rest_constraint_count: int
    overlap_constraint_count: int
    multiple_shift_constraint_count: int
    one_shift_per_day_constraint_count: int
    rest_overlap_issues: tuple[PreflightIssue, ...]
    assigned_shift_count_variable_count: int
    working_minutes_variable_count: int
    workload_score_variable_count: int
    fairness_imbalance_variable_count: int
    fairness_constraint_count: int
    fairness_issues: tuple[PreflightIssue, ...]
    preference_variable_count: int
    preference_score_term_count: int
    preference_constraint_count: int
    preference_issues: tuple[PreflightIssue, ...]
    ot_variable_count: int
    ot_penalty_terms: int
    ot_constraint_count: int
    ot_diagnostics: tuple[PreflightIssue, ...]
    objective_components: tuple[tuple[str, int, int], ...]
    objective_weights: dict[str, int]
    total_objective_terms: int
    notices: tuple[str, ...]


@dataclass(frozen=True)
class PreviewAssignment:
    staff_id: int
    employee_code: str
    staff_name: str
    work_date: date
    shift_type_id: int
    shift_code: str
    is_incharge: bool


@dataclass(frozen=True)
class PreviewStaffWorkload:
    staff_id: int
    employee_code: str
    staff_name: str
    assigned_shift_count: int
    working_minutes: int
    workload_score: int
    ot_minutes: int


@dataclass(frozen=True)
class SchedulerPreviewSummary:
    total_staff: int
    total_assignments: int
    total_working_minutes: int
    total_ot_minutes: int
    objective_score: float
    staff_workloads: tuple[PreviewStaffWorkload, ...]
    quality_score: float = 0.0
    fairness_score: float = 0.0
    preference_score: float = 0.0
    ot_score: float = 0.0


@dataclass(frozen=True)
class SchedulerPreviewResult:
    solver_status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID"]
    objective_value: float | None
    solve_time_seconds: float
    variable_count: int
    constraint_count: int
    diagnostics: tuple[PreflightIssue, ...]
    assignments: tuple[PreviewAssignment, ...]
    summary: SchedulerPreviewSummary | None
    notices: tuple[str, ...]
