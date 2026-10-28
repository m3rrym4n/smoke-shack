"""add spice catalog

Revision ID: 1ccda11b4107
Revises: b67a21d9942f
"""

import sqlalchemy as sa
from alembic import op

revision = "1ccda11b4107"
down_revision = "b67a21d9942f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "spices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("brand", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("price", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("size_oz", sa.Numeric(precision=6, scale=1), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_custom", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_spices_brand_name_ci "
        "ON spices (lower(brand), lower(name))"
    )


def downgrade():
    op.drop_index("uq_spices_brand_name_ci", table_name="spices")
    op.drop_table("spices")
