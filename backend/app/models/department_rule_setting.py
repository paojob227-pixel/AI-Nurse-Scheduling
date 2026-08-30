from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class DepartmentRuleSetting(Base):
    """Typed per-department scheduler configuration, ready for CP-SAT constraints."""

    __tablename__ = "department_rule_settings"
    __table_args__ = (UniqueConstraint("department_id", "key", name="uq_department_rule_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    key: Mapped[str] = mapped_column(String(100))
    integer_value: Mapped[int | None] = mapped_column(Integer)
    text_value: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
