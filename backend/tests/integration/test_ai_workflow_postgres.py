"""Phase 3.3 end-to-end API tests against an explicitly configured PostgreSQL test DB."""

import os
import unittest
from datetime import date
from urllib.parse import urlparse

from fastapi.testclient import TestClient
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.database.database import get_db
from app.main import app
from app.models import (
    AiScheduleDraft, AiScheduleDraftDetail, Availability, CoverageWindow,
    CoverageWindowShiftType, Department, DepartmentRuleSetting, LeaveRequest,
    Schedule, ScheduleDetail, ShiftType, Staff, StaffShiftPreference, User,
)
from app.simulation.dataset_generator import build_snapshot
from app.pilot_preparation import build_pilot_audit_verification


INTEGRATION_DATABASE_URL = os.getenv("INTEGRATION_DATABASE_URL", "")


def _is_safe_test_database(url: str) -> bool:
    database_name = urlparse(url).path.rsplit("/", 1)[-1]
    # Keep destructive integration fixtures away from a locally running Pilot
    # app.  ``nurse_schedule_pilot_test`` is a local Pilot database, not a
    # disposable test fixture.
    return bool(database_name) and database_name.endswith("_integration_test")


@unittest.skipUnless(INTEGRATION_DATABASE_URL, "Set INTEGRATION_DATABASE_URL to run PostgreSQL integration tests")
class AiWorkflowPostgresIntegrationTests(unittest.TestCase):
    """All persistent actions are isolated to a database explicitly named *_test."""

    @classmethod
    def setUpClass(cls) -> None:
        if not _is_safe_test_database(INTEGRATION_DATABASE_URL):
            raise RuntimeError("INTEGRATION_DATABASE_URL must name a disposable database ending in _integration_test")
        cls.engine = create_engine(INTEGRATION_DATABASE_URL, pool_pre_ping=True)
        cls.Session = sessionmaker(bind=cls.engine, autocommit=False, autoflush=False, expire_on_commit=False)
        with cls.engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != ScriptDirectory.from_config(Config("alembic.ini")).get_current_head():
            raise RuntimeError("Run `python -m alembic upgrade head` against the integration test database first")

        def override_get_db():
            db = cls.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.pop(get_db, None)
        cls.client.close()
        cls.engine.dispose()

    def setUp(self) -> None:
        self._truncate_test_data()
        self.ids = self._seed_simulation_data()
        self.admin_headers = self._headers_for("integration_admin", "integration-password")
        self.head_nurse_headers = self._headers_for("integration_head_nurse", "integration-password")
        self.nurse_headers = self._headers_for("integration_nurse", "integration-password")

    def _truncate_test_data(self) -> None:
        tables = (
            "schedule_validation_history, schedule_audit_logs, schedule_details, "
            "ai_schedule_draft_details, ai_schedule_drafts, schedules, leave_requests, "
            "availability, staff_shift_preferences, coverage_window_shift_types, coverage_windows, "
            "department_rule_settings, staffs, shift_types, departments, users"
        )
        with self.engine.begin() as connection:
            connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))

    def _seed_simulation_data(self) -> dict[str, int]:
        """Persist the same staff/rules/leave/preference/lock shape used by Phase 3.1."""
        snapshot = build_snapshot()
        db: Session = self.Session()
        try:
            department = Department(name="ICU Integration Test", code="ICU_IT")
            db.add(department)
            db.flush()
            shifts = [ShiftType(code=item.code, name=f"Integration {item.code}", start_time=item.start_time, end_time=item.end_time, duration_minutes=item.duration_minutes, category="normal", crosses_midnight=item.crosses_midnight, is_working_shift=True) for item in snapshot.shifts]
            db.add_all(shifts)
            db.flush()
            shift_id_by_code = {item.code: item.id for item in shifts}
            staff_rows = [Staff(employee_code=item.employee_code, first_name=item.display_name.split(" ")[0], last_name=item.display_name.split(" ")[-1], position=item.position, skill_level=None, is_senior_rn=item.is_senior_rn, active=True, department_id=department.id) for item in snapshot.staff]
            db.add_all(staff_rows)
            db.flush()
            staff_id_by_code = {item.employee_code: item.id for item in staff_rows}
            db.add_all(DepartmentRuleSetting(department_id=department.id, key=key, integer_value=value, enabled=True) for key, value in snapshot.rules.items())
            windows = [CoverageWindow(department_id=department.id, code=item.code, start_time=item.start_time, end_time=item.end_time, crosses_midnight=item.crosses_midnight, min_rn=item.min_rn, max_rn=item.max_rn, min_support_staff=item.min_support_staff, min_senior_rn=item.min_senior_rn) for item in snapshot.coverage_windows]
            db.add_all(windows)
            db.flush()
            for window, source in zip(windows, snapshot.coverage_windows, strict=True):
                for shift_type_id in source.shift_type_ids:
                    source_code = next(item.code for item in snapshot.shifts if item.id == shift_type_id)
                    db.add(CoverageWindowShiftType(coverage_window_id=window.id, shift_type_id=shift_id_by_code[source_code]))
            source_staff_by_id = {item.id: item.employee_code for item in snapshot.staff}
            source_shift_by_id = {item.id: item.code for item in snapshot.shifts}
            db.add_all(LeaveRequest(staff_id=staff_id_by_code[source_staff_by_id[item.staff_id]], leave_type="annual", start_date=item.start_date, end_date=item.end_date, reason="integration fixture", status=item.status) for item in snapshot.leave_requests)
            db.add_all(Availability(staff_id=staff_id_by_code[source_staff_by_id[item.staff_id]], date=item.work_date, status=item.status, reason="integration fixture") for item in snapshot.availability)
            db.add_all(StaffShiftPreference(staff_id=staff_id_by_code[source_staff_by_id[item.staff_id]], work_date=item.work_date, shift_type_id=shift_id_by_code[source_shift_by_id[item.shift_type_id]], preference=item.preference, weight=item.weight, reason="integration fixture") for item in snapshot.preferences)
            users = [
                User(username="integration_admin", password_hash=hash_password("integration-password"), role="admin"),
                User(username="integration_head_nurse", password_hash=hash_password("integration-password"), role="head_nurse"),
                User(username="integration_nurse", password_hash=hash_password("integration-password"), role="nurse"),
            ]
            db.add_all(users)
            db.commit()
            return {"department_id": department.id, "rn001_id": staff_id_by_code["RN001"], "am_shift_id": shift_id_by_code["AM"], "admin_id": users[0].id}
        finally:
            db.close()

    def _headers_for(self, username: str, password: str) -> dict[str, str]:
        response = self.client.post("/api/v1/auth/login", json={"username": username, "password": password})
        self.assertEqual(response.status_code, 200, response.text)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def _preview(self) -> dict[str, object]:
        response = self.client.post("/api/v1/scheduler/preview", headers=self.admin_headers, json={"department_id": self.ids["department_id"], "year": 2026, "month": 8})
        self.assertEqual(response.status_code, 200, response.text)
        preview = response.json()
        self.assertIn(preview["solver_status"], {"FEASIBLE", "OPTIMAL"})
        self.assertGreater(len(preview["assignments"]), 0)
        return preview

    @staticmethod
    def _draft_payload(preview: dict[str, object], department_id: int) -> dict[str, object]:
        return {
            "department_id": department_id, "year": 2026, "month": 8,
            "solver_status": preview["solver_status"], "objective_score": preview["summary"]["objective_score"],
            "assignments": [{key: item[key] for key in ("staff_id", "shift_type_id", "work_date", "is_incharge")} for item in preview["assignments"]],
        }

    def _create_approved_draft(self, status: str = "APPROVED", approval_status: str = "approved") -> int:
        db: Session = self.Session()
        try:
            draft = AiScheduleDraft(department_id=self.ids["department_id"], year=2026, month=8, created_by_user_id=self.ids["admin_id"], solver_status="FEASIBLE", objective_score=0, status=status, validation_status="passed", validation_error_count=0, validation_warning_count=0, validation_conflicts=[], approval_status=approval_status)
            db.add(draft)
            db.flush()
            db.add(AiScheduleDraftDetail(draft_id=draft.id, staff_id=self.ids["rn001_id"], shift_type_id=self.ids["am_shift_id"], work_date=date(2026, 8, 1), is_incharge=True))
            db.commit()
            return draft.id
        finally:
            db.close()

    def test_preview_uses_simulation_data_and_does_not_create_an_ai_schedule(self) -> None:
        db: Session = self.Session()
        try:
            manual = Schedule(department_id=self.ids["department_id"], year=2026, month=8, status="draft", source="MANUAL")
            db.add(manual)
            db.flush()
            db.add(ScheduleDetail(schedule_id=manual.id, staff_id=self.ids["rn001_id"], shift_type_id=self.ids["am_shift_id"], work_date=date(2026, 8, 1), locked=True, generated=False, is_incharge=True))
            db.commit()
        finally:
            db.close()
        preview = self._preview()
        self.assertTrue(any(item["is_incharge"] for item in preview["assignments"]))
        db = self.Session()
        try:
            self.assertEqual(db.scalar(select(func.count()).select_from(Schedule)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(Schedule).where(Schedule.source == "AI_GENERATED")), 0)
        finally:
            db.close()

    def test_full_generate_validate_submit_approve_convert_validate_and_publish_workflow(self) -> None:
        empty = self.client.post("/api/v1/schedules", headers=self.head_nurse_headers, json={"department_id": self.ids["department_id"], "year": 2026, "month": 8})
        self.assertEqual(empty.status_code, 201, empty.text)
        preview = self._preview()
        assignments = self._draft_payload(preview, self.ids["department_id"])["assignments"]
        validation = self.client.post("/api/v1/scheduler/preview/validate", headers=self.admin_headers, json={"department_id": self.ids["department_id"], "year": 2026, "month": 8, "assignments": assignments})
        self.assertEqual(validation.status_code, 200, validation.text)
        self.assertIn(validation.json()["status"], {"passed", "passed_with_warnings"})
        self.assertEqual(validation.json()["error_count"], 0)

        created = self.client.post("/api/v1/ai-schedule-drafts", headers=self.admin_headers, json=self._draft_payload(preview, self.ids["department_id"]))
        self.assertEqual(created.status_code, 201, created.text)
        draft = created.json()
        self.assertEqual(draft["status"], "GENERATED")
        self.assertGreater(len(draft["details"]), 0)

        submitted = self.client.post(f"/api/v1/ai-schedule-drafts/{draft['id']}/submit", headers=self.admin_headers)
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertEqual(submitted.json()["status"], "VALIDATED")
        approved = self.client.post(f"/api/v1/ai-schedule-drafts/{draft['id']}/approve", headers=self.head_nurse_headers)
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["status"], "APPROVED")

        converted = self.client.post(f"/api/v1/ai-schedule-drafts/{draft['id']}/convert", headers=self.head_nurse_headers)
        self.assertEqual(converted.status_code, 200, converted.text)
        self.assertEqual(converted.json()["source"], "AI_GENERATED")
        schedule_id = converted.json()["schedule_id"]
        self.assertEqual(schedule_id, empty.json()["id"])
        conflicts = self.client.get(f"/api/v1/schedules/{schedule_id}/conflicts", headers=self.head_nurse_headers)
        self.assertEqual(conflicts.status_code, 200, conflicts.text)
        self.assertEqual(conflicts.json()["error_count"], 0)
        published = self.client.post(f"/api/v1/schedules/{schedule_id}/publish", headers=self.head_nurse_headers)
        self.assertEqual(published.status_code, 200, published.text)
        self.assertEqual(published.json()["status"], "published")
        self.assertIn(published.json()["approval_state"], {"approved", "approved_with_warnings"})
        db = self.Session()
        try:
            audit = build_pilot_audit_verification(db, draft["id"])
            self.assertTrue(audit.complete)
            self.assertEqual([item.key for item in audit.items], ["generated_by", "validated_by", "approved_by", "published_by"])
        finally:
            db.close()

    def test_nurse_cannot_approve_ai_draft(self) -> None:
        draft_id = self._create_approved_draft(status="VALIDATED", approval_status="pending")
        response = self.client.post(f"/api/v1/ai-schedule-drafts/{draft_id}/approve", headers=self.nurse_headers)
        self.assertEqual(response.status_code, 403)

    def test_rejected_draft_cannot_convert(self) -> None:
        draft_id = self._create_approved_draft(status="REJECTED", approval_status="rejected")
        response = self.client.post(f"/api/v1/ai-schedule-drafts/{draft_id}/convert", headers=self.head_nurse_headers)
        self.assertEqual(response.status_code, 409)

    def test_draft_cannot_convert_twice_or_overwrite_existing_month(self) -> None:
        draft_id = self._create_approved_draft()
        first = self.client.post(f"/api/v1/ai-schedule-drafts/{draft_id}/convert", headers=self.head_nurse_headers)
        self.assertEqual(first.status_code, 200, first.text)
        second = self.client.post(f"/api/v1/ai-schedule-drafts/{draft_id}/convert", headers=self.head_nurse_headers)
        self.assertEqual(second.status_code, 409)

        self._truncate_test_data()
        self.ids = self._seed_simulation_data()
        self.admin_headers = self._headers_for("integration_admin", "integration-password")
        self.head_nurse_headers = self._headers_for("integration_head_nurse", "integration-password")
        draft_id = self._create_approved_draft()
        db: Session = self.Session()
        try:
            manual = Schedule(department_id=self.ids["department_id"], year=2026, month=8, status="draft", source="MANUAL")
            db.add(manual)
            db.flush()
            db.add(ScheduleDetail(schedule_id=manual.id, staff_id=self.ids["rn001_id"], shift_type_id=self.ids["am_shift_id"], work_date=date(2026, 8, 1), locked=False, generated=False, is_incharge=False))
            db.commit()
        finally:
            db.close()
        overwrite = self.client.post(f"/api/v1/ai-schedule-drafts/{draft_id}/convert", headers=self.head_nurse_headers)
        self.assertEqual(overwrite.status_code, 409)

    def test_empty_manual_draft_accepts_ai_without_creating_second_schedule(self) -> None:
        draft_id = self._create_approved_draft()
        response = self.client.post("/api/v1/schedules", headers=self.head_nurse_headers, json={"department_id": self.ids["department_id"], "year": 2026, "month": 8})
        self.assertEqual(response.status_code, 201, response.text)
        schedule_id = response.json()["id"]
        converted = self.client.post(f"/api/v1/ai-schedule-drafts/{draft_id}/convert-replace-draft", headers=self.head_nurse_headers)
        self.assertEqual(converted.status_code, 200, converted.text)
        self.assertEqual(converted.json()["schedule_id"], schedule_id)
        self.assertFalse(converted.json()["will_publish_schedule"])
        with self.Session() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Schedule)), 1)
            self.assertEqual(db.get(Schedule, schedule_id).source, "AI_GENERATED")
            self.assertEqual(db.scalar(select(func.count()).select_from(ScheduleDetail)), 1)

    def test_publish_is_blocked_when_manual_validator_has_errors(self) -> None:
        db: Session = self.Session()
        try:
            schedule = Schedule(department_id=self.ids["department_id"], year=2026, month=8, status="draft", source="MANUAL")
            db.add(schedule)
            db.commit()
            schedule_id = schedule.id
        finally:
            db.close()
        response = self.client.post(f"/api/v1/schedules/{schedule_id}/publish", headers=self.admin_headers)
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
