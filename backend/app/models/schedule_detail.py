from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class ScheduleDetail(Base):
    """One staff assignment on one working date within a monthly schedule."""

    __tablename__ = "schedule_details"
    __table_args__ = (UniqueConstraint("schedule_id", "staff_id", "work_date", name="uq_schedule_staff_work_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id"), index=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staffs.id"), index=True)
    shift_type_id: Mapped[int] = mapped_column(ForeignKey("shift_types.id"))
    work_date: Mapped[date] = mapped_column(Date)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    generated: Mapped[bool] = mapped_column(Boolean, default=False)
    is_incharge: Mapped[bool] = mapped_column(Boolean, default=False)
    incharge_exception: Mapped[bool] = mapped_column(Boolean, default=False)
    exception_reason: Mapped[str | None] = mapped_column(Text)
    exception_approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    exception_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    schedule: Mapped["Schedule"] = relationship(back_populates="details")
    staff: Mapped["Staff"] = relationship(back_populates="schedule_details")
