"""Conversion regressions using a disposable in-memory database."""

import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database.database import Base
from app.models import AiScheduleDraft, AiScheduleDraftDetail, Department, Schedule, ScheduleAuditLog, ScheduleDetail, ShiftType, Staff, User
from app.services.ai_draft_conversion import AiDraftConversionError, convert_approved_draft


class AiDraftConversionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.actor = User(username="test_hn", password_hash="test-only", role="head_nurse")
        department = Department(name="Test ICU", code="TEST")
        staff = Staff(employee_code="TEST01", first_name="Test", last_name="Nurse", position="RN")
        shift = ShiftType(code="AM", name="Morning", duration_minutes=480, category="normal", crosses_midnight=False, is_working_shift=True)
        self.db.add_all([self.actor, department, staff, shift])
        self.db.flush()
        self.draft = AiScheduleDraft(department_id=department.id, year=2026, month=10, created_by_user_id=self.actor.id, solver_status="FEASIBLE", status="APPROVED", approval_status="approved")
        self.draft.details = [AiScheduleDraftDetail(staff_id=staff.id, shift_type_id=shift.id, work_date=date(2026, 10, 1), is_incharge=True)]
        self.db.add(self.draft)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def existing(self, source="MANUAL", status="draft", populated=False, was_published=False):
        schedule = Schedule(department_id=self.draft.department_id, year=2026, month=10, source=source, status=status, published_at=datetime.now(timezone.utc) if was_published else None)
        if populated:
            item = self.draft.details[0]
            schedule.details = [ScheduleDetail(staff_id=item.staff_id, shift_type_id=item.shift_type_id, work_date=item.work_date, locked=True, generated=False, is_incharge=False)]
        self.db.add(schedule)
        self.db.commit()
        return schedule

    def convert(self, replace=False):
        with patch("app.services.ai_draft_conversion.schedule_validator.validate_schedule", return_value=[]) as validator:
            result = convert_approved_draft(self.db, self.draft, self.actor, replace_existing_ai_draft=replace)
            self.db.commit()
            validator.assert_called_once_with(self.db, result[0].id)
            return result[0]

    def test_empty_manual_draft_accepts_ai_from_both_endpoints(self):
        schedule = self.existing()
        result = self.convert(replace=True)
        self.assertEqual(result.id, schedule.id)
        self.assertEqual(result.source, "AI_GENERATED")
        self.assertEqual(result.status, "draft")
        self.assertIsNone(result.published_at)
        self.assertEqual(self.draft.converted_schedule_id, result.id)
        details = list(self.db.scalars(select(ScheduleDetail)))
        self.assertEqual(len(details), 1)
        self.assertTrue(details[0].generated)
        self.assertTrue(details[0].is_incharge)
        audit = self.db.scalar(select(ScheduleAuditLog))
        self.assertEqual(audit.action, "AI_DRAFT_CONVERTED")
        self.assertEqual(audit.before_value["previous_source"], "MANUAL")

    def test_regular_convert_also_accepts_empty_manual_draft(self):
        schedule = self.existing()
        self.assertEqual(self.convert().id, schedule.id)

    def test_populated_manual_is_protected(self):
        schedule = self.existing(populated=True)
        original_id = schedule.details[0].id
        with self.assertRaises(AiDraftConversionError):
            self.convert(replace=True)
        self.assertEqual(schedule.source, "MANUAL")
        self.assertEqual(schedule.details[0].id, original_id)
        self.assertTrue(schedule.details[0].locked)
        self.assertIsNone(self.draft.converted_schedule_id)

    def test_published_and_previously_published_manual_are_protected(self):
        schedule = self.existing(status="published")
        with self.assertRaises(AiDraftConversionError):
            self.convert(replace=True)
        schedule.status = "draft"
        schedule.published_at = datetime.now(timezone.utc)
        self.db.commit()
        with self.assertRaises(AiDraftConversionError):
            self.convert(replace=True)

    def test_ai_draft_replacement_still_works(self):
        schedule = self.existing(source="AI_GENERATED", populated=True)
        self.assertEqual(self.convert(replace=True).id, schedule.id)
        self.assertEqual(self.db.scalar(select(ScheduleAuditLog)).action, "AI_DRAFT_REPLACED")

    def test_published_ai_schedule_is_protected(self):
        self.existing(source="AI_GENERATED", status="published", populated=True)
        with self.assertRaises(AiDraftConversionError):
            self.convert(replace=True)

    def test_new_schedule_and_double_conversion(self):
        self.convert()
        with self.assertRaises(AiDraftConversionError):
            self.convert(replace=True)
