"""Auditable, human-in-the-loop workflow for persisted AI schedule proposals."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import AiScheduleDraft, AiScheduleDraftDetail, User
from app.scheduler.contracts import SchedulerSnapshot
from app.services.ai_preview_validation import PreviewAssignmentInput, validate_preview
from app.services.schedule_publish_validation import conflict_snapshot


class AiDraftApprovalError(ValueError):
    pass


def create_draft(
    db: Session,
    snapshot: SchedulerSnapshot,
    created_by: User,
    solver_status: str,
    objective_score: float | None,
    assignments: tuple[PreviewAssignmentInput, ...],
) -> AiScheduleDraft:
    """Persist an AI proposal and its validator result without touching Manual Schedule data."""
    conflicts = validate_preview(snapshot, assignments)
    errors = sum(item.severity == "error" for item in conflicts)
    warnings = sum(item.severity == "warning" for item in conflicts)
    validation_status = "failed" if errors else "passed_with_warnings" if warnings else "passed"
    valid_staff_ids = {item.id for item in snapshot.staff}
    valid_shift_ids = {item.id for item in snapshot.shifts}
    valid_assignments = [
        item for item in assignments
        if item.staff_id in valid_staff_ids and item.shift_type_id in valid_shift_ids
        and item.work_date.year == snapshot.year and item.work_date.month == snapshot.month
    ]
    draft = AiScheduleDraft(
        department_id=snapshot.department_id, year=snapshot.year, month=snapshot.month,
        created_by_user_id=created_by.id, solver_status=solver_status, objective_score=objective_score,
        status="GENERATED", validation_status=validation_status,
        validation_error_count=errors, validation_warning_count=warnings,
        validation_conflicts=conflict_snapshot(conflicts), approval_status="not_submitted",
    )
    db.add(draft)
    db.flush()
    db.add_all(AiScheduleDraftDetail(
        draft_id=draft.id, staff_id=item.staff_id, shift_type_id=item.shift_type_id,
        work_date=item.work_date, is_incharge=item.is_incharge,
    ) for item in valid_assignments)
    return draft


def submit_for_approval(draft: AiScheduleDraft, actor: User) -> AiScheduleDraft:
    """Make a successfully validated proposal available for Head Nurse decision."""
    if draft.status != "GENERATED" or draft.approval_status != "not_submitted":
        raise AiDraftApprovalError("Only a newly generated, unsubmitted AI draft can be submitted for approval")
    if draft.validation_status not in {"passed", "passed_with_warnings"}:
        raise AiDraftApprovalError("AI draft must pass ICU validation before it can be submitted for approval")
    draft.status = "VALIDATED"
    draft.approval_status = "pending"
    draft.submitted_by_user_id = actor.id
    draft.submitted_at = datetime.now(timezone.utc)
    return draft


def approve_draft(draft: AiScheduleDraft, head_nurse: User) -> AiScheduleDraft:
    """Record Head Nurse approval only; conversion to a Manual Schedule remains separate."""
    if draft.status != "VALIDATED" or draft.approval_status != "pending":
        raise AiDraftApprovalError("Only a validated AI draft pending approval can be approved")
    draft.status = "APPROVED"
    draft.approval_status = "approved"
    draft.approved_by_user_id = head_nurse.id
    draft.approved_at = datetime.now(timezone.utc)
    return draft


def reject_draft(draft: AiScheduleDraft, head_nurse: User, reason: str) -> AiScheduleDraft:
    """Record a Head Nurse rejection without deleting the proposal or its audit data."""
    if draft.status != "VALIDATED" or draft.approval_status != "pending":
        raise AiDraftApprovalError("Only a validated AI draft pending approval can be rejected")
    draft.status = "REJECTED"
    draft.approval_status = "rejected"
    draft.rejected_by_user_id = head_nurse.id
    draft.rejected_at = datetime.now(timezone.utc)
    draft.rejection_reason = reason
    return draft
