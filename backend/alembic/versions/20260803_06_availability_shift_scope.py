"""Allow availability to apply to one shift or all shifts for a date.

Revision ID: 20260803_06
Revises: 20260802_05
Create Date: 2026-08-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260803_06"
down_revision = "20260802_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_availability_staff_date", "availability", type_="unique")
    op.add_column("availability", sa.Column("shift_type_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_availability_shift_type", "availability", "shift_types", ["shift_type_id"], ["id"])
    op.create_index("ix_availability_shift_type_id", "availability", ["shift_type_id"])
    op.create_unique_constraint("uq_availability_staff_date_shift", "availability", ["staff_id", "date", "shift_type_id"])


def downgrade() -> None:
    op.drop_constraint("uq_availability_staff_date_shift", "availability", type_="unique")
    op.drop_index("ix_availability_shift_type_id", table_name="availability")
    op.drop_constraint("fk_availability_shift_type", "availability", type_="foreignkey")
    op.drop_column("availability", "shift_type_id")
    op.create_unique_constraint("uq_availability_staff_date", "availability", ["staff_id", "date"])
