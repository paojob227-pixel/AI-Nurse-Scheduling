"""Allow a priority-5 avoid preference to represent all-day unavailability.

Revision ID: 20260916_07
Revises: 20260803_06
Create Date: 2026-09-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20260916_07"
down_revision = "20260803_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "staff_shift_preferences",
        "shift_type_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_staff_preference_all_day_is_priority_five_avoid",
        "staff_shift_preferences",
        "shift_type_id IS NOT NULL OR (preference = 'avoid' AND weight = 5)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_staff_preference_all_day_is_priority_five_avoid", "staff_shift_preferences", type_="check")
    op.alter_column(
        "staff_shift_preferences",
        "shift_type_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
