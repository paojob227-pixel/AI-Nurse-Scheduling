"""Add auditable AI draft storage and human-approval workflow.

Revision ID: 20260802_04
Revises: 20260802_03
Create Date: 2026-08-02
"""

from alembic import op
import sqlalchemy as sa


revision = "20260802_04"
down_revision = "20260802_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_schedule_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("solver_status", sa.String(length=20), nullable=False),
        sa.Column("objective_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="GENERATED"),
        sa.Column("validation_status", sa.String(length=30), nullable=False, server_default="not_validated"),
        sa.Column("validation_error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("validation_warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("validation_conflicts", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("approval_status", sa.String(length=30), nullable=False, server_default="not_submitted"),
        sa.Column("submitted_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("month >= 1 AND month <= 12", name="ck_ai_schedule_draft_month"),
    )
    op.create_index("ix_ai_schedule_drafts_department_id", "ai_schedule_drafts", ["department_id"])
    op.create_index("ix_ai_schedule_drafts_created_by_user_id", "ai_schedule_drafts", ["created_by_user_id"])
    op.create_index("ix_ai_schedule_drafts_status", "ai_schedule_drafts", ["status"])
    op.create_table(
        "ai_schedule_draft_details",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("draft_id", sa.Integer(), sa.ForeignKey("ai_schedule_drafts.id"), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=False),
        sa.Column("shift_type_id", sa.Integer(), sa.ForeignKey("shift_types.id"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("is_incharge", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.UniqueConstraint("draft_id", "staff_id", "work_date", "shift_type_id", name="uq_ai_draft_assignment"),
    )
    op.create_index("ix_ai_schedule_draft_details_draft_id", "ai_schedule_draft_details", ["draft_id"])
    op.create_index("ix_ai_schedule_draft_details_staff_id", "ai_schedule_draft_details", ["staff_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_schedule_draft_details_staff_id", table_name="ai_schedule_draft_details")
    op.drop_index("ix_ai_schedule_draft_details_draft_id", table_name="ai_schedule_draft_details")
    op.drop_table("ai_schedule_draft_details")
    op.drop_index("ix_ai_schedule_drafts_status", table_name="ai_schedule_drafts")
    op.drop_index("ix_ai_schedule_drafts_created_by_user_id", table_name="ai_schedule_drafts")
    op.drop_index("ix_ai_schedule_drafts_department_id", table_name="ai_schedule_drafts")
    op.drop_table("ai_schedule_drafts")
