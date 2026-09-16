from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginInput(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=4, max_length=128)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshInput(BaseModel):
    refresh_token: str = Field(min_length=1)


class UserOut(ORMModel):
    id: int
    username: str
    role: str
    is_active: bool


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=30)


class DepartmentOut(ORMModel):
    id: int
    name: str
    code: str


class StaffBase(BaseModel):
    employee_code: str = Field(min_length=1, max_length=30)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    position: str = Field(min_length=1, max_length=50)
    skill_level: str | None = Field(default=None, max_length=30)
    is_senior_rn: bool = False
    employment_type: str = Field(default="full_time", max_length=30)
    start_date: date | None = None
    active: bool = True
    department_id: int | None = None


class StaffCreate(StaffBase):
    username: str | None = Field(default=None, min_length=3, max_length=50)
    password: str | None = Field(default=None, min_length=4, max_length=128)
    role: str = "nurse"


class StaffUpdate(StaffBase):
    pass


class StaffOut(StaffBase, ORMModel):
    id: int
    user_id: int | None


class SeniorRnUpdate(BaseModel):
    is_senior_rn: bool


class ShiftTypeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    start_time: time | None = None
    end_time: time | None = None
    is_working_shift: bool = True


class ShiftTypeOut(ShiftTypeCreate, ORMModel):
    id: int


class HolidayCreate(BaseModel):
    date: date
    name: str = Field(min_length=1, max_length=150)


class HolidayOut(HolidayCreate, ORMModel):
    id: int


class AvailabilityCreate(BaseModel):
    staff_id: int | None = None
    date: date
    shift_type_id: int | None = None
    status: str = Field(pattern="^(available|unavailable|preferred_off)$")
    reason: str | None = Field(default=None, max_length=255)


class AvailabilityOut(AvailabilityCreate, ORMModel):
    id: int
    staff_id: int


class StaffPreferenceCreate(BaseModel):
    staff_id: int | None = None
    work_date: date
    shift_type_id: int | None = None
    preference: Literal["prefer", "avoid"]
    weight: int = Field(default=1, ge=1, le=5)
    reason: str | None = Field(default=None, max_length=500)


class StaffPreferenceUpdate(BaseModel):
    work_date: date
    shift_type_id: int | None = None
    preference: Literal["prefer", "avoid"]
    weight: int = Field(default=1, ge=1, le=5)
    reason: str | None = Field(default=None, max_length=500)


class StaffPreferenceOut(ORMModel):
    id: int
    staff_id: int
    work_date: date
    shift_type_id: int | None
    preference: Literal["prefer", "avoid"]
    weight: int
    reason: str | None


class LeaveCreate(BaseModel):
    staff_id: int | None = None
    leave_type: str = Field(min_length=1, max_length=50)
    start_date: date
    end_date: date
    reason: str | None = None

    @model_validator(mode="after")
    def dates_are_valid(self) -> "LeaveCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class LeaveUpdate(BaseModel):
    status: str = Field(pattern="^(pending|approved|rejected|cancelled)$")


class LeaveOut(LeaveCreate, ORMModel):
    id: int
    staff_id: int
    status: str


class SettingUpsert(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1)


class SettingOut(SettingUpsert, ORMModel):
    id: int


IcuRuleKey = Literal["MIN_RN", "MAX_RN", "MIN_SUPPORT", "REST_AFTER_NIGHT", "MONTHLY_HOURS", "OT_THRESHOLD"]


class IcuRuleCreate(BaseModel):
    key: IcuRuleKey
    value: int


class IcuRuleUpdate(BaseModel):
    value: int


class IcuRuleOut(ORMModel):
    id: int
    department_id: int
    key: IcuRuleKey
    value: int
    enabled: bool


class ScheduleCreate(BaseModel):
    department_id: int
    year: int = Field(ge=2020, le=2100)
    month: int = Field(ge=1, le=12)


class AssignmentUpsert(BaseModel):
    staff_id: int
    shift_type_id: int
    work_date: date
    locked: bool = False


class AssignmentOut(AssignmentUpsert, ORMModel):
    id: int
    schedule_id: int
    generated: bool


class ScheduleOut(ORMModel):
    id: int
    department_id: int
    year: int
    month: int
    status: str
    source: Literal["MANUAL", "AI_GENERATED"]
    validation_state: str
    approval_state: str
    last_validated_at: datetime | None
    last_error_count: int
    last_warning_count: int
    published_at: datetime | None
    details: list[AssignmentOut]


class ScheduleConflictOut(BaseModel):
    severity: Literal["error", "warning"]
    code: str
    work_date: date
    shift: str
    staff_ids: list[int]
    staff_names: list[str]
    reason: str


class ScheduleValidationOut(BaseModel):
    schedule_id: int
    error_count: int
    warning_count: int
    conflicts: list[ScheduleConflictOut]


class ScheduleValidationHistoryOut(BaseModel):
    id: int
    schedule_id: int
    validated_by_user_id: int | None
    error_count: int
    warning_count: int
    outcome: str
    conflicts: list[ScheduleConflictOut]
    created_at: datetime


class SchedulerDryRunRequest(BaseModel):
    department_id: int
    year: int = Field(ge=2020, le=2100)
    month: int = Field(ge=1, le=12)


class SchedulerPreflightIssueOut(BaseModel):
    severity: Literal["error", "warning"]
    code: str
    reason: str


class SchedulerSnapshotSummaryOut(BaseModel):
    staff_count: int
    shift_count: int
    coverage_window_count: int
    approved_leave_count: int
    availability_count: int
    preference_count: int
    locked_assignment_count: int
    configured_rule_count: int


class SchedulerObjectiveComponentOut(BaseModel):
    weight: int
    score_term_count: int


class SchedulerPreviewAssignmentOut(BaseModel):
    staff_id: int
    employee_code: str
    staff_name: str
    work_date: date
    shift_type_id: int
    shift_code: str
    is_incharge: bool


class SchedulerPreviewStaffWorkloadOut(BaseModel):
    staff_id: int
    employee_code: str
    staff_name: str
    assigned_shift_count: int
    working_minutes: int
    workload_score: int
    ot_minutes: int


class SchedulerPreviewSummaryOut(BaseModel):
    total_staff: int
    total_assignments: int
    total_working_minutes: int
    total_ot_minutes: int
    objective_score: float
    quality_score: float = Field(ge=0, le=10)
    fairness_score: float = Field(ge=0, le=10)
    preference_score: float = Field(ge=0, le=10)
    ot_score: float = Field(ge=0, le=10)
    staff_workloads: list[SchedulerPreviewStaffWorkloadOut]


class SchedulerPreviewOut(BaseModel):
    department_id: int
    year: int
    month: int
    solver_status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID"]
    objective_value: float | None
    solve_time_seconds: float
    variable_count: int
    constraint_count: int
    diagnostics: list[SchedulerPreflightIssueOut]
    assignments: list[SchedulerPreviewAssignmentOut]
    summary: SchedulerPreviewSummaryOut | None
    will_write_schedule: bool
    will_publish_schedule: bool
    notices: list[str]


class SchedulerPreviewValidationAssignmentIn(BaseModel):
    staff_id: int
    shift_type_id: int
    work_date: date
    is_incharge: bool = False


class SchedulerPreviewValidationRequest(SchedulerDryRunRequest):
    assignments: list[SchedulerPreviewValidationAssignmentIn]


class SchedulerPreviewValidationOut(BaseModel):
    status: Literal["passed", "passed_with_warnings", "failed"]
    error_count: int
    warning_count: int
    conflicts: list[ScheduleConflictOut]
    will_write_schedule: bool
    will_publish_schedule: bool


class SchedulerPreviewExplanationRequest(SchedulerPreviewValidationRequest):
    """The same in-memory assignment payload displayed in AI Preview mode."""


class SchedulerExplanationSummaryOut(BaseModel):
    total_assignments: int
    total_working_minutes: int
    total_ot_minutes: int
    message: str


class SchedulerFairnessReportOut(BaseModel):
    mean_workload_minutes: float
    minimum_workload_minutes: int
    maximum_workload_minutes: int
    workload_difference_minutes: int
    standard_deviation_minutes: float
    status: Literal["GOOD", "ACCEPTABLE", "IMBALANCED"]


class SchedulerNightStaffOut(BaseModel):
    staff_id: int
    employee_code: str
    night_count: int
    difference_from_mean: float


class SchedulerNightDistributionOut(BaseModel):
    total_night_assignments: int
    mean_nights_per_rn: float
    minimum_nights: int
    maximum_nights: int
    difference: int
    status: Literal["GOOD", "ACCEPTABLE", "WARNING"]
    staff: list[SchedulerNightStaffOut]


class SchedulerPreferenceReportOut(BaseModel):
    total_preferences: int
    prefer_total: int
    prefer_satisfied: int
    prefer_satisfaction_percent: float
    avoid_total: int
    avoid_violations: int
    overall_satisfied: int
    overall_satisfaction_percent: float


class SchedulerStaffExplanationOut(BaseModel):
    staff_id: int
    employee_code: str
    staff_name: str
    total_shifts: int
    working_minutes: int
    workload_score: int
    night_count: int
    ot_minutes: int
    shift_counts: dict[str, int]
    preference_total: int
    prefer_satisfied: int
    prefer_unsatisfied: int
    avoid_violations: int
    summary: str


class SchedulerPreviewExplanationOut(BaseModel):
    summary: SchedulerExplanationSummaryOut
    fairness: SchedulerFairnessReportOut
    night_distribution: SchedulerNightDistributionOut
    preference: SchedulerPreferenceReportOut
    staff_explanations: list[SchedulerStaffExplanationOut]
    will_write_schedule: bool
    will_publish_schedule: bool


class AiScheduleDraftCreate(SchedulerPreviewValidationRequest):
    solver_status: Literal["OPTIMAL", "FEASIBLE"]
    objective_score: float | None = None


class AiScheduleDraftDetailOut(ORMModel):
    id: int
    staff_id: int
    shift_type_id: int
    work_date: date
    is_incharge: bool


class AiScheduleDraftOut(ORMModel):
    id: int
    department_id: int
    year: int
    month: int
    created_by_user_id: int
    solver_status: str
    objective_score: float | None
    status: Literal["GENERATED", "VALIDATED", "APPROVED", "REJECTED"]
    validation_status: Literal["not_validated", "passed", "passed_with_warnings", "failed"]
    validation_error_count: int
    validation_warning_count: int
    validation_conflicts: list[ScheduleConflictOut]
    approval_status: Literal["not_submitted", "pending", "approved", "rejected"]
    submitted_by_user_id: int | None
    submitted_at: datetime | None
    approved_by_user_id: int | None
    approved_at: datetime | None
    rejected_by_user_id: int | None
    rejected_at: datetime | None
    rejection_reason: str | None
    converted_schedule_id: int | None
    converted_by_user_id: int | None
    converted_at: datetime | None
    created_at: datetime
    details: list[AiScheduleDraftDetailOut]


class AiScheduleDraftReject(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class AiDraftConversionOut(BaseModel):
    schedule_id: int
    status: Literal["draft"]
    source: Literal["AI_GENERATED"]
    validation_ran: bool
    error_count: int
    warning_count: int
    conflicts: list[ScheduleConflictOut]
    will_publish_schedule: bool


class SchedulerDryRunOut(BaseModel):
    department_id: int
    year: int
    month: int
    solver_status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID"]
    objective_value: float | None
    solve_time_seconds: float
    variable_count: int
    constraint_count: int
    diagnostics: list[SchedulerPreflightIssueOut]
    will_write_schedule: bool
    will_publish_schedule: bool
    assignment_variable_count: int
    incharge_variable_count: int
    locked_assignment_constraint_count: int
    locked_assignment_issues: list[SchedulerPreflightIssueOut]
    approved_leave_constraint_count: int
    approved_leave_issues: list[SchedulerPreflightIssueOut]
    availability_constraint_count: int
    availability_issues: list[SchedulerPreflightIssueOut]
    staffing_constraint_count: int
    coverage_constraint_count: int
    coverage_issues: list[SchedulerPreflightIssueOut]
    senior_rn_constraint_count: int
    incharge_qualification_constraint_count: int
    incharge_coverage_constraint_count: int
    senior_incharge_issues: list[SchedulerPreflightIssueOut]
    rest_constraint_count: int
    overlap_constraint_count: int
    multiple_shift_constraint_count: int
    one_shift_per_day_constraint_count: int
    rest_overlap_issues: list[SchedulerPreflightIssueOut]
    assigned_shift_count_variable_count: int
    working_minutes_variable_count: int
    workload_score_variable_count: int
    fairness_imbalance_variable_count: int
    fairness_constraint_count: int
    fairness_issues: list[SchedulerPreflightIssueOut]
    preference_variable_count: int
    preference_score_term_count: int
    preference_constraint_count: int
    preference_issues: list[SchedulerPreflightIssueOut]
    ot_variable_count: int
    ot_penalty_terms: int
    ot_constraint_count: int
    ot_diagnostics: list[SchedulerPreflightIssueOut]
    objective_components: dict[str, SchedulerObjectiveComponentOut]
    objective_weights: dict[str, int]
    total_objective_terms: int
    snapshot: SchedulerSnapshotSummaryOut
    preflight_issues: list[SchedulerPreflightIssueOut]
    notices: list[str]
