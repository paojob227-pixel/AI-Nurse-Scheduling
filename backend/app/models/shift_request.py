from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class ShiftRequest(Base):
    __tablename__ = "shift_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_staff_id: Mapped[int] = mapped_column(ForeignKey("staffs.id"))
    target_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staffs.id"))
    date: Mapped[date] = mapped_column(Date)
    requested_shift_type_id: Mapped[int | None] = mapped_column(ForeignKey("shift_types.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
