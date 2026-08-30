"""Read-only, human-readable evaluation for temporary AI schedule previews."""

from app.scheduler.explanation.schedule_explainer import ScheduleExplanation, build_schedule_explanation

__all__ = ["ScheduleExplanation", "build_schedule_explanation"]
