"""Internal, read-only reports used to prepare an ICU clinical pilot.

The report builder may run an in-memory CP-SAT preview to measure readiness,
but it never calls a database write operation and never changes the existing
AI approval or Manual Publish workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AiScheduleDraft, Schedule, ScheduleValidationHistory
from app.scheduler.explanation.schedule_explainer import build_schedule_explanation
from app.scheduler.snapshot_loader import load_snapshot
from app.scheduler.solver import CpSatSchedulerSolver
from app.services.ai_preview_validation import PreviewAssignmentInput, validate_preview


@dataclass(frozen=True)
class PilotChecklistItem:
    key: str
    label: str
    status: str
    detail: str


@dataclass(frozen=True)
class PilotKpiReport:
    generation_time_seconds: float
    solver_status: str
    validation_error_count: int
    validation_warning_count: int
    total_ot_minutes: int
    fairness_status: str | None
    fairness_difference_minutes: int | None
    night_distribution_status: str | None
    night_distribution_difference: int | None
    preference_satisfaction_percent: float | None
    preference_avoid_violations: int | None


@dataclass(frozen=True)
class PilotReadinessReport:
    department_id: int
    year: int
    month: int
    ready_for_clinical_review: bool
    checklist: tuple[PilotChecklistItem, ...]
    kpis: PilotKpiReport


@dataclass(frozen=True)
class PilotAuditItem:
    key: str
    label: str
    actor_user_id: int | None
    timestamp: datetime | None
    status: str
    detail: str


@dataclass(frozen=True)
class PilotAuditVerification:
    ai_draft_id: int
    converted_schedule_id: int | None
    complete: bool
    items: tuple[PilotAuditItem, ...]


def build_pilot_kpi_report(snapshot, preview, conflicts) -> PilotKpiReport:
    """Calculate pilot metrics from an ephemeral preview without modifying it."""
    if preview.summary is None:
        return PilotKpiReport(
            generation_time_seconds=preview.solve_time_seconds,
            solver_status=preview.solver_status,
            validation_error_count=sum(conflict.severity == "error" for conflict in conflicts),
            validation_warning_count=sum(conflict.severity == "warning" for conflict in conflicts),
            total_ot_minutes=0,
            fairness_status=None,
            fairness_difference_minutes=None,
            night_distribution_status=None,
            night_distribution_difference=None,
            preference_satisfaction_percent=None,
            preference_avoid_violations=None,
        )

    assignments = tuple(
        PreviewAssignmentInput(item.staff_id, item.shift_type_id, item.work_date, item.is_incharge)
        for item in preview.assignments
    )
    explanation = build_schedule_explanation(snapshot, assignments)
    return PilotKpiReport(
        generation_time_seconds=preview.solve_time_seconds,
        solver_status=preview.solver_status,
        validation_error_count=sum(conflict.severity == "error" for conflict in conflicts),
        validation_warning_count=sum(conflict.severity == "warning" for conflict in conflicts),
        total_ot_minutes=explanation.summary.total_ot_minutes,
        fairness_status=explanation.fairness.status,
        fairness_difference_minutes=explanation.fairness.workload_difference_minutes,
        night_distribution_status=explanation.night_distribution.status,
        night_distribution_difference=explanation.night_distribution.difference,
        preference_satisfaction_percent=explanation.preference.overall_satisfaction_percent,
        preference_avoid_violations=explanation.preference.avoid_violations,
    )


def build_pilot_readiness_report(db: Session, department_id: int, year: int, month: int) -> PilotReadinessReport:
    """Create a repeatable readiness report from a department-month snapshot.

    This is deliberately an internal service: its only database actions are
    reads performed by ``load_snapshot``.  The solver itself works in memory.
    """
    snapshot = load_snapshot(db, department_id, year, month)
    preview = CpSatSchedulerSolver().preview(snapshot)
    assignments = tuple(
        PreviewAssignmentInput(item.staff_id, item.shift_type_id, item.work_date, item.is_incharge)
        for item in preview.assignments
    )
    conflicts = validate_preview(snapshot, assignments) if assignments else ()
    preflight_errors = [issue for issue in snapshot.preflight_issues if issue.severity == "error"]
    validation_errors = [item for item in conflicts if item.severity == "error"]

    checklist = (
        PilotChecklistItem(
            "snapshot_data", "Pilot dataset is structurally complete",
            "PASS" if not preflight_errors else "BLOCKED",
            "No blocking snapshot issue found" if not preflight_errors else "; ".join(item.reason for item in preflight_errors),
        ),
        PilotChecklistItem(
            "de_identification", "Dataset uses operational identifiers only",
            "REVIEW_REQUIRED",
            "Confirm with the clinical owner that the selected dataset contains no patient data and no unnecessary personal identifiers.",
        ),
        PilotChecklistItem(
            "icu_rule_freeze", "ICU rules are configured and ready to freeze",
            "PASS" if not preflight_errors else "BLOCKED",
            "Confirm Head Nurse sign-off before running the clinical comparison.",
        ),
        PilotChecklistItem(
            "solver", "AI scheduler can generate a read-only candidate",
            "PASS" if preview.solver_status in {"OPTIMAL", "FEASIBLE"} else "BLOCKED",
            f"Solver status: {preview.solver_status}; generation time: {preview.solve_time_seconds:.2f} seconds.",
        ),
        PilotChecklistItem(
            "validator", "AI candidate passes the existing ICU validator",
            "PASS" if not validation_errors and assignments else "BLOCKED",
            "No hard validation errors" if not validation_errors and assignments else f"{len(validation_errors)} hard validation error(s) found.",
        ),
        PilotChecklistItem(
            "workflow_acceptance", "Human approval and Manual Publish Gate remain required",
            "REVIEW_REQUIRED",
            "Run the acceptance workflow in an isolated test database and obtain Head Nurse approval before clinical use.",
        ),
    )
    kpis = build_pilot_kpi_report(snapshot, preview, conflicts)
    return PilotReadinessReport(
        department_id, year, month,
        all(item.status == "PASS" for item in checklist if item.key not in {"de_identification", "workflow_acceptance"}),
        checklist, kpis,
    )


def build_pilot_audit_verification(db: Session, ai_draft_id: int) -> PilotAuditVerification:
    """Verify required actor/timestamp evidence for an already-created AI draft.

    Missing evidence is reported as a gap; this function does not backfill or
    alter audit data.  Validation evidence comes from the immutable Manual
    Schedule validation history after conversion.
    """
    draft = db.get(AiScheduleDraft, ai_draft_id)
    if draft is None:
        raise LookupError("AI schedule draft not found")
    schedule = db.get(Schedule, draft.converted_schedule_id) if draft.converted_schedule_id else None
    history = None
    if schedule is not None:
        history = db.scalar(
            select(ScheduleValidationHistory)
            .where(ScheduleValidationHistory.schedule_id == schedule.id)
            .order_by(ScheduleValidationHistory.created_at.desc(), ScheduleValidationHistory.id.desc())
        )

    items = (
        _audit_item("generated_by", "AI draft generator", draft.created_by_user_id, draft.created_at),
        _audit_item(
            "validated_by", "Manual validation actor",
            history.validated_by_user_id if history else None,
            history.created_at if history else None,
            "Validation evidence is recorded only after a converted draft is checked by the Manual workflow.",
        ),
        _audit_item("approved_by", "Head Nurse approver", draft.approved_by_user_id, draft.approved_at),
        _audit_item("published_by", "Manual schedule publisher", schedule.published_by_user_id if schedule else None, schedule.published_at if schedule else None),
    )
    return PilotAuditVerification(
        ai_draft_id, draft.converted_schedule_id,
        all(item.status == "VERIFIED" for item in items), items,
    )


def _audit_item(key: str, label: str, actor_user_id: int | None, timestamp: datetime | None, detail: str | None = None) -> PilotAuditItem:
    verified = actor_user_id is not None and timestamp is not None
    return PilotAuditItem(
        key, label, actor_user_id, timestamp, "VERIFIED" if verified else "MISSING",
        detail or ("Actor and timestamp are recorded." if verified else "Required audit actor or timestamp is missing."),
    )


def render_pilot_readiness_markdown(report: PilotReadinessReport) -> str:
    """Render a portable, human-readable pilot readiness report."""
    kpis = report.kpis
    lines = [
        "# ICU Clinical Pilot Readiness Report",
        "",
        f"- Department ID: {report.department_id}",
        f"- Period: {report.year}-{report.month:02d}",
        f"- Technical readiness: {'READY FOR CLINICAL REVIEW' if report.ready_for_clinical_review else 'BLOCKED'}",
        "",
        "## Readiness checklist",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
        *[f"| {item.label} | {item.status} | {item.detail} |" for item in report.checklist],
        "",
        "## KPI snapshot",
        "",
        f"- Solver: {kpis.solver_status}",
        f"- AI generation time: {kpis.generation_time_seconds:.2f} seconds",
        f"- Validation: {kpis.validation_error_count} error(s), {kpis.validation_warning_count} warning(s)",
        f"- OT: {kpis.total_ot_minutes} minutes",
        f"- Workload fairness: {kpis.fairness_status or 'not available'} (spread {kpis.fairness_difference_minutes if kpis.fairness_difference_minutes is not None else '-'} minutes)",
        f"- Night distribution: {kpis.night_distribution_status or 'not available'} (spread {kpis.night_distribution_difference if kpis.night_distribution_difference is not None else '-'})",
        f"- Preference satisfaction: {kpis.preference_satisfaction_percent if kpis.preference_satisfaction_percent is not None else '-'}%",
    ]
    return "\n".join(lines) + "\n"
