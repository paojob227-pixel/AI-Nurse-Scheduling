"""Validate Pilot workbooks as a complete set before any database write."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Availability, Department, DepartmentRuleSetting, LeaveRequest, ShiftType, Staff, StaffShiftPreference
from app.services.icu_rules import RULE_LIMITS, validate_rule_set


DATASET_FILES = {"staff": "staff.xlsx", "shift": "shift.xlsx", "icu_rules": "icu_rules.xlsx", "leave": "leave.xlsx", "availability": "availability.xlsx", "preferences": "preferences.xlsx"}


@dataclass(frozen=True)
class ImportIssue:
    file: str
    row: int
    field: str
    message: str


@dataclass
class PilotDataset:
    rows: dict[str, list[dict[str, Any]]]


@dataclass
class PilotValidationReport:
    issues: list[ImportIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.issues

    def require_valid(self) -> None:
        if not self.valid:
            details = "; ".join(f"{item.file} row {item.row} ({item.field}): {item.message}" for item in self.issues)
            raise ValueError(f"Pilot dataset was not imported because validation failed: {details}")


def load_workbooks(folder: str | Path) -> PilotDataset:
    """Load the six supplied files without writing to a database."""
    root = Path(folder)
    rows: dict[str, list[dict[str, Any]]] = {}
    for name, filename in DATASET_FILES.items():
        candidates = list(root.glob(f"{Path(filename).stem}*.xlsx"))
        if not candidates:
            raise FileNotFoundError(f"Missing required Pilot workbook: {filename}")
        # Prefer the newest attachment when Downloads contains an older unnumbered copy.
        path = max(candidates, key=lambda item: item.stat().st_mtime)
        # Pilot exports can have an incorrect worksheet dimension; normal mode reads all populated cells.
        workbook = load_workbook(path, read_only=False, data_only=True)
        sheet = workbook.active
        values = list(sheet.iter_rows(values_only=True))
        if not values:
            rows[name] = []
            continue
        headers = [str(value).strip() if value is not None else "" for value in values[0]]
        rows[name] = [
            dict(zip(headers, values_row))
            for values_row in values[1:]
            if any(value is not None and str(value).strip() for value in values_row)
        ]
    return PilotDataset(rows)


def validate_dataset(dataset: PilotDataset, year: int, month: int) -> PilotValidationReport:
    report = PilotValidationReport()
    staff_codes = {str(row.get("employee_code", "")).strip() for row in dataset.rows.get("staff", []) if str(row.get("employee_code", "")).strip()}
    shift_codes = {str(row.get("shift_code", "")).strip().upper() for row in dataset.rows.get("shift", []) if str(row.get("shift_code", "")).strip()}
    if not staff_codes:
        report.issues.append(ImportIssue("staff.xlsx", 1, "employee_code", "ต้องมีบุคลากรอย่างน้อย 1 คน"))
    if not shift_codes:
        report.issues.append(ImportIssue("shift.xlsx", 1, "shift_code", "ต้องมีประเภทเวรอย่างน้อย 1 รายการ"))
    for index, row in enumerate(dataset.rows.get("staff", []), 2):
        code = str(row.get("employee_code", "")).strip()
        if not code:
            report.issues.append(ImportIssue("staff.xlsx", index, "employee_code", "ต้องระบุ employee_code"))
        if str(row.get("position", "")).strip().upper() not in {"RN", "PN", "NA", "HEAD NURSE"}:
            report.issues.append(ImportIssue("staff.xlsx", index, "position", "ตำแหน่งต้องเป็น RN, PN, NA หรือ HEAD NURSE"))
    _validate_person_rows(report, dataset.rows.get("leave", []), "leave.xlsx", "start_date", staff_codes, shift_codes, year, month, leave=True)
    _validate_person_rows(report, dataset.rows.get("availability", []), "availability.xlsx", "unavailable_date", staff_codes, shift_codes, year, month, availability=True)
    _validate_person_rows(report, dataset.rows.get("preferences", []), "preferences.xlsx", "preference_date", staff_codes, shift_codes, year, month, preference=True)
    rules: dict[str, int] = {}
    for index, row in enumerate(dataset.rows.get("icu_rules", []), 2):
        key = str(row.get("rule_key", "")).strip().upper()
        if key not in RULE_LIMITS:
            report.issues.append(ImportIssue("icu_rules.xlsx", index, "rule_key", f"ไม่รองรับ ICU rule '{key}'"))
            continue
        try:
            rules[key] = int(row.get("rule_value"))
        except (TypeError, ValueError):
            report.issues.append(ImportIssue("icu_rules.xlsx", index, "rule_value", "ต้องเป็นจำนวนเต็ม"))
    try:
        validate_rule_set(rules)
    except ValueError as error:
        report.issues.append(ImportIssue("icu_rules.xlsx", 1, "rule_value", str(error)))
    return report


def _validate_person_rows(report: PilotValidationReport, rows: list[dict[str, Any]], filename: str, date_field: str, staff_codes: set[str], shift_codes: set[str], year: int, month: int, *, leave: bool = False, availability: bool = False, preference: bool = False) -> None:
    for index, row in enumerate(rows, 2):
        code = str(row.get("employee_code", "")).strip()
        if code not in staff_codes:
            report.issues.append(ImportIssue(filename, index, "employee_code", f"ไม่พบ employee_code '{code}' ใน staff.xlsx"))
        work_date = _to_date(row.get(date_field))
        if work_date is None or work_date.year != year or work_date.month != month:
            report.issues.append(ImportIssue(filename, index, date_field, f"วันที่ต้องอยู่ในเดือน Pilot {year}-{month:02d}"))
        if leave and str(row.get("status", "")).strip().lower() not in {"approved", "pending", "rejected", "cancelled"}:
            report.issues.append(ImportIssue(filename, index, "status", "สถานะต้องเป็น approved, pending, rejected หรือ cancelled"))
        if availability:
            shift = str(row.get("unavailable_shift", "")).strip().upper()
            if shift != "ALL" and shift not in shift_codes:
                report.issues.append(ImportIssue(filename, index, "unavailable_shift", f"ไม่พบ shift_code '{shift}' ใน shift.xlsx (รองรับ ALL)"))
            if str(row.get("status", "")).strip().lower() != "unavailable":
                report.issues.append(ImportIssue(filename, index, "status", "Pilot availability ต้องมีสถานะ unavailable"))
        if preference:
            shift = str(row.get("shift_code", "")).strip().upper()
            if shift not in shift_codes:
                report.issues.append(ImportIssue(filename, index, "shift_code", f"ไม่พบ shift_code '{shift}' ใน shift.xlsx"))
            if str(row.get("preference", "")).strip().lower() not in {"prefer", "avoid"}:
                report.issues.append(ImportIssue(filename, index, "preference", "ต้องเป็น prefer หรือ avoid"))
            try:
                if not 1 <= int(row.get("weight")) <= 5:
                    raise ValueError
            except (TypeError, ValueError):
                report.issues.append(ImportIssue(filename, index, "weight", "ต้องเป็นตัวเลข 1–5"))


def _to_date(value: Any) -> date | None:
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    if isinstance(value, str):
        try: return date.fromisoformat(value)
        except ValueError: return None
    return None


def import_dataset(db: Session, department_id: int, dataset: PilotDataset, year: int, month: int) -> PilotValidationReport:
    """Apply an already-valid Pilot dataset atomically; callers must explicitly opt in."""
    report = validate_dataset(dataset, year, month)
    report.require_valid()
    with db.begin():
        if db.get(Department, department_id) is None:
            raise LookupError("Department not found")
        staff_by_code: dict[str, Staff] = {}
        for row in dataset.rows["staff"]:
            code = str(row["employee_code"]).strip()
            staff = db.scalar(select(Staff).where(Staff.employee_code == code))
            if staff is None:
                staff = Staff(employee_code=code, first_name=code, last_name="Pilot", position=str(row["position"]).strip(), department_id=department_id)
                db.add(staff)
            staff.position, staff.is_senior_rn, staff.active, staff.department_id = str(row["position"]).strip(), _to_bool(row.get("is_senior_rn")), _to_bool(row.get("active", True)), department_id
            staff_by_code[code] = staff
        db.flush()
        shifts: dict[str, ShiftType] = {}
        for row in dataset.rows["shift"]:
            code = str(row["shift_code"]).strip().upper()
            shift = db.scalar(select(ShiftType).where(ShiftType.code == code)) or ShiftType(code=code, name=str(row["shift_name"]).strip())
            shift.name, shift.start_time, shift.end_time, shift.duration_minutes, shift.category, shift.crosses_midnight = str(row["shift_name"]).strip(), _to_time(row["start_time"]), _to_time(row["end_time"]), int(row["duration_minutes"]), str(row["shift_group"]).strip(), _to_time(row["end_time"]) <= _to_time(row["start_time"])
            db.add(shift); shifts[code] = shift
        db.flush()
        for row in dataset.rows["icu_rules"]:
            key, value = str(row["rule_key"]).strip().upper(), int(row["rule_value"])
            setting = db.scalar(select(DepartmentRuleSetting).where(DepartmentRuleSetting.department_id == department_id, DepartmentRuleSetting.key == key)) or DepartmentRuleSetting(department_id=department_id, key=key)
            setting.integer_value, setting.enabled = value, True; db.add(setting)
        for row in dataset.rows["leave"]:
            staff = staff_by_code[str(row["employee_code"]).strip()]
            leave = db.scalar(select(LeaveRequest).where(LeaveRequest.staff_id == staff.id, LeaveRequest.leave_type == str(row["leave_type"]), LeaveRequest.start_date == _to_date(row["start_date"]), LeaveRequest.end_date == _to_date(row["end_date"])))
            if leave is None:
                leave = LeaveRequest(staff_id=staff.id, leave_type=str(row["leave_type"]), start_date=_to_date(row["start_date"]), end_date=_to_date(row["end_date"]))
            leave.status, leave.reason = str(row["status"]).lower(), "Pilot import"; db.add(leave)
        for row in dataset.rows["availability"]:
            staff, code = staff_by_code[str(row["employee_code"]).strip()], str(row["unavailable_shift"]).strip().upper()
            shift_id = None if code == "ALL" else shifts[code].id
            shift_scope = Availability.shift_type_id.is_(None) if shift_id is None else Availability.shift_type_id == shift_id
            availability = db.scalar(select(Availability).where(Availability.staff_id == staff.id, Availability.date == _to_date(row["unavailable_date"]), shift_scope))
            if availability is None:
                availability = Availability(staff_id=staff.id, date=_to_date(row["unavailable_date"]), shift_type_id=shift_id)
            availability.status, availability.reason = "unavailable", str(row.get("reason") or "Pilot import"); db.add(availability)
        for row in dataset.rows["preferences"]:
            staff, shift = staff_by_code[str(row["employee_code"]).strip()], shifts[str(row["shift_code"]).strip().upper()]
            preference = db.scalar(select(StaffShiftPreference).where(StaffShiftPreference.staff_id == staff.id, StaffShiftPreference.work_date == _to_date(row["preference_date"]), StaffShiftPreference.shift_type_id == shift.id, StaffShiftPreference.preference == str(row["preference"]).lower()))
            if preference is None:
                preference = StaffShiftPreference(staff_id=staff.id, work_date=_to_date(row["preference_date"]), shift_type_id=shift.id, preference=str(row["preference"]).lower())
            preference.weight, preference.reason = int(row["weight"]), str(row.get("reason") or "Pilot import"); db.add(preference)
    return report


def _to_time(value: Any) -> time:
    if isinstance(value, time): return value
    if isinstance(value, datetime): return value.time()
    return time.fromisoformat(str(value))


def _to_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)
