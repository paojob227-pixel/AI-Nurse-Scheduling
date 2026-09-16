from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class StaffShiftPreference(Base):
    """A dated shift request used as a soft constraint by the future scheduler."""

    __tablename__ = "staff_shift_preferences"
    __table_args__ = (UniqueConstraint("staff_id", "work_date", "shift_type_id", "preference", name="uq_staff_preference"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staffs.id"), index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    # A null shift denotes an all-day hard unavailability request. It is only
    # valid for an "avoid" preference with weight 5 (enforced by the service).
    shift_type_id: Mapped[int | None] = mapped_column(ForeignKey("shift_types.id"), nullable=True)
    preference: Mapped[str] = mapped_column(String(20))
    weight: Mapped[int] = mapped_column(Integer, default=1)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    staff: Mapped["Staff"] = relationship(back_populates="shift_preferences")
