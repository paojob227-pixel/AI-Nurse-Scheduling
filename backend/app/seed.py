"""Seed the minimum safe local-development data set after migrations."""

import os
from datetime import time

from sqlalchemy import select

from app.core.security import hash_password
from app.database.database import SessionLocal
from app.models import CoverageWindow, CoverageWindowShiftType, Department, DepartmentRuleSetting, ShiftType, SystemSetting, User


def seed() -> None:
    password = os.getenv("ADMIN_INITIAL_PASSWORD")
    if not password:
        raise RuntimeError("Set ADMIN_INITIAL_PASSWORD before running the seed command")
    db = SessionLocal()
    try:
        admin = db.scalar(select(User).where(User.username == "admin"))
        if admin is None:
            db.add(User(username="admin", password_hash=hash_password(password), role="admin"))
        else:
            # Keep the deployment credential and the stored account in sync. This
            # also repairs a database created by an earlier failed deployment.
            admin.password_hash = hash_password(password)
        department = db.scalar(select(Department).where(Department.code == "ICU"))
        if department is None:
            department = Department(name="Intensive Care Unit", code="ICU")
            db.add(department)
            db.flush()
        shift_defaults = [
            ("AM", "Morning Shift", time(7), time(15), 480, "normal", False, True),
            ("PM", "Afternoon Shift", time(15), time(23), 480, "normal", False, True),
            ("N", "Night Shift", time(23), time(7), 480, "normal", True, True),
            ("D", "Day Shift", time(7), time(19), 720, "extended", False, True),
            ("DE", "Day Night Shift", time(19), time(7), 720, "extended", True, True),
            ("OFF", "Off", None, None, None, None, False, False),
        ]
        for code, name, start, end, duration, category, crosses_midnight, working in shift_defaults:
            if db.scalar(select(ShiftType).where(ShiftType.code == code)) is None:
                db.add(ShiftType(code=code, name=name, start_time=start, end_time=end, duration_minutes=duration, category=category, crosses_midnight=crosses_midnight, is_working_shift=working))
        db.flush()
        defaults = {"max_night_shifts": "8", "max_consecutive_work_days": "6", "minimum_rn_per_shift": "3", "minimum_support_staff_per_window": "1"}
        for key, value in defaults.items():
            if db.scalar(select(SystemSetting).where(SystemSetting.key == key)) is None:
                db.add(SystemSetting(key=key, value=value))
        rule_defaults = {"minimum_rest_hours": 8, "max_consecutive_work_days": 6, "max_consecutive_night_shifts": 3, "monthly_standard_hours": 168, "max_night_shifts_per_month": 8}
        for key, value in rule_defaults.items():
            if db.scalar(select(DepartmentRuleSetting).where(DepartmentRuleSetting.department_id == department.id, DepartmentRuleSetting.key == key)) is None:
                db.add(DepartmentRuleSetting(department_id=department.id, key=key, integer_value=value))
        coverage_defaults = [("07-15", time(7), time(15), False, ("AM", "D")), ("15-19", time(15), time(19), False, ("PM", "D")), ("19-23", time(19), time(23), False, ("PM", "DE")), ("23-07", time(23), time(7), True, ("N", "DE"))]
        for code, start, end, crosses_midnight, shift_codes in coverage_defaults:
            window = db.scalar(select(CoverageWindow).where(CoverageWindow.department_id == department.id, CoverageWindow.code == code))
            if window is None:
                window = CoverageWindow(department_id=department.id, code=code, start_time=start, end_time=end, crosses_midnight=crosses_midnight, min_rn=3, max_rn=4, min_support_staff=1, min_senior_rn=1)
                db.add(window)
                db.flush()
            for shift_code in shift_codes:
                shift_type = db.scalar(select(ShiftType).where(ShiftType.code == shift_code))
                if shift_type and db.get(CoverageWindowShiftType, {"coverage_window_id": window.id, "shift_type_id": shift_type.id}) is None:
                    db.add(CoverageWindowShiftType(coverage_window_id=window.id, shift_type_id=shift_type.id))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
