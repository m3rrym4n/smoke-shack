"""connect one equipment

Revision ID: 7c3e1a4b9f20
Revises: e4b72c1a90f6
"""

import sqlalchemy as sa
from alembic import op

revision = "7c3e1a4b9f20"
down_revision = "e4b72c1a90f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("equipment") as batch_op:
        batch_op.add_column(
            sa.Column("connected", sa.Boolean(), server_default=sa.false(), nullable=False)
        )

    # The channels migration created this record from entities.yaml for existing
    # installations. Keep their ingest behavior unchanged after upgrade.
    connection = op.get_bind()
    first_id = connection.execute(
        sa.text("SELECT id FROM equipment ORDER BY id LIMIT 1")
    ).scalar_one_or_none()
    if first_id is not None:
        connection.execute(
            sa.text("UPDATE equipment SET connected = 1 WHERE id = :id"),
            {"id": first_id},
        )

    op.create_index(
        "uq_equipment_one_connected",
        "equipment",
        ["connected"],
        unique=True,
        sqlite_where=sa.text("connected = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_equipment_one_connected", table_name="equipment")
    with op.batch_alter_table("equipment") as batch_op:
        batch_op.drop_column("connected")
