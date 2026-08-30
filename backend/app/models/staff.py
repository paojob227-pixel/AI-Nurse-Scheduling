from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class Staff(Base):
    __tablename__ = "staffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    position: Mapped[str] = mapped_column(String(50))
    skill_level: Mapped[str | None] = mapped_column(String(30))
    is_senior_rn: Mapped[bool] = mapped_column(Boolean, default=False)
    employment_type: Mapped[str] = mapped_column(String(30), default="full_time")
    start_date: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True)

    department: Mapped["Department | None"] = relationship(back_populates="staffs")
    user: Mapped["User | None"] = relationship(back_populates="staff")
    availability: Mapped[list["Availability"]] = relationship(back_populates="staff", cascade="all, delete-orphan")
    leave_requests: Mapped[list["LeaveRequest"]] = relationship(back_populates="staff")
    schedule_details: Mapped[list["ScheduleDetail"]] = relationship(back_populates="staff")
    shift_preferences: Mapped[list["StaffShiftPreference"]] = relationship(back_populates="staff", cascade="all, delete-orphan")
