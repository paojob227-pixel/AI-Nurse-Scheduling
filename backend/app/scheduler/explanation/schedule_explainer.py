"""Compose read-only staff explanations from a snapshot and preview assignments."""

from collections import Counter
from dataclasses import dataclass
from datetime import date

from app.scheduler.explanation.fairness_report import FairnessReport, build_fairness_report
from app.scheduler.explanation.night_report import NightDistributionReport, build_night_report
from app.scheduler.explanation.preference_report import PreferenceReport, build_preference_report
from app.scheduler.fairness_model import SHIFT_BASE_WEIGHTS
from app.scheduler.contracts import SchedulerSnapshot
from app.services.ai_preview_validation import PreviewAssignmentInput


@dataclass(frozen=True)
class ExplanationSummary:
    total_assignments: int
    total_working_minutes: int
    total_ot_minutes: int
    message: str


@dataclass(frozen=True)
class StaffExplanation:
    staff_id: int
    employee_code: str
    staff_name: str
    total_shifts: int
    working_minutes: int
    workload_score: int
    night_count: int
    ot_minutes: int
    shift_counts: dict[str, int]
    preference_total: int
    prefer_satisfied: int
    prefer_unsatisfied: int
    avoid_violations: int
    summary: str


@dataclass(frozen=True)
class ScheduleExplanation:
    summary: ExplanationSummary
    fairness: FairnessReport
    night_distribution: NightDistributionReport
    preference: PreferenceReport
    staff_explanations: tuple[StaffExplanation, ...]


def build_schedule_explanation(
    snapshot: SchedulerSnapshot,
    assignments: tuple[PreviewAssignmentInput, ...],
) -> ScheduleExplanation:
    """Explain an existing preview. This function never solves, writes, or validates schedules."""
    staff_by_id = {item.id: item for item in snapshot.staff}
    shift_by_id = {item.id: item for item in snapshot.shifts}
    assignment_keys: set[tuple[int, date, int]] = set()
    for item in assignments:
        if item.staff_id not in staff_by_id or item.shift_type_id not in shift_by_id:
            raise ValueError("Preview assignment is outside the selected scheduler snapshot")
        if item.work_date.year != snapshot.year or item.work_date.month != snapshot.month:
            raise ValueError("Preview assignment date is outside the selected scheduler month")
        assignment_keys.add((item.staff_id, item.work_date, item.shift_type_id))

    by_staff: dict[int, list[tuple[date, int]]] = {staff_id: [] for staff_id in staff_by_id}
    for staff_id, work_date, shift_id in assignment_keys:
        by_staff[staff_id].append((work_date, shift_id))
    workload_minutes = {
        staff_id: sum(shift_by_id[shift_id].duration_minutes or 0 for _day, shift_id in entries)
        for staff_id, entries in by_staff.items()
    }
    workload_scores = {
        staff_id: sum(SHIFT_BASE_WEIGHTS.get(shift_by_id[shift_id].code.upper(), 0) for _day, shift_id in entries)
        for staff_id, entries in by_staff.items()
    }
    ot_threshold_minutes = snapshot.rules.get("OT_THRESHOLD", 0) * 60
    ot_minutes = {staff_id: max(0, minutes - ot_threshold_minutes) for staff_id, minutes in workload_minutes.items()}
    fairness = build_fairness_report(workload_minutes)
    night = build_night_report(snapshot, assignment_keys)
    preferences = build_preference_report(snapshot, assignment_keys)

    staff_explanations: list[StaffExplanation] = []
    for staff in snapshot.staff:
        entries = by_staff[staff.id]
        counts = Counter(shift_by_id[shift_id].code.upper() for _day, shift_id in entries)
        staff_preferences = [item for item in snapshot.preferences if item.staff_id == staff.id]
        preferred = [item for item in staff_preferences if item.preference == "prefer"]
        avoided = [item for item in staff_preferences if item.preference == "avoid"]
        prefer_satisfied = sum((item.staff_id, item.work_date, item.shift_type_id) in assignment_keys for item in preferred)
        avoid_violations = sum((item.staff_id, item.work_date, item.shift_type_id) in assignment_keys for item in avoided)
        night_count = counts.get("N", 0)
        staff_explanations.append(StaffExplanation(
            staff.id, staff.employee_code, staff.display_name, len(entries), workload_minutes[staff.id],
            workload_scores[staff.id], night_count, ot_minutes[staff.id], dict(sorted(counts.items())),
            len(staff_preferences), prefer_satisfied, len(preferred) - prefer_satisfied, avoid_violations,
            _staff_summary(staff.employee_code, staff.position, staff.is_senior_rn, night_count, night.mean_nights_per_rn,
                           workload_minutes[staff.id], fairness.mean_workload_minutes, ot_minutes[staff.id],
                           len(preferred) - prefer_satisfied, avoid_violations),
        ))
    return ScheduleExplanation(
        ExplanationSummary(
            len(assignment_keys), sum(workload_minutes.values()), sum(ot_minutes.values()),
            "รายงานนี้อธิบายผล AI Preview จากกฎความปลอดภัยและคะแนนที่มีอยู่แล้ว โดยไม่เปลี่ยน solver หรือการตัดสินใจของตาราง",
        ),
        fairness, night, preferences, tuple(staff_explanations),
    )


def _staff_summary(
    employee_code: str, position: str, is_senior_rn: bool, night_count: int, mean_nights: float,
    working_minutes: int, mean_workload: float, ot_minutes: int, unmet_preferences: int, avoid_violations: int,
) -> str:
    notes = [
        f"{employee_code} ได้เวรดึก {night_count} ครั้ง (ค่าเฉลี่ย RN {mean_nights:.1f} ครั้ง)"
        if position.upper() == "RN" else f"{employee_code} ได้เวรดึก {night_count} ครั้ง"
    ]
    if is_senior_rn:
        notes.append("เป็น Senior RN จึงมีคุณสมบัติสำหรับ Senior RN/Incharge coverage")
    if position.upper() == "RN" and working_minutes < mean_workload:
        notes.append("ภาระงานยังต่ำกว่าค่าเฉลี่ยของตาราง")
    if ot_minutes == 0:
        notes.append("ไม่มี OT จากเกณฑ์ที่ตั้งไว้")
    else:
        notes.append(f"มี OT {ot_minutes} นาที")
    if unmet_preferences or avoid_violations:
        notes.append(f"มี soft-preference trade-off: prefer ไม่ตรง {unmet_preferences}, avoid ถูกละเมิด {avoid_violations}")
    return ". ".join(notes) + "."
