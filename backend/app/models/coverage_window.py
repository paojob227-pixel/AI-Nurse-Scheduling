from datetime import time

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class CoverageWindow(Base):
    """Minimum ICU staffing required for a real time window, not merely a shift code."""

    __tablename__ = "coverage_windows"
    __table_args__ = (
        UniqueConstraint("department_id", "code", name="uq_coverage_window_department_code"),
        CheckConstraint("min_rn >= 0 AND max_rn >= min_rn", name="ck_coverage_window_rn_bounds"),
        CheckConstraint("min_support_staff >= 0 AND min_senior_rn >= 0", name="ck_coverage_window_minimums"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    crosses_midnight: Mapped[bool] = mapped_column(Boolean, default=False)
    min_rn: Mapped[int] = mapped_column(Integer, default=3)
    max_rn: Mapped[int] = mapped_column(Integer, default=4)
    min_support_staff: Mapped[int] = mapped_column(Integer, default=1)
    min_senior_rn: Mapped[int] = mapped_column(Integer, default=1)


class CoverageWindowShiftType(Base):
    """Maps the shifts that contribute to a real-time coverage window."""

    __tablename__ = "coverage_window_shift_types"

    coverage_window_id: Mapped[int] = mapped_column(ForeignKey("coverage_windows.id"), primary_key=True)
    shift_type_id: Mapped[int] = mapped_column(ForeignKey("shift_types.id"), primary_key=True)
