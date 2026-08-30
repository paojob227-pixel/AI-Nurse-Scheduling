"""Rename schedule assignment date to work_date.

Revision ID: 20260802_01
Revises: 20260726_01
Create Date: 2026-08-02
"""

from alembic import op


revision = "20260802_01"
down_revision = "20260726_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_schedule_staff_date", "schedule_details", type_="unique")
    op.alter_column("schedule_details", "date", new_column_name="work_date")
    op.create_unique_constraint("uq_schedule_staff_work_date", "schedule_details", ["schedule_id", "staff_id", "work_date"])


def downgrade() -> None:
    op.drop_constraint("uq_schedule_staff_work_date", "schedule_details", type_="unique")
    op.alter_column("schedule_details", "work_date", new_column_name="date")
    op.create_unique_constraint("uq_schedule_staff_date", "schedule_details", ["schedule_id", "staff_id", "date"])
