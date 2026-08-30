from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class Schedule(Base):
    __tablename__ = "schedules"
    __table_args__ = (UniqueConstraint("department_id", "year", "month", name="uq_schedule_department_month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    year: Mapped[int] = mapped_column()
    month: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), default="draft")
    source: Mapped[str] = mapped_column(String(20), default="MANUAL")
    validation_state: Mapped[str] = mapped_column(String(30), default="pending")
    approval_state: Mapped[str] = mapped_column(String(30), default="not_requested")
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_validated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    last_error_count: Mapped[int] = mapped_column(Integer, default=0)
    last_warning_count: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    details: Mapped[list["ScheduleDetail"]] = relationship(back_populates="schedule", cascade="all, delete-orphan")
