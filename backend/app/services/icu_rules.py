"""Business rules for department-level ICU scheduler configuration.

This module intentionally stores configuration only. It does not create an AI
schedule or import an optimization library.
"""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Department, DepartmentRuleSetting


RULE_LIMITS: dict[str, tuple[int, int]] = {
    "MIN_RN": (1, 20),
    "MAX_RN": (1, 20),
    "MIN_SUPPORT": (0, 20),
    "REST_AFTER_NIGHT": (1, 24),
    "MONTHLY_HOURS": (1, 744),
    "OT_THRESHOLD": (1, 744),
}


class IcuRuleError(ValueError):
    """Raised when a proposed ICU setting violates configuration rules."""


def validate_rule_value(key: str, value: int) -> None:
    if key not in RULE_LIMITS:
        raise IcuRuleError(f"Unsupported ICU rule: {key}")
    minimum, maximum = RULE_LIMITS[key]
    if not minimum <= value <= maximum:
        raise IcuRuleError(f"{key} must be between {minimum} and {maximum}")


def ensure_supported_rule(key: str) -> None:
    if key not in RULE_LIMITS:
        raise IcuRuleError(f"Unsupported ICU rule: {key}")


def validate_rule_set(values: dict[str, int]) -> None:
    for key, value in values.items():
        validate_rule_value(key, value)
    if "MIN_RN" in values and "MAX_RN" in values and values["MIN_RN"] > values["MAX_RN"]:
        raise IcuRuleError("MIN_RN must not exceed MAX_RN")
    if "MONTHLY_HOURS" in values and "OT_THRESHOLD" in values and values["OT_THRESHOLD"] < values["MONTHLY_HOURS"]:
        raise IcuRuleError("OT_THRESHOLD must be greater than or equal to MONTHLY_HOURS")


def _department_or_error(db: Session, department_id: int) -> Department:
    department = db.get(Department, department_id)
    if department is None:
        raise LookupError("Department not found")
    return department


def _current_values(db: Session, department_id: int) -> dict[str, int]:
    settings: Iterable[DepartmentRuleSetting] = db.scalars(
        select(DepartmentRuleSetting).where(
            DepartmentRuleSetting.department_id == department_id,
            DepartmentRuleSetting.key.in_(RULE_LIMITS),
        )
    )
    return {setting.key: setting.integer_value for setting in settings if setting.integer_value is not None}


def list_rules(db: Session, department_id: int) -> list[DepartmentRuleSetting]:
    _department_or_error(db, department_id)
    return list(db.scalars(select(DepartmentRuleSetting).where(DepartmentRuleSetting.department_id == department_id, DepartmentRuleSetting.key.in_(RULE_LIMITS)).order_by(DepartmentRuleSetting.key)))


def get_rule(db: Session, department_id: int, key: str) -> DepartmentRuleSetting:
    ensure_supported_rule(key)
    _department_or_error(db, department_id)
    setting = db.scalar(select(DepartmentRuleSetting).where(DepartmentRuleSetting.department_id == department_id, DepartmentRuleSetting.key == key))
    if setting is None:
        raise LookupError("ICU rule not found")
    return setting


def create_rule(db: Session, department_id: int, key: str, value: int) -> DepartmentRuleSetting:
    _department_or_error(db, department_id)
    current = _current_values(db, department_id)
    if db.scalar(select(DepartmentRuleSetting).where(DepartmentRuleSetting.department_id == department_id, DepartmentRuleSetting.key == key)) is not None:
        raise IcuRuleError("ICU rule already exists; use PUT to change it")
    validate_rule_set({**current, key: value})
    setting = DepartmentRuleSetting(department_id=department_id, key=key, integer_value=value, enabled=True)
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


def update_rule(db: Session, department_id: int, key: str, value: int) -> DepartmentRuleSetting:
    setting = get_rule(db, department_id, key)
    current = _current_values(db, department_id)
    validate_rule_set({**current, key: value})
    setting.integer_value = value
    setting.enabled = True
    db.commit()
    db.refresh(setting)
    return setting


def delete_rule(db: Session, department_id: int, key: str) -> None:
    setting = get_rule(db, department_id, key)
    db.delete(setting)
    db.commit()
