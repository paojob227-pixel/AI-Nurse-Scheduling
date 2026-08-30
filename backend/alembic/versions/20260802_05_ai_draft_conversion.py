"""Add AI source metadata and conversion audit references.

Revision ID: 20260802_05
Revises: 20260802_04
Create Date: 2026-08-02
"""

from alembic import op
import sqlalchemy as sa


revision = "20260802_05"
down_revision = "20260802_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schedules", sa.Column("source", sa.String(length=20), nullable=False, server_default="MANUAL"))
    op.add_column("ai_schedule_drafts", sa.Column("converted_schedule_id", sa.Integer(), nullable=True))
    op.add_column("ai_schedule_drafts", sa.Column("converted_by_user_id", sa.Integer(), nullable=True))
    op.add_column("ai_schedule_drafts", sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_ai_draft_converted_schedule", "ai_schedule_drafts", "schedules", ["converted_schedule_id"], ["id"])
    op.create_foreign_key("fk_ai_draft_converter", "ai_schedule_drafts", "users", ["converted_by_user_id"], ["id"])
    op.create_index("ix_ai_schedule_drafts_converted_schedule_id", "ai_schedule_drafts", ["converted_schedule_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_schedule_drafts_converted_schedule_id", table_name="ai_schedule_drafts")
    op.drop_constraint("fk_ai_draft_converter", "ai_schedule_drafts", type_="foreignkey")
    op.drop_constraint("fk_ai_draft_converted_schedule", "ai_schedule_drafts", type_="foreignkey")
    op.drop_column("ai_schedule_drafts", "converted_at")
    op.drop_column("ai_schedule_drafts", "converted_by_user_id")
    op.drop_column("ai_schedule_drafts", "converted_schedule_id")
    op.drop_column("schedules", "source")
