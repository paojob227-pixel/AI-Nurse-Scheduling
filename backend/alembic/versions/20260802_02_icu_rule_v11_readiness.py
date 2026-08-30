"""Add ICU Rule Configuration v1.1 scheduler readiness schema.

Revision ID: 20260802_02
Revises: 20260802_01
Create Date: 2026-08-02
"""

from alembic import op
import sqlalchemy as sa


revision = "20260802_02"
down_revision = "20260802_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("staffs", sa.Column("is_senior_rn", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    op.add_column("shift_types", sa.Column("duration_minutes", sa.Integer(), nullable=True))
    op.add_column("shift_types", sa.Column("category", sa.String(length=20), nullable=True))
    op.add_column("shift_types", sa.Column("crosses_midnight", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.execute("""
        UPDATE shift_types
        SET duration_minutes = CASE
            WHEN start_time IS NULL OR end_time IS NULL THEN NULL
            WHEN end_time > start_time THEN EXTRACT(EPOCH FROM (end_time - start_time)) / 60
            ELSE EXTRACT(EPOCH FROM ((end_time - start_time) + INTERVAL '24 hours')) / 60
        END,
        crosses_midnight = CASE WHEN start_time IS NOT NULL AND end_time <= start_time THEN true ELSE false END
    """)
    op.execute("UPDATE shift_types SET category = CASE WHEN duration_minutes >= 720 THEN 'extended' ELSE 'normal' END WHERE duration_minutes IS NOT NULL")

    op.add_column("schedule_details", sa.Column("is_incharge", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("schedule_details", sa.Column("incharge_exception", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("schedule_details", sa.Column("exception_reason", sa.Text(), nullable=True))
    op.add_column("schedule_details", sa.Column("exception_approved_by_user_id", sa.Integer(), nullable=True))
    op.add_column("schedule_details", sa.Column("exception_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_schedule_detail_exception_approver", "schedule_details", "users", ["exception_approved_by_user_id"], ["id"])

    op.create_table(
        "coverage_windows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("crosses_midnight", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("min_rn", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("max_rn", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("min_support_staff", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("min_senior_rn", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("department_id", "code", name="uq_coverage_window_department_code"),
        sa.CheckConstraint("min_rn >= 0 AND max_rn >= min_rn", name="ck_coverage_window_rn_bounds"),
        sa.CheckConstraint("min_support_staff >= 0 AND min_senior_rn >= 0", name="ck_coverage_window_minimums"),
    )
    op.create_index("ix_coverage_windows_department_id", "coverage_windows", ["department_id"])
    op.create_table(
        "coverage_window_shift_types",
        sa.Column("coverage_window_id", sa.Integer(), sa.ForeignKey("coverage_windows.id"), primary_key=True),
        sa.Column("shift_type_id", sa.Integer(), sa.ForeignKey("shift_types.id"), primary_key=True),
    )
    op.create_table(
        "department_rule_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("integer_value", sa.Integer(), nullable=True),
        sa.Column("text_value", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("department_id", "key", name="uq_department_rule_key"),
    )
    op.create_index("ix_department_rule_settings_department_id", "department_rule_settings", ["department_id"])
    op.create_table(
        "staff_shift_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("shift_type_id", sa.Integer(), sa.ForeignKey("shift_types.id"), nullable=False),
        sa.Column("preference", sa.String(length=20), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("staff_id", "work_date", "shift_type_id", "preference", name="uq_staff_preference"),
    )
    op.create_index("ix_staff_shift_preferences_staff_id", "staff_shift_preferences", ["staff_id"])
    op.create_index("ix_staff_shift_preferences_work_date", "staff_shift_preferences", ["work_date"])
    op.create_table(
        "schedule_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("schedules.id"), nullable=False),
        sa.Column("schedule_detail_id", sa.Integer(), sa.ForeignKey("schedule_details.id"), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("before_value", sa.JSON(), nullable=True),
        sa.Column("after_value", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_schedule_audit_logs_schedule_id", "schedule_audit_logs", ["schedule_id"])
    op.create_index("ix_schedule_audit_logs_schedule_detail_id", "schedule_audit_logs", ["schedule_detail_id"])
    op.create_index("ix_schedule_audit_logs_actor_user_id", "schedule_audit_logs", ["actor_user_id"])


def downgrade() -> None:
    op.drop_index("ix_schedule_audit_logs_actor_user_id", table_name="schedule_audit_logs")
    op.drop_index("ix_schedule_audit_logs_schedule_detail_id", table_name="schedule_audit_logs")
    op.drop_index("ix_schedule_audit_logs_schedule_id", table_name="schedule_audit_logs")
    op.drop_table("schedule_audit_logs")
    op.drop_index("ix_staff_shift_preferences_work_date", table_name="staff_shift_preferences")
    op.drop_index("ix_staff_shift_preferences_staff_id", table_name="staff_shift_preferences")
    op.drop_table("staff_shift_preferences")
    op.drop_index("ix_department_rule_settings_department_id", table_name="department_rule_settings")
    op.drop_table("department_rule_settings")
    op.drop_table("coverage_window_shift_types")
    op.drop_index("ix_coverage_windows_department_id", table_name="coverage_windows")
    op.drop_table("coverage_windows")
    op.drop_constraint("fk_schedule_detail_exception_approver", "schedule_details", type_="foreignkey")
    op.drop_column("schedule_details", "exception_approved_at")
    op.drop_column("schedule_details", "exception_approved_by_user_id")
    op.drop_column("schedule_details", "exception_reason")
    op.drop_column("schedule_details", "incharge_exception")
    op.drop_column("schedule_details", "is_incharge")
    op.drop_column("shift_types", "crosses_midnight")
    op.drop_column("shift_types", "category")
    op.drop_column("shift_types", "duration_minutes")
    op.drop_column("staffs", "is_senior_rn")
