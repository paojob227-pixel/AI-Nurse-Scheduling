"""Validation and persistence helpers for future scheduling soft constraints."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ShiftType, Staff, StaffShiftPreference


class StaffPreferenceError(ValueError):
    """Raised when a preference cannot become a safe scheduling input."""


def validate_preference(preference: str, weight: int) -> None:
    if preference not in {"prefer", "avoid"}:
        raise StaffPreferenceError("Preference must be either 'prefer' or 'avoid'")
    if not 1 <= weight <= 5:
        raise StaffPreferenceError("Preference weight must be between 1 and 5")


def validate_staff_and_shift(db: Session, staff_id: int, shift_type_id: int | None) -> None:
    staff = db.get(Staff, staff_id)
    if staff is None or not staff.active:
        raise StaffPreferenceError("Staff must exist and be active")
    if shift_type_id is None:
        return
    shift_type = db.get(ShiftType, shift_type_id)
    if shift_type is None or not shift_type.is_working_shift:
        raise StaffPreferenceError("Preference must reference an active working shift")


def list_preferences(db: Session, staff_id: int | None = None) -> list[StaffShiftPreference]:
    statement = select(StaffShiftPreference).order_by(StaffShiftPreference.work_date, StaffShiftPreference.created_at)
    if staff_id is not None:
        statement = statement.where(StaffShiftPreference.staff_id == staff_id)
    return list(db.scalars(statement))


def get_preference(db: Session, preference_id: int) -> StaffShiftPreference:
    preference = db.get(StaffShiftPreference, preference_id)
    if preference is None:
        raise LookupError("Staff preference not found")
    return preference


def _normalised_shift_type_id(preference: str, weight: int, shift_type_id: int | None) -> int | None:
    """Priority-5 avoid requests always mean unavailable for the whole day."""
    if preference == "avoid" and weight == 5:
        return None
    if weight == 5:
        raise StaffPreferenceError("Weight 5 is reserved for an avoid request that blocks every shift that day")
    if shift_type_id is None:
        raise StaffPreferenceError("A shift is required unless this is an avoid request with weight 5")
    return shift_type_id


def _assert_no_duplicate_all_day_preference(db: Session, staff_id: int, work_date: object, *, exclude_id: int | None = None) -> None:
    statement = select(StaffShiftPreference.id).where(
        StaffShiftPreference.staff_id == staff_id,
        StaffShiftPreference.work_date == work_date,
        StaffShiftPreference.preference == "avoid",
        StaffShiftPreference.weight == 5,
    )
    if exclude_id is not None:
        statement = statement.where(StaffShiftPreference.id != exclude_id)
    if db.scalar(statement) is not None:
        raise StaffPreferenceError("An all-day unavailable preference already exists for this date")


def create_preference(db: Session, staff_id: int, work_date: object, shift_type_id: int | None, preference: str, weight: int, reason: str | None) -> StaffShiftPreference:
    shift_type_id = _normalised_shift_type_id(preference, weight, shift_type_id)
    validate_preference(preference, weight)
    validate_staff_and_shift(db, staff_id, shift_type_id)
    if shift_type_id is None:
        _assert_no_duplicate_all_day_preference(db, staff_id, work_date)
    entry = StaffShiftPreference(staff_id=staff_id, work_date=work_date, shift_type_id=shift_type_id, preference=preference, weight=weight, reason=reason)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def update_preference(db: Session, entry: StaffShiftPreference, work_date: object, shift_type_id: int | None, preference: str, weight: int, reason: str | None) -> StaffShiftPreference:
    shift_type_id = _normalised_shift_type_id(preference, weight, shift_type_id)
    validate_preference(preference, weight)
    validate_staff_and_shift(db, entry.staff_id, shift_type_id)
    if shift_type_id is None:
        _assert_no_duplicate_all_day_preference(db, entry.staff_id, work_date, exclude_id=entry.id)
    entry.work_date, entry.shift_type_id, entry.preference, entry.weight, entry.reason = work_date, shift_type_id, preference, weight, reason
    db.commit()
    db.refresh(entry)
    return entry


def delete_preference(db: Session, entry: StaffShiftPreference) -> None:
    db.delete(entry)
    db.commit()
