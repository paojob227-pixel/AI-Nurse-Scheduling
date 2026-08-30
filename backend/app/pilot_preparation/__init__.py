"""Read-only clinical-pilot readiness checks and reports.

This package intentionally never creates schedules, changes approval state, or
publishes data.  It is an internal evaluation aid for an isolated pilot.
"""

from app.pilot_preparation.reports import (
    build_pilot_audit_verification,
    build_pilot_kpi_report,
    build_pilot_readiness_report,
    render_pilot_readiness_markdown,
)

__all__ = [
    "build_pilot_audit_verification",
    "build_pilot_kpi_report",
    "build_pilot_readiness_report",
    "render_pilot_readiness_markdown",
]
