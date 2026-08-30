"""Add validation approval state and validation history for schedule publishing.

Revision ID: 20260802_03
Revises: 20260802_02
Create Date: 2026-08-02
"""

from alembic import op
import sqlalchemy as sa


revision = "20260802_03"
down_revision = "20260802_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schedules", sa.Column("validation_state", sa.String(length=30), nullable=False, server_default="pending"))
    op.add_column("schedules", sa.Column("approval_state", sa.String(length=30), nullable=False, server_default="not_requested"))
    op.add_column("schedules", sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("schedules", sa.Column("last_validated_by_user_id", sa.Integer(), nullable=True))
    op.add_column("schedules", sa.Column("last_error_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("schedules", sa.Column("last_warning_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("schedules", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("schedules", sa.Column("published_by_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_schedule_last_validator", "schedules", "users", ["last_validated_by_user_id"], ["id"])
    op.create_foreign_key("fk_schedule_publisher", "schedules", "users", ["published_by_user_id"], ["id"])
    op.create_table(
        "schedule_validation_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("schedules.id"), nullable=False),
        sa.Column("validated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("conflicts", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_schedule_validation_history_schedule_id", "schedule_validation_history", ["schedule_id"])
    op.create_index("ix_schedule_validation_history_validated_by_user_id", "schedule_validation_history", ["validated_by_user_id"])


def downgrade() -> None:
    op.drop_index("ix_schedule_validation_history_validated_by_user_id", table_name="schedule_validation_history")
    op.drop_index("ix_schedule_validation_history_schedule_id", table_name="schedule_validation_history")
    op.drop_table("schedule_validation_history")
    op.drop_constraint("fk_schedule_publisher", "schedules", type_="foreignkey")
    op.drop_constraint("fk_schedule_last_validator", "schedules", type_="foreignkey")
    op.drop_column("schedules", "published_by_user_id")
    op.drop_column("schedules", "published_at")
    op.drop_column("schedules", "last_warning_count")
    op.drop_column("schedules", "last_error_count")
    op.drop_column("schedules", "last_validated_by_user_id")
    op.drop_column("schedules", "last_validated_at")
    op.drop_column("schedules", "approval_state")
    op.drop_column("schedules", "validation_state")
