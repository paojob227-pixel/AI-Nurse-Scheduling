"""Persistence-independent rules for the manual schedule publish gate."""

from dataclasses import dataclass
from typing import Iterable

from app.services.schedule_validator import Conflict


@dataclass(frozen=True)
class PublishValidationSummary:
    error_count: int
    warning_count: int
    validation_state: str
    approval_state: str
    outcome: str


def summarize_for_publish(conflicts: Iterable[Conflict]) -> PublishValidationSummary:
    items = tuple(conflicts)
    errors = sum(item.severity == "error" for item in items)
    warnings = sum(item.severity == "warning" for item in items)
    if errors:
        return PublishValidationSummary(errors, warnings, "blocked", "rejected", "blocked")
    if warnings:
        return PublishValidationSummary(0, warnings, "passed_with_warnings", "approved_with_warnings", "published_with_warnings")
    return PublishValidationSummary(0, 0, "passed", "approved", "published")


def conflict_snapshot(conflicts: Iterable[Conflict]) -> list[dict[str, object]]:
    return [
        {
            "severity": item.severity,
            "code": item.code,
            "work_date": item.work_date.isoformat(),
            "shift": item.shift,
            "staff_ids": list(item.staff_ids),
            "staff_names": list(item.staff_names),
            "reason": item.reason,
        }
        for item in conflicts
    ]
