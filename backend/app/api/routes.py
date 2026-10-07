from dataclasses import asdict
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, require_roles
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.database.database import get_db
from app.database.config import STAFF_INITIAL_PASSWORD
from app.models import AiScheduleDraft, Availability, Department, Holiday, LeaveRequest, Schedule, ScheduleAuditLog, ScheduleDetail, ScheduleValidationHistory, ShiftType, Staff, StaffShiftPreference, SystemSetting, User
from app.schemas import (
    AiDraftConversionOut, AiScheduleDraftCreate, AiScheduleDraftOut, AiScheduleDraftReject, AssignmentOut, AssignmentUpsert, AvailabilityCreate, AvailabilityOut, DepartmentCreate, DepartmentOut,
    HolidayCreate, HolidayOut, IcuRuleCreate, IcuRuleOut, IcuRuleUpdate, LeaveCreate, LeaveOut, LeaveUpdate, LoginInput, ScheduleConflictOut, ScheduleCreate, ScheduleOut, ScheduleValidationHistoryOut, ScheduleValidationOut, SchedulerDryRunOut, SchedulerDryRunRequest, SchedulerObjectiveComponentOut, SchedulerPreflightIssueOut, SchedulerPreviewAssignmentOut, SchedulerPreviewOut, SchedulerPreviewStaffWorkloadOut, SchedulerPreviewSummaryOut, SchedulerPreviewValidationOut, SchedulerPreviewValidationRequest, SchedulerPreviewExplanationOut, SchedulerPreviewExplanationRequest, SchedulerSnapshotSummaryOut,
    SettingOut, SettingUpsert, SeniorRnUpdate, ShiftTypeCreate, ShiftTypeOut, StaffCreate, StaffOut, StaffPreferenceCreate, StaffPreferenceOut, StaffPreferenceUpdate, StaffUpdate, TokenPair, TokenRefreshInput, UserOut,
)
from app.services import icu_rules
from app.services.staff_qualification import HEAD_NURSE_ALLOWED_SHIFT_CODES, StaffQualificationError, is_head_nurse, resolve_senior_rn_status
from app.services import staff_preferences
from app.services import schedule_validator
from app.services.ai_preview_validation import PreviewAssignmentInput, validate_preview
from app.services import ai_draft_approval
from app.services import ai_draft_conversion
from app.services.schedule_publish_validation import conflict_snapshot, summarize_for_publish
from app.services.database_export import export_database
from app.scheduler.snapshot_loader import load_snapshot
from app.scheduler.solver import CpSatSchedulerSolver
from app.scheduler.explanation import build_schedule_explanation


router = APIRouter(prefix="/api/v1")
MANAGERS = ("admin", "head_nurse")


@router.get("/admin/database-export")
def download_database_export(db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))) -> JSONResponse:
    """Download a read-only JSON snapshot; credential hashes are never included."""
    filename = f"ai_nurse_database_{date.today().isoformat()}.json"
    return JSONResponse(
        content=export_database(db),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def commit_or_conflict(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message) from exc


def get_own_staff_or_forbidden(db: Session, user: User) -> Staff:
    staff = db.scalar(select(Staff).where(Staff.user_id == user.id))
    if staff is None:
        raise HTTPException(status_code=403, detail="This account is not linked to a staff record")
    return staff


def icu_rule_response(setting: object) -> IcuRuleOut:
    return IcuRuleOut(
        id=setting.id,
        department_id=setting.department_id,
        key=setting.key,
        value=setting.integer_value,
        enabled=setting.enabled,
    )


def icu_rule_http_error(error: Exception) -> HTTPException:
    if isinstance(error, LookupError):
        return HTTPException(status_code=404, detail=str(error))
    return HTTPException(status_code=422, detail=str(error))


@router.post("/auth/login", response_model=TokenPair)
def login(payload: LoginInput, db: Session = Depends(get_db)) -> TokenPair:
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return TokenPair(access_token=create_token(str(user.id), user.role, "access"), refresh_token=create_token(str(user.id), user.role, "refresh"))


@router.post("/auth/refresh", response_model=TokenPair)
def refresh_token(refresh_input: TokenRefreshInput, db: Session = Depends(get_db)) -> TokenPair:
    try:
        payload = decode_token(refresh_input.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Expected a refresh token")
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive or missing user")
    return TokenPair(access_token=create_token(str(user.id), user.role, "access"), refresh_token=create_token(str(user.id), user.role, "refresh"))


@router.post("/auth/logout", status_code=204)
def logout(_: User = Depends(get_current_user)) -> None:
    """JWTs are short-lived; clients discard both tokens on logout."""
    return None


@router.get("/auth/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[Department]:
    return list(db.scalars(select(Department).order_by(Department.name)))


@router.post("/departments", response_model=DepartmentOut, status_code=201)
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> Department:
    department = Department(**payload.model_dump())
    db.add(department)
    commit_or_conflict(db, "Department name or code already exists")
    db.refresh(department)
    return department


@router.put("/departments/{department_id}", response_model=DepartmentOut)
def update_department(department_id: int, payload: DepartmentCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> Department:
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    department.name, department.code = payload.name, payload.code
    commit_or_conflict(db, "Department name or code already exists")
    return department


@router.delete("/departments/{department_id}", status_code=204)
def delete_department(department_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))) -> None:
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    db.delete(department)
    commit_or_conflict(db, "Department is still in use and cannot be deleted")


@router.get("/staff", response_model=list[StaffOut])
def list_staff(active_only: bool = True, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[Staff]:
    statement = select(Staff).order_by(Staff.employee_code)
    if active_only:
        statement = statement.where(Staff.active.is_(True))
    return list(db.scalars(statement))


@router.post("/staff", response_model=StaffOut, status_code=201)
def create_staff(payload: StaffCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> Staff:
    data = payload.model_dump(exclude={"username", "password", "role"})
    try:
        data["is_senior_rn"] = resolve_senior_rn_status(payload.position, payload.role, payload.is_senior_rn)
    except StaffQualificationError as error:
        raise HTTPException(status_code=422, detail=str(error))
    staff = Staff(**data)
    if payload.department_id and db.get(Department, payload.department_id) is None:
        raise HTTPException(status_code=404, detail="Department not found")
    if payload.username or payload.password:
        if not (payload.username and payload.password):
            raise HTTPException(status_code=422, detail="username and password must be provided together")
        if payload.role not in {"admin", "head_nurse", "nurse", "nurse_assistant"}:
            raise HTTPException(status_code=422, detail="Invalid role")
        user = User(username=payload.username, password_hash=hash_password(payload.password), role=payload.role)
        db.add(user)
        db.flush()
        staff.user_id = user.id
    else:
        if not STAFF_INITIAL_PASSWORD:
            raise HTTPException(status_code=422, detail="Automatic staff account setup requires STAFF_INITIAL_PASSWORD")
        role = payload.role if payload.role in {"head_nurse", "nurse", "nurse_assistant"} else "nurse"
        user = User(username=payload.employee_code, password_hash=hash_password(STAFF_INITIAL_PASSWORD), role=role)
        db.add(user)
        db.flush()
        staff.user_id = user.id
    db.add(staff)
    commit_or_conflict(db, "Employee code or username already exists")
    db.refresh(staff)
    return staff


@router.put("/staff/{staff_id}", response_model=StaffOut)
def update_staff(staff_id: int, payload: StaffUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> Staff:
    staff = db.get(Staff, staff_id)
    if staff is None:
        raise HTTPException(status_code=404, detail="Staff not found")
    if payload.department_id and db.get(Department, payload.department_id) is None:
        raise HTTPException(status_code=404, detail="Department not found")
    account_role = db.get(User, staff.user_id).role if staff.user_id and db.get(User, staff.user_id) else None
    try:
        update_data = payload.model_dump()
        update_data["is_senior_rn"] = resolve_senior_rn_status(payload.position, account_role, payload.is_senior_rn)
    except StaffQualificationError as error:
        raise HTTPException(status_code=422, detail=str(error))
    for key, value in update_data.items():
        setattr(staff, key, value)
    commit_or_conflict(db, "Employee code already exists")
    return staff


@router.patch("/staff/{staff_id}/senior-rn", response_model=StaffOut)
def update_senior_rn(staff_id: int, payload: SeniorRnUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> Staff:
    staff = db.get(Staff, staff_id)
    if staff is None:
        raise HTTPException(status_code=404, detail="Staff not found")
    account = db.get(User, staff.user_id) if staff.user_id else None
    try:
        staff.is_senior_rn = resolve_senior_rn_status(staff.position, account.role if account else None, payload.is_senior_rn)
    except StaffQualificationError as error:
        raise HTTPException(status_code=422, detail=str(error))
    commit_or_conflict(db, "Unable to update Senior RN status")
    return staff


@router.delete("/staff/{staff_id}", status_code=204)
def deactivate_staff(staff_id: int, db: Session = Depends(get_db), actor: User = Depends(require_roles(*MANAGERS))) -> None:
    """Safely remove a staff member from active scheduling without erasing history."""
    staff = db.get(Staff, staff_id)
    if staff is None:
        raise HTTPException(status_code=404, detail="Staff not found")
    if staff.user_id == actor.id:
        raise HTTPException(status_code=409, detail="You cannot remove your own account")
    staff.active = False
    if staff.user_id:
        account = db.get(User, staff.user_id)
        if account:
            account.is_active = False
    commit_or_conflict(db, "Unable to deactivate staff")


@router.post("/staff/{staff_id}/restore", response_model=StaffOut)
def restore_staff(staff_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> Staff:
    """Return a previously deactivated staff account to active scheduling."""
    staff = db.get(Staff, staff_id)
    if staff is None:
        raise HTTPException(status_code=404, detail="Staff not found")
    staff.active = True
    if staff.user_id:
        account = db.get(User, staff.user_id)
        if account:
            account.is_active = True
    commit_or_conflict(db, "Unable to restore staff")
    return staff


@router.get("/shift-types", response_model=list[ShiftTypeOut])
def list_shift_types(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[ShiftType]:
    return list(db.scalars(select(ShiftType).order_by(ShiftType.code)))


@router.post("/shift-types", response_model=ShiftTypeOut, status_code=201)
def create_shift_type(payload: ShiftTypeCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> ShiftType:
    shift_type = ShiftType(**payload.model_dump())
    db.add(shift_type)
    commit_or_conflict(db, "Shift code already exists")
    db.refresh(shift_type)
    return shift_type


@router.put("/shift-types/{shift_type_id}", response_model=ShiftTypeOut)
def update_shift_type(shift_type_id: int, payload: ShiftTypeCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> ShiftType:
    shift_type = db.get(ShiftType, shift_type_id)
    if shift_type is None:
        raise HTTPException(status_code=404, detail="Shift type not found")
    for key, value in payload.model_dump().items():
        setattr(shift_type, key, value)
    commit_or_conflict(db, "Shift code already exists")
    return shift_type


@router.delete("/shift-types/{shift_type_id}", status_code=204)
def delete_shift_type(shift_type_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))) -> None:
    shift_type = db.get(ShiftType, shift_type_id)
    if shift_type is None:
        raise HTTPException(status_code=404, detail="Shift type not found")
    db.delete(shift_type)
    commit_or_conflict(db, "Shift type is still in use and cannot be deleted")


@router.get("/holidays", response_model=list[HolidayOut])
def list_holidays(year: int | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[Holiday]:
    statement = select(Holiday).order_by(Holiday.date)
    if year:
        statement = statement.where(Holiday.date >= date(year, 1, 1), Holiday.date < date(year + 1, 1, 1))
    return list(db.scalars(statement))


@router.post("/holidays", response_model=HolidayOut, status_code=201)
def create_holiday(payload: HolidayCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> Holiday:
    holiday = Holiday(**payload.model_dump())
    db.add(holiday)
    commit_or_conflict(db, "Holiday date already exists")
    db.refresh(holiday)
    return holiday


@router.put("/holidays/{holiday_id}", response_model=HolidayOut)
def update_holiday(holiday_id: int, payload: HolidayCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> Holiday:
    holiday = db.get(Holiday, holiday_id)
    if holiday is None:
        raise HTTPException(status_code=404, detail="Holiday not found")
    holiday.date, holiday.name = payload.date, payload.name
    commit_or_conflict(db, "Holiday date already exists")
    return holiday


@router.delete("/holidays/{holiday_id}", status_code=204)
def delete_holiday(holiday_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> None:
    holiday = db.get(Holiday, holiday_id)
    if holiday is None:
        raise HTTPException(status_code=404, detail="Holiday not found")
    db.delete(holiday)
    commit_or_conflict(db, "Unable to delete holiday")


@router.get("/availability", response_model=list[AvailabilityOut])
def list_availability(staff_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Availability]:
    if user.role not in MANAGERS:
        staff_id = get_own_staff_or_forbidden(db, user).id
    statement = select(Availability).order_by(Availability.date)
    if staff_id:
        statement = statement.where(Availability.staff_id == staff_id)
    return list(db.scalars(statement))


@router.post("/availability", response_model=AvailabilityOut, status_code=201)
def create_availability(payload: AvailabilityCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Availability:
    staff_id = payload.staff_id if user.role in MANAGERS and payload.staff_id else get_own_staff_or_forbidden(db, user).id
    if payload.shift_type_id is not None and db.get(ShiftType, payload.shift_type_id) is None:
        raise HTTPException(status_code=404, detail="Shift type not found")
    entry = Availability(staff_id=staff_id, date=payload.date, shift_type_id=payload.shift_type_id, status=payload.status, reason=payload.reason)
    db.add(entry)
    commit_or_conflict(db, "Availability already exists for this staff, date, and shift")
    db.refresh(entry)
    return entry


@router.delete("/availability/{availability_id}", status_code=204)
def delete_availability(availability_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    entry = db.get(Availability, availability_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Availability not found")
    if user.role not in MANAGERS and entry.staff_id != get_own_staff_or_forbidden(db, user).id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    db.delete(entry)
    commit_or_conflict(db, "Unable to delete availability")


def preference_owner_or_forbidden(db: Session, preference: StaffShiftPreference, user: User) -> None:
    if user.role not in MANAGERS and preference.staff_id != get_own_staff_or_forbidden(db, user).id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.get("/staff-preferences", response_model=list[StaffPreferenceOut])
def list_staff_preferences(staff_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[StaffShiftPreference]:
    if user.role not in MANAGERS:
        staff_id = get_own_staff_or_forbidden(db, user).id
    return staff_preferences.list_preferences(db, staff_id)


@router.post("/staff-preferences", response_model=StaffPreferenceOut, status_code=201)
def create_staff_preference(payload: StaffPreferenceCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StaffShiftPreference:
    staff_id = payload.staff_id if user.role in MANAGERS and payload.staff_id else get_own_staff_or_forbidden(db, user).id
    try:
        return staff_preferences.create_preference(db, staff_id, payload.work_date, payload.shift_type_id, payload.preference, payload.weight, payload.reason)
    except staff_preferences.StaffPreferenceError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="วันนี้มีรายการความต้องการนี้อยู่แล้ว") from error


@router.put("/staff-preferences/{preference_id}", response_model=StaffPreferenceOut)
def update_staff_preference(preference_id: int, payload: StaffPreferenceUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StaffShiftPreference:
    try:
        entry = staff_preferences.get_preference(db, preference_id)
        preference_owner_or_forbidden(db, entry, user)
        return staff_preferences.update_preference(db, entry, payload.work_date, payload.shift_type_id, payload.preference, payload.weight, payload.reason)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except staff_preferences.StaffPreferenceError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="วันนี้มีรายการความต้องการนี้อยู่แล้ว") from error


@router.delete("/staff-preferences/{preference_id}", status_code=204)
def delete_staff_preference(preference_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    try:
        entry = staff_preferences.get_preference(db, preference_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    preference_owner_or_forbidden(db, entry, user)
    staff_preferences.delete_preference(db, entry)


@router.get("/leave-requests", response_model=list[LeaveOut])
def list_leave_requests(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[LeaveRequest]:
    statement = select(LeaveRequest).order_by(LeaveRequest.start_date.desc())
    if user.role not in MANAGERS:
        statement = statement.where(LeaveRequest.staff_id == get_own_staff_or_forbidden(db, user).id)
    return list(db.scalars(statement))


@router.post("/leave-requests", response_model=LeaveOut, status_code=201)
def create_leave_request(payload: LeaveCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> LeaveRequest:
    staff_id = payload.staff_id if user.role in MANAGERS and payload.staff_id else get_own_staff_or_forbidden(db, user).id
    if db.get(Staff, staff_id) is None:
        raise HTTPException(status_code=404, detail="Staff not found")
    leave_request = LeaveRequest(staff_id=staff_id, leave_type=payload.leave_type, start_date=payload.start_date, end_date=payload.end_date, reason=payload.reason)
    db.add(leave_request)
    commit_or_conflict(db, "Unable to create leave request")
    db.refresh(leave_request)
    return leave_request


@router.put("/leave-requests/{leave_id}", response_model=LeaveOut)
def update_leave_request(leave_id: int, payload: LeaveUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> LeaveRequest:
    leave_request = db.get(LeaveRequest, leave_id)
    if leave_request is None:
        raise HTTPException(status_code=404, detail="Leave request not found")
    leave_request.status = payload.status
    commit_or_conflict(db, "Unable to update leave request")
    return leave_request


@router.get("/settings", response_model=list[SettingOut])
def list_settings(db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> list[SystemSetting]:
    return list(db.scalars(select(SystemSetting).order_by(SystemSetting.key)))


@router.put("/settings/{key}", response_model=SettingOut)
def upsert_setting(key: str, payload: SettingUpsert, db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))) -> SystemSetting:
    if key != payload.key:
        raise HTTPException(status_code=422, detail="Path and payload keys must match")
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if setting is None:
        setting = SystemSetting(**payload.model_dump())
        db.add(setting)
    else:
        setting.value = payload.value
    commit_or_conflict(db, "Unable to save setting")
    db.refresh(setting)
    return setting


@router.get("/departments/{department_id}/icu-rules", response_model=list[IcuRuleOut])
def list_icu_rules(department_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> list[IcuRuleOut]:
    try:
        return [icu_rule_response(setting) for setting in icu_rules.list_rules(db, department_id)]
    except (LookupError, icu_rules.IcuRuleError) as error:
        raise icu_rule_http_error(error)


@router.get("/departments/{department_id}/icu-rules/{key}", response_model=IcuRuleOut)
def get_icu_rule(department_id: int, key: str, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> IcuRuleOut:
    try:
        return icu_rule_response(icu_rules.get_rule(db, department_id, key))
    except (LookupError, icu_rules.IcuRuleError) as error:
        raise icu_rule_http_error(error)


@router.post("/departments/{department_id}/icu-rules", response_model=IcuRuleOut, status_code=201)
def create_icu_rule(department_id: int, payload: IcuRuleCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> IcuRuleOut:
    try:
        return icu_rule_response(icu_rules.create_rule(db, department_id, payload.key, payload.value))
    except (LookupError, icu_rules.IcuRuleError) as error:
        raise icu_rule_http_error(error)


@router.put("/departments/{department_id}/icu-rules/{key}", response_model=IcuRuleOut)
def update_icu_rule(department_id: int, key: str, payload: IcuRuleUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> IcuRuleOut:
    try:
        return icu_rule_response(icu_rules.update_rule(db, department_id, key, payload.value))
    except (LookupError, icu_rules.IcuRuleError) as error:
        raise icu_rule_http_error(error)


@router.delete("/departments/{department_id}/icu-rules/{key}", status_code=204)
def delete_icu_rule(department_id: int, key: str, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> None:
    try:
        icu_rules.delete_rule(db, department_id, key)
    except (LookupError, icu_rules.IcuRuleError) as error:
        raise icu_rule_http_error(error)


@router.get("/schedules", response_model=list[ScheduleOut])
def list_schedules(department_id: int | None = None, year: int | None = None, month: int | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[Schedule]:
    statement = select(Schedule).options(selectinload(Schedule.details)).order_by(Schedule.year.desc(), Schedule.month.desc())
    if department_id:
        statement = statement.where(Schedule.department_id == department_id)
    if year:
        statement = statement.where(Schedule.year == year)
    if month:
        statement = statement.where(Schedule.month == month)
    return list(db.scalars(statement))


@router.post("/schedules", response_model=ScheduleOut, status_code=201)
def create_schedule(payload: ScheduleCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> Schedule:
    if db.get(Department, payload.department_id) is None:
        raise HTTPException(status_code=404, detail="Department not found")
    schedule = Schedule(**payload.model_dump())
    db.add(schedule)
    commit_or_conflict(db, "A schedule for this department and month already exists")
    db.refresh(schedule)
    return schedule


@router.put("/schedules/{schedule_id}/assignments", response_model=AssignmentOut)
def save_assignment(schedule_id: int, payload: AssignmentUpsert, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> ScheduleDetail:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if schedule.status == "published":
        raise HTTPException(status_code=409, detail="Published schedules cannot be edited")
    if payload.work_date.year != schedule.year or payload.work_date.month != schedule.month:
        raise HTTPException(status_code=422, detail="Assignment date must be within the schedule month")
    staff = db.get(Staff, payload.staff_id)
    if staff is None or not staff.active or staff.department_id != schedule.department_id:
        raise HTTPException(status_code=422, detail="Staff must be active and assigned to this department")
    if db.get(ShiftType, payload.shift_type_id) is None:
        raise HTTPException(status_code=404, detail="Shift type not found")
    assignment = db.scalar(select(ScheduleDetail).where(ScheduleDetail.schedule_id == schedule_id, ScheduleDetail.staff_id == payload.staff_id, ScheduleDetail.work_date == payload.work_date))
    if assignment is None:
        assignment = ScheduleDetail(schedule_id=schedule_id, staff_id=payload.staff_id, shift_type_id=payload.shift_type_id, work_date=payload.work_date, locked=payload.locked, generated=False)
        db.add(assignment)
    elif assignment.locked:
        raise HTTPException(status_code=409, detail="Assignment is locked")
    else:
        assignment.shift_type_id, assignment.locked = payload.shift_type_id, payload.locked
    schedule.validation_state = "pending"
    schedule.approval_state = "not_requested"
    commit_or_conflict(db, "Unable to save assignment")
    db.refresh(assignment)
    return assignment


@router.delete("/schedules/{schedule_id}/assignments/{assignment_id}", status_code=204)
def delete_assignment(schedule_id: int, assignment_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> None:
    assignment = db.get(ScheduleDetail, assignment_id)
    if assignment is None or assignment.schedule_id != schedule_id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.locked:
        raise HTTPException(status_code=409, detail="Assignment is locked")
    schedule = db.get(Schedule, schedule_id)
    if schedule is not None:
        schedule.validation_state = "pending"
        schedule.approval_state = "not_requested"
    db.delete(assignment)
    commit_or_conflict(db, "Unable to delete assignment")


@router.post("/schedules/{schedule_id}/publish", response_model=ScheduleOut)
def publish_schedule(schedule_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*MANAGERS))) -> Schedule:
    schedule = db.scalar(select(Schedule).options(selectinload(Schedule.details)).where(Schedule.id == schedule_id))
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if schedule.status == "published":
        raise HTTPException(status_code=409, detail="Schedule is already published")

    conflicts = list(schedule_validator.validate_schedule(db, schedule_id))
    if not schedule.details:
        from app.services.schedule_validator import Conflict
        conflicts.append(Conflict("error", "EMPTY_SCHEDULE", date(schedule.year, schedule.month, 1), "", (), (), "Cannot publish an empty schedule"))

    summary = summarize_for_publish(conflicts)
    schedule.validation_state = summary.validation_state
    schedule.approval_state = summary.approval_state
    schedule.last_validated_at = datetime.now(timezone.utc)
    schedule.last_validated_by_user_id = current_user.id
    schedule.last_error_count = summary.error_count
    schedule.last_warning_count = summary.warning_count
    db.add(ScheduleValidationHistory(
        schedule_id=schedule.id,
        validated_by_user_id=current_user.id,
        error_count=summary.error_count,
        warning_count=summary.warning_count,
        outcome=summary.outcome,
        conflicts=conflict_snapshot(conflicts),
    ))
    if summary.error_count:
        commit_or_conflict(db, "Unable to record failed publish validation")
        raise HTTPException(status_code=422, detail=f"Publish blocked: {summary.error_count} validation error(s) found")

    schedule.status = "published"
    schedule.published_at = datetime.now(timezone.utc)
    schedule.published_by_user_id = current_user.id
    commit_or_conflict(db, "Unable to publish schedule")
    return schedule


@router.post("/schedules/{schedule_id}/reopen", response_model=ScheduleOut)
def reopen_published_schedule(schedule_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*MANAGERS))) -> Schedule:
    """Create an editable revision of a published schedule while retaining an audit event."""
    schedule = db.scalar(select(Schedule).options(selectinload(Schedule.details)).where(Schedule.id == schedule_id))
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if schedule.status != "published":
        raise HTTPException(status_code=409, detail="Only a published schedule can be reopened for revision")

    before = {
        "status": schedule.status,
        "validation_state": schedule.validation_state,
        "approval_state": schedule.approval_state,
        "published_at": schedule.published_at.isoformat() if schedule.published_at else None,
    }
    schedule.status = "draft"
    schedule.validation_state = "pending"
    schedule.approval_state = "not_requested"
    schedule.last_error_count = 0
    schedule.last_warning_count = 0
    schedule.published_at = None
    schedule.published_by_user_id = None
    db.add(ScheduleAuditLog(
        schedule_id=schedule.id,
        schedule_detail_id=None,
        actor_user_id=current_user.id,
        action="REOPEN_PUBLISHED_SCHEDULE",
        before_value=before,
        after_value={"status": "draft", "validation_state": "pending", "approval_state": "not_requested"},
        reason="Published schedule reopened for a controlled revision",
    ))
    commit_or_conflict(db, "Unable to reopen published schedule")
    return schedule


@router.post("/schedules/{schedule_id}/clear-invalid-head-nurse-shifts")
def clear_invalid_head_nurse_shifts(schedule_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*MANAGERS))) -> dict[str, int]:
    """Remove pre-policy PM/N/DE assignments from Head Nurse draft schedules with an audit trail."""
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if schedule.status != "draft":
        raise HTTPException(status_code=409, detail="Reopen the published schedule before correcting Head Nurse shifts")
    rows = db.execute(
        select(ScheduleDetail, Staff, ShiftType, User)
        .join(Staff, ScheduleDetail.staff_id == Staff.id)
        .join(ShiftType, ScheduleDetail.shift_type_id == ShiftType.id)
        .outerjoin(User, Staff.user_id == User.id)
        .where(ScheduleDetail.schedule_id == schedule_id)
    ).all()
    removed_count = 0
    skipped_locked_count = 0
    for detail, staff, shift, user in rows:
        if not is_head_nurse(staff.position, user.role if user else None) or shift.code.strip().upper() in HEAD_NURSE_ALLOWED_SHIFT_CODES:
            continue
        if detail.locked:
            skipped_locked_count += 1
            continue
        db.add(ScheduleAuditLog(
            schedule_id=schedule.id,
            schedule_detail_id=None,
            actor_user_id=current_user.id,
            action="CLEAR_INVALID_HEAD_NURSE_SHIFT",
            before_value={"staff_id": staff.id, "work_date": detail.work_date.isoformat(), "shift_code": shift.code},
            after_value=None,
            reason="Head Nurse can only work AM or D shifts",
        ))
        db.delete(detail)
        removed_count += 1
    if removed_count:
        schedule.validation_state = "pending"
        schedule.approval_state = "not_requested"
    commit_or_conflict(db, "Unable to clear invalid Head Nurse shifts")
    return {"removed_count": removed_count, "skipped_locked_count": skipped_locked_count}


@router.get("/schedules/{schedule_id}/conflicts", response_model=ScheduleValidationOut)
def validate_manual_schedule(schedule_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> ScheduleValidationOut:
    try:
        conflicts = schedule_validator.validate_schedule(db, schedule_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    output = [ScheduleConflictOut(severity=item.severity, code=item.code, work_date=item.work_date, shift=item.shift, staff_ids=list(item.staff_ids), staff_names=list(item.staff_names), reason=item.reason) for item in conflicts]
    return ScheduleValidationOut(schedule_id=schedule_id, error_count=sum(item.severity == "error" for item in conflicts), warning_count=sum(item.severity == "warning" for item in conflicts), conflicts=output)


@router.get("/schedules/{schedule_id}/validation-history", response_model=list[ScheduleValidationHistoryOut])
def list_schedule_validation_history(schedule_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> list[ScheduleValidationHistory]:
    if db.get(Schedule, schedule_id) is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return list(db.scalars(select(ScheduleValidationHistory).where(ScheduleValidationHistory.schedule_id == schedule_id).order_by(ScheduleValidationHistory.created_at.desc(), ScheduleValidationHistory.id.desc())))


@router.post("/scheduler/dry-run", response_model=SchedulerDryRunOut)
def scheduler_dry_run(payload: SchedulerDryRunRequest, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> SchedulerDryRunOut:
    """Load a read-only scheduler snapshot. Phase 1 never creates assignments or publishes."""
    try:
        snapshot = load_snapshot(db, payload.department_id, payload.year, payload.month)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    result = CpSatSchedulerSolver().dry_run(snapshot)
    return SchedulerDryRunOut(
        department_id=snapshot.department_id,
        year=snapshot.year,
        month=snapshot.month,
        solver_status=result.solver_status,
        objective_value=result.objective_value,
        solve_time_seconds=result.solve_time_seconds,
        variable_count=result.variable_count,
        constraint_count=result.constraint_count,
        diagnostics=[SchedulerPreflightIssueOut(severity=item.severity, code=item.code, reason=item.reason) for item in result.diagnostics],
        will_write_schedule=False,
        will_publish_schedule=False,
        assignment_variable_count=result.assignment_variable_count,
        incharge_variable_count=result.incharge_variable_count,
        locked_assignment_constraint_count=result.locked_assignment_constraint_count,
        locked_assignment_issues=[SchedulerPreflightIssueOut(severity=item.severity, code=item.code, reason=item.reason) for item in result.locked_assignment_issues],
        approved_leave_constraint_count=result.approved_leave_constraint_count,
        approved_leave_issues=[SchedulerPreflightIssueOut(severity=item.severity, code=item.code, reason=item.reason) for item in result.approved_leave_issues],
        availability_constraint_count=result.availability_constraint_count,
        availability_issues=[SchedulerPreflightIssueOut(severity=item.severity, code=item.code, reason=item.reason) for item in result.availability_issues],
        staffing_constraint_count=result.staffing_constraint_count,
        coverage_constraint_count=result.coverage_constraint_count,
        coverage_issues=[SchedulerPreflightIssueOut(severity=item.severity, code=item.code, reason=item.reason) for item in result.coverage_issues],
        senior_rn_constraint_count=result.senior_rn_constraint_count,
        incharge_qualification_constraint_count=result.incharge_qualification_constraint_count,
        incharge_coverage_constraint_count=result.incharge_coverage_constraint_count,
        senior_incharge_issues=[SchedulerPreflightIssueOut(severity=item.severity, code=item.code, reason=item.reason) for item in result.senior_incharge_issues],
        rest_constraint_count=result.rest_constraint_count,
        overlap_constraint_count=result.overlap_constraint_count,
        multiple_shift_constraint_count=result.multiple_shift_constraint_count,
        one_shift_per_day_constraint_count=result.one_shift_per_day_constraint_count,
        rest_overlap_issues=[SchedulerPreflightIssueOut(severity=item.severity, code=item.code, reason=item.reason) for item in result.rest_overlap_issues],
        assigned_shift_count_variable_count=result.assigned_shift_count_variable_count,
        working_minutes_variable_count=result.working_minutes_variable_count,
        workload_score_variable_count=result.workload_score_variable_count,
        fairness_imbalance_variable_count=result.fairness_imbalance_variable_count,
        fairness_constraint_count=result.fairness_constraint_count,
        fairness_issues=[SchedulerPreflightIssueOut(severity=item.severity, code=item.code, reason=item.reason) for item in result.fairness_issues],
        preference_variable_count=result.preference_variable_count,
        preference_score_term_count=result.preference_score_term_count,
        preference_constraint_count=result.preference_constraint_count,
        preference_issues=[SchedulerPreflightIssueOut(severity=item.severity, code=item.code, reason=item.reason) for item in result.preference_issues],
        ot_variable_count=result.ot_variable_count,
        ot_penalty_terms=result.ot_penalty_terms,
        ot_constraint_count=result.ot_constraint_count,
        ot_diagnostics=[SchedulerPreflightIssueOut(severity=item.severity, code=item.code, reason=item.reason) for item in result.ot_diagnostics],
        objective_components={
            key: SchedulerObjectiveComponentOut(weight=weight, score_term_count=score_term_count)
            for key, weight, score_term_count in result.objective_components
        },
        objective_weights=result.objective_weights,
        total_objective_terms=result.total_objective_terms,
        snapshot=SchedulerSnapshotSummaryOut(
            staff_count=len(snapshot.staff),
            shift_count=len(snapshot.shifts),
            coverage_window_count=len(snapshot.coverage_windows),
            approved_leave_count=sum(item.status == "approved" for item in snapshot.leave_requests),
            availability_count=len(snapshot.availability),
            preference_count=len(snapshot.preferences),
            locked_assignment_count=len(snapshot.locked_assignments),
            configured_rule_count=len(snapshot.rules),
        ),
        preflight_issues=[SchedulerPreflightIssueOut(severity=item.severity, code=item.code, reason=item.reason) for item in snapshot.preflight_issues],
        notices=list(result.notices),
    )


@router.post("/scheduler/preview", response_model=SchedulerPreviewOut)
def scheduler_preview(payload: SchedulerDryRunRequest, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> SchedulerPreviewOut:
    """Return an in-memory AI solution preview; no schedule data is persisted."""
    try:
        snapshot = load_snapshot(db, payload.department_id, payload.year, payload.month)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    result = CpSatSchedulerSolver().preview(snapshot)
    summary = None if result.summary is None else SchedulerPreviewSummaryOut(
        total_staff=result.summary.total_staff,
        total_assignments=result.summary.total_assignments,
        total_working_minutes=result.summary.total_working_minutes,
        total_ot_minutes=result.summary.total_ot_minutes,
        objective_score=result.summary.objective_score,
        quality_score=result.summary.quality_score,
        fairness_score=result.summary.fairness_score,
        preference_score=result.summary.preference_score,
        ot_score=result.summary.ot_score,
        staff_workloads=[
            SchedulerPreviewStaffWorkloadOut(
                staff_id=item.staff_id, employee_code=item.employee_code, staff_name=item.staff_name,
                assigned_shift_count=item.assigned_shift_count, working_minutes=item.working_minutes,
                workload_score=item.workload_score, ot_minutes=item.ot_minutes,
            )
            for item in result.summary.staff_workloads
        ],
    )
    return SchedulerPreviewOut(
        department_id=snapshot.department_id, year=snapshot.year, month=snapshot.month,
        solver_status=result.solver_status, objective_value=result.objective_value,
        solve_time_seconds=result.solve_time_seconds, variable_count=result.variable_count,
        constraint_count=result.constraint_count,
        diagnostics=[SchedulerPreflightIssueOut(severity=item.severity, code=item.code, reason=item.reason) for item in result.diagnostics],
        assignments=[
            SchedulerPreviewAssignmentOut(
                staff_id=item.staff_id, employee_code=item.employee_code, staff_name=item.staff_name,
                work_date=item.work_date, shift_type_id=item.shift_type_id, shift_code=item.shift_code,
                is_incharge=item.is_incharge,
            )
            for item in result.assignments
        ],
        summary=summary, will_write_schedule=False, will_publish_schedule=False, notices=list(result.notices),
    )


@router.post("/scheduler/preview/validate", response_model=SchedulerPreviewValidationOut)
def validate_scheduler_preview(payload: SchedulerPreviewValidationRequest, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> SchedulerPreviewValidationOut:
    """Validate a displayed AI preview using the Manual Schedule ICU validator, read-only."""
    try:
        snapshot = load_snapshot(db, payload.department_id, payload.year, payload.month)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    conflicts = validate_preview(snapshot, tuple(
        PreviewAssignmentInput(item.staff_id, item.shift_type_id, item.work_date, item.is_incharge)
        for item in payload.assignments
    ))
    error_count = sum(item.severity == "error" for item in conflicts)
    warning_count = sum(item.severity == "warning" for item in conflicts)
    validation_status = "failed" if error_count else "passed_with_warnings" if warning_count else "passed"
    return SchedulerPreviewValidationOut(
        status=validation_status, error_count=error_count, warning_count=warning_count,
        conflicts=[ScheduleConflictOut(
            severity=item.severity, code=item.code, work_date=item.work_date, shift=item.shift,
            staff_ids=list(item.staff_ids), staff_names=list(item.staff_names), reason=item.reason,
        ) for item in conflicts],
        will_write_schedule=False, will_publish_schedule=False,
    )


@router.post("/scheduler/preview/explanation", response_model=SchedulerPreviewExplanationOut)
def explain_scheduler_preview(payload: SchedulerPreviewExplanationRequest, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> SchedulerPreviewExplanationOut:
    """Evaluate an AI preview for human review; this endpoint never writes schedule data."""
    try:
        snapshot = load_snapshot(db, payload.department_id, payload.year, payload.month)
        explanation = build_schedule_explanation(snapshot, tuple(
            PreviewAssignmentInput(item.staff_id, item.shift_type_id, item.work_date, item.is_incharge)
            for item in payload.assignments
        ))
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return SchedulerPreviewExplanationOut(
        **asdict(explanation), will_write_schedule=False, will_publish_schedule=False,
    )


@router.get("/ai-schedule-drafts", response_model=list[AiScheduleDraftOut])
def list_ai_schedule_drafts(department_id: int | None = None, year: int | None = None, month: int | None = None, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))) -> list[AiScheduleDraft]:
    statement = select(AiScheduleDraft).options(selectinload(AiScheduleDraft.details)).order_by(AiScheduleDraft.created_at.desc(), AiScheduleDraft.id.desc())
    if department_id is not None:
        statement = statement.where(AiScheduleDraft.department_id == department_id)
    if year is not None:
        statement = statement.where(AiScheduleDraft.year == year)
    if month is not None:
        statement = statement.where(AiScheduleDraft.month == month)
    return list(db.scalars(statement))


@router.post("/ai-schedule-drafts", response_model=AiScheduleDraftOut, status_code=201)
def create_ai_schedule_draft(payload: AiScheduleDraftCreate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*MANAGERS))) -> AiScheduleDraft:
    try:
        snapshot = load_snapshot(db, payload.department_id, payload.year, payload.month)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    draft = ai_draft_approval.create_draft(
        db, snapshot, current_user, payload.solver_status, payload.objective_score,
        tuple(PreviewAssignmentInput(item.staff_id, item.shift_type_id, item.work_date, item.is_incharge) for item in payload.assignments),
    )
    commit_or_conflict(db, "Unable to store AI schedule draft")
    return db.scalar(select(AiScheduleDraft).options(selectinload(AiScheduleDraft.details)).where(AiScheduleDraft.id == draft.id))


def get_ai_draft_or_404(db: Session, draft_id: int) -> AiScheduleDraft:
    draft = db.scalar(select(AiScheduleDraft).options(selectinload(AiScheduleDraft.details)).where(AiScheduleDraft.id == draft_id))
    if draft is None:
        raise HTTPException(status_code=404, detail="AI schedule draft not found")
    return draft


@router.post("/ai-schedule-drafts/{draft_id}/submit", response_model=AiScheduleDraftOut)
def submit_ai_schedule_draft(draft_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*MANAGERS))) -> AiScheduleDraft:
    try:
        draft = ai_draft_approval.submit_for_approval(get_ai_draft_or_404(db, draft_id), current_user)
    except ai_draft_approval.AiDraftApprovalError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    commit_or_conflict(db, "Unable to submit AI schedule draft for approval")
    return draft


@router.post("/ai-schedule-drafts/{draft_id}/approve", response_model=AiScheduleDraftOut)
def approve_ai_schedule_draft(draft_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles("head_nurse"))) -> AiScheduleDraft:
    try:
        draft = ai_draft_approval.approve_draft(get_ai_draft_or_404(db, draft_id), current_user)
    except ai_draft_approval.AiDraftApprovalError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    commit_or_conflict(db, "Unable to approve AI schedule draft")
    return draft


@router.post("/ai-schedule-drafts/{draft_id}/reject", response_model=AiScheduleDraftOut)
def reject_ai_schedule_draft(draft_id: int, payload: AiScheduleDraftReject, db: Session = Depends(get_db), current_user: User = Depends(require_roles("head_nurse"))) -> AiScheduleDraft:
    try:
        draft = ai_draft_approval.reject_draft(get_ai_draft_or_404(db, draft_id), current_user, payload.reason)
    except ai_draft_approval.AiDraftApprovalError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    commit_or_conflict(db, "Unable to reject AI schedule draft")
    return draft


@router.post("/ai-schedule-drafts/{draft_id}/convert", response_model=AiDraftConversionOut)
def convert_ai_schedule_draft(draft_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles("head_nurse"))) -> AiDraftConversionOut:
    try:
        schedule, conflicts = ai_draft_conversion.convert_approved_draft(db, get_ai_draft_or_404(db, draft_id), current_user)
    except ai_draft_conversion.AiDraftConversionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    commit_or_conflict(db, "Unable to convert AI draft to Manual Schedule")
    return AiDraftConversionOut(
        schedule_id=schedule.id, status="draft", source="AI_GENERATED", validation_ran=True,
        error_count=sum(item.severity == "error" for item in conflicts), warning_count=sum(item.severity == "warning" for item in conflicts),
        conflicts=[ScheduleConflictOut(severity=item.severity, code=item.code, work_date=item.work_date, shift=item.shift, staff_ids=list(item.staff_ids), staff_names=list(item.staff_names), reason=item.reason) for item in conflicts],
        will_publish_schedule=False,
    )


@router.post("/ai-schedule-drafts/{draft_id}/convert-replace-draft", response_model=AiDraftConversionOut)
def convert_replace_ai_schedule_draft(draft_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles("head_nurse"))) -> AiDraftConversionOut:
    """Explicitly replace only an existing AI-generated draft; published/manual schedules remain protected."""
    try:
        schedule, conflicts = ai_draft_conversion.convert_approved_draft(
            db, get_ai_draft_or_404(db, draft_id), current_user, replace_existing_ai_draft=True,
        )
    except ai_draft_conversion.AiDraftConversionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    commit_or_conflict(db, "Unable to replace AI Schedule draft")
    return AiDraftConversionOut(
        schedule_id=schedule.id, status="draft", source="AI_GENERATED", validation_ran=True,
        error_count=sum(item.severity == "error" for item in conflicts), warning_count=sum(item.severity == "warning" for item in conflicts),
        conflicts=[ScheduleConflictOut(severity=item.severity, code=item.code, work_date=item.work_date, shift=item.shift, staff_ids=list(item.staff_ids), staff_names=list(item.staff_names), reason=item.reason) for item in conflicts],
        will_publish_schedule=False,
    )


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict[str, int]:
    today = date.today()
    return {
        "active_staff": db.scalar(select(func.count()).select_from(Staff).where(Staff.active.is_(True))) or 0,
        "pending_leave_requests": db.scalar(select(func.count()).select_from(LeaveRequest).where(LeaveRequest.status == "pending")) or 0,
        "today_assignments": db.scalar(select(func.count()).select_from(ScheduleDetail).where(ScheduleDetail.work_date == today)) or 0,
    }


@router.get("/dashboard/my-shift")
def my_shift_today(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, object]:
    """Return the signed-in staff member's assignment and Senior RN colleagues for today."""
    today = date.today()
    row = db.execute(
        select(ScheduleDetail, Schedule, ShiftType)
        .join(Schedule, Schedule.id == ScheduleDetail.schedule_id)
        .join(ShiftType, ShiftType.id == ScheduleDetail.shift_type_id)
        .join(Staff, Staff.id == ScheduleDetail.staff_id)
        .where(Staff.user_id == current_user.id, ScheduleDetail.work_date == today)
        .order_by(Schedule.status.desc())
    ).first()
    if row is None:
        return {"date": today.isoformat(), "assignment": None, "senior_rns": []}

    assignment, schedule, shift = row
    senior_rows = list(db.execute(
        select(Staff, ShiftType)
        .join(ScheduleDetail, ScheduleDetail.staff_id == Staff.id)
        .join(ShiftType, ShiftType.id == ScheduleDetail.shift_type_id)
        .where(
            ScheduleDetail.schedule_id == schedule.id,
            ScheduleDetail.work_date == today,
            Staff.is_senior_rn.is_(True),
        )
        .order_by(Staff.employee_code)
    ))

    def minutes(value: object) -> int:
        return value.hour * 60 + value.minute  # type: ignore[union-attr]

    def intervals(item: ShiftType) -> tuple[tuple[int, int], ...]:
        if item.start_time is None or item.end_time is None:
            return ()
        start, end = minutes(item.start_time), minutes(item.end_time)
        if item.crosses_midnight or end <= start:
            return ((start, 24 * 60), (0, end))
        return ((start, end),)

    current_intervals = intervals(shift)
    covering_seniors = [
        (staff, senior_shift)
        for staff, senior_shift in senior_rows
        if any(start < other_end and other_start < end for start, end in current_intervals for other_start, other_end in intervals(senior_shift))
    ]
    time_range = "ไม่ระบุเวลา"
    if shift.start_time and shift.end_time:
        time_range = f"{shift.start_time.strftime('%H:%M')}–{shift.end_time.strftime('%H:%M')}"
        if shift.crosses_midnight:
            time_range += " (ถึงวันถัดไป)"

    return {
        "date": today.isoformat(),
        "assignment": {
            "shift_code": shift.code,
            "shift_name": shift.name,
            "time_range": time_range,
            "is_incharge": assignment.is_incharge,
            "schedule_status": schedule.status,
        },
        "senior_rns": [
            {"employee_code": staff.employee_code, "name": f"{staff.first_name} {staff.last_name}", "shift_code": senior_shift.code}
            for staff, senior_shift in covering_seniors
        ],
    }
