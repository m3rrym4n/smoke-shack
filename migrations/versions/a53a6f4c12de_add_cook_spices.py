"""add cook spices

Revision ID: a53a6f4c12de
Revises: 1ccda11b4107
"""

import sqlalchemy as sa
from alembic import op

revision = "a53a6f4c12de"
down_revision = "1ccda11b4107"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cook_spices",
        sa.Column("cook_id", sa.Integer(), nullable=False),
        sa.Column("spice_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["cook_id"], ["cooks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spice_id"], ["spices.id"]),
        sa.PrimaryKeyConstraint("cook_id", "spice_id"),
    )


def downgrade():
    op.drop_table("cook_spices")
