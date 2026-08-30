from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class AiScheduleDraft(Base):
    """Auditable AI proposal stored separately from Manual Schedule data."""

    __tablename__ = "ai_schedule_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    solver_status: Mapped[str] = mapped_column(String(20))
    objective_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="GENERATED", index=True)
    validation_status: Mapped[str] = mapped_column(String(30), default="not_validated")
    validation_error_count: Mapped[int] = mapped_column(Integer, default=0)
    validation_warning_count: Mapped[int] = mapped_column(Integer, default=0)
    validation_conflicts: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    approval_status: Mapped[str] = mapped_column(String(30), default="not_submitted")
    submitted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    converted_schedule_id: Mapped[int | None] = mapped_column(ForeignKey("schedules.id"))
    converted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    details: Mapped[list["AiScheduleDraftDetail"]] = relationship(back_populates="draft", cascade="all, delete-orphan")


class AiScheduleDraftDetail(Base):
    __tablename__ = "ai_schedule_draft_details"
    __table_args__ = (UniqueConstraint("draft_id", "staff_id", "work_date", "shift_type_id", name="uq_ai_draft_assignment"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("ai_schedule_drafts.id"), index=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staffs.id"), index=True)
    shift_type_id: Mapped[int] = mapped_column(ForeignKey("shift_types.id"))
    work_date: Mapped[date] = mapped_column(Date)
    is_incharge: Mapped[bool] = mapped_column(Boolean, default=False)

    draft: Mapped["AiScheduleDraft"] = relationship(back_populates="details")
