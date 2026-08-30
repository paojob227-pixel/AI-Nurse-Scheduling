from datetime import date

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class Availability(Base):
    __tablename__ = "availability"
    __table_args__ = (UniqueConstraint("staff_id", "date", "shift_type_id", name="uq_availability_staff_date_shift"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staffs.id"), index=True)
    # None means ALL working shifts for this date.  A populated value is a single shift.
    shift_type_id: Mapped[int | None] = mapped_column(ForeignKey("shift_types.id"), nullable=True, index=True)
    date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(String(255))
    staff: Mapped["Staff"] = relationship(back_populates="availability")
