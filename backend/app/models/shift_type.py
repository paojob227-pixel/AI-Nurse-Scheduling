from datetime import time

from sqlalchemy import Boolean, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class ShiftType(Base):
    __tablename__ = "shift_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    is_working_shift: Mapped[bool] = mapped_column(Boolean, default=True)
    duration_minutes: Mapped[int | None] = mapped_column()
    category: Mapped[str | None] = mapped_column(String(20))
    crosses_midnight: Mapped[bool] = mapped_column(Boolean, default=False)
