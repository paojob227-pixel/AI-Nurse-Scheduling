"""Create the initial manual scheduling schema.

Revision ID: 20260726_01
Revises:
Create Date: 2026-07-26
"""

from alembic import op
import sqlalchemy as sa


revision = "20260726_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("code", sa.String(length=30), nullable=False, unique=True),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=50), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_table(
        "shift_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=20), nullable=False, unique=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("is_working_shift", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=100), nullable=False, unique=True),
        sa.Column("value", sa.Text(), nullable=False),
    )
    op.create_table(
        "holidays",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False, unique=True),
        sa.Column("name", sa.String(length=150), nullable=False),
    )
    op.create_index("ix_holidays_date", "holidays", ["date"])
    op.create_table(
        "staffs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_code", sa.String(length=30), nullable=False, unique=True),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("position", sa.String(length=50), nullable=False),
        sa.Column("skill_level", sa.String(length=30), nullable=True),
        sa.Column("employment_type", sa.String(length=30), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, unique=True),
    )
    op.create_index("ix_staffs_employee_code", "staffs", ["employee_code"])
    op.create_table(
        "availability",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.UniqueConstraint("staff_id", "date", name="uq_availability_staff_date"),
    )
    op.create_index("ix_availability_staff_id", "availability", ["staff_id"])
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=False),
        sa.Column("leave_type", sa.String(length=50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_leave_requests_staff_id", "leave_requests", ["staff_id"])
    op.create_table(
        "schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("department_id", "year", "month", name="uq_schedule_department_month"),
    )
    op.create_table(
        "schedule_details",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("schedules.id"), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=False),
        sa.Column("shift_type_id", sa.Integer(), sa.ForeignKey("shift_types.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("generated", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("schedule_id", "staff_id", "date", name="uq_schedule_staff_date"),
    )
    op.create_index("ix_schedule_details_schedule_id", "schedule_details", ["schedule_id"])
    op.create_index("ix_schedule_details_staff_id", "schedule_details", ["staff_id"])
    op.create_table(
        "shift_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requester_staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=False),
        sa.Column("target_staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("requested_shift_type_id", sa.Integer(), sa.ForeignKey("shift_types.id"), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("shift_requests")
    op.drop_index("ix_schedule_details_staff_id", table_name="schedule_details")
    op.drop_index("ix_schedule_details_schedule_id", table_name="schedule_details")
    op.drop_table("schedule_details")
    op.drop_table("schedules")
    op.drop_index("ix_leave_requests_staff_id", table_name="leave_requests")
    op.drop_table("leave_requests")
    op.drop_index("ix_availability_staff_id", table_name="availability")
    op.drop_table("availability")
    op.drop_index("ix_staffs_employee_code", table_name="staffs")
    op.drop_table("staffs")
    op.drop_index("ix_holidays_date", table_name="holidays")
    op.drop_table("holidays")
    op.drop_table("system_settings")
    op.drop_table("shift_types")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
    op.drop_table("departments")
