"""Explicit conversion of an approved AI proposal into a Manual Schedule draft."""

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AiScheduleDraft, Schedule, ScheduleAuditLog, ScheduleDetail, User
from app.services import schedule_validator


class AiDraftConversionError(ValueError):
    pass


def validate_conversion_eligibility(draft: AiScheduleDraft) -> None:
    if draft.status != "APPROVED" or draft.approval_status != "approved":
        raise AiDraftConversionError("Only an approved AI draft can be converted to a Manual Schedule draft")
    if draft.converted_schedule_id is not None:
        raise AiDraftConversionError("This AI draft has already been converted to a Manual Schedule")
    duplicates = [key for key, count in Counter((item.staff_id, item.work_date) for item in draft.details).items() if count > 1]
    if duplicates:
        raise AiDraftConversionError("AI draft contains multiple shifts for the same staff member and date, which the current Manual Schedule model cannot represent")


def convert_approved_draft(db: Session, draft: AiScheduleDraft, actor: User, replace_existing_ai_draft: bool = False) -> tuple[Schedule, list[schedule_validator.Conflict]]:
    """Create, or explicitly replace, an AI-sourced Manual Schedule draft and validate it again."""
    validate_conversion_eligibility(draft)
    existing = db.scalar(select(Schedule).where(Schedule.department_id == draft.department_id, Schedule.year == draft.year, Schedule.month == draft.month).with_for_update())
    if existing is not None:
        empty_manual_draft = (
            existing.status == "draft" and existing.source == "MANUAL"
            and not existing.details and existing.published_at is None
        )
        if not empty_manual_draft and not replace_existing_ai_draft:
            raise AiDraftConversionError("A Manual Schedule already exists for this department and month; AI conversion will not overwrite it")
        if not empty_manual_draft and (existing.status != "draft" or existing.source != "AI_GENERATED"):
            raise AiDraftConversionError("ไม่สามารถเขียนทับตารางที่เผยแพร่แล้ว หรือตาราง Manual ที่มีเวรอยู่แล้วได้ กรุณาเลือกเดือนอื่นหรือทบทวนตารางเดิม")
        previous_assignment_count = len(existing.details)
        previous_source = existing.source
        for detail in list(existing.details):
            db.delete(detail)
        schedule = existing
        schedule.source = "AI_GENERATED"
        schedule.validation_state = "pending"
        schedule.approval_state = "not_requested"
        schedule.last_error_count = 0
        schedule.last_warning_count = 0
        audit_action = "AI_DRAFT_CONVERTED" if empty_manual_draft else "AI_DRAFT_REPLACED"
        audit_before = {"ai_draft_id": draft.id, "previous_assignment_count": previous_assignment_count, "previous_source": previous_source}
        db.flush()
    else:
        schedule = Schedule(department_id=draft.department_id, year=draft.year, month=draft.month, status="draft", source="AI_GENERATED", validation_state="pending", approval_state="not_requested")
        db.add(schedule)
        db.flush()
        audit_action = "AI_DRAFT_CONVERTED"
        audit_before = {"ai_draft_id": draft.id}

    db.add_all(ScheduleDetail(
        schedule_id=schedule.id, staff_id=item.staff_id, shift_type_id=item.shift_type_id,
        work_date=item.work_date, locked=False, generated=True, is_incharge=item.is_incharge,
    ) for item in draft.details)
    db.flush()

    conflicts = list(schedule_validator.validate_schedule(db, schedule.id))
    errors = sum(item.severity == "error" for item in conflicts)
    warnings = sum(item.severity == "warning" for item in conflicts)
    schedule.validation_state = "blocked" if errors else "passed_with_warnings" if warnings else "passed"
    schedule.approval_state = "not_requested"
    schedule.last_validated_at = datetime.now(timezone.utc)
    schedule.last_validated_by_user_id = actor.id
    schedule.last_error_count = errors
    schedule.last_warning_count = warnings
    draft.converted_schedule_id = schedule.id
    draft.converted_by_user_id = actor.id
    draft.converted_at = datetime.now(timezone.utc)
    db.add(ScheduleAuditLog(
        schedule_id=schedule.id, schedule_detail_id=None, actor_user_id=actor.id,
        action=audit_action, before_value=audit_before,
        after_value={"source": "AI_GENERATED", "assignment_count": len(draft.details), "validation_error_count": errors, "validation_warning_count": warnings},
        reason="Converted from Head Nurse-approved AI draft; publish remains a separate Manual Schedule workflow.",
    ))
    return schedule, conflicts
