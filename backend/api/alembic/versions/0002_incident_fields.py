"""Index incident metadata and keep it consistent with every JSONB write."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"


def upgrade():
    for field in ("status", "severity"):
        op.add_column(
            "incidents",
            sa.Column(
                field,
                sa.Text(),
                sa.Computed(f"record ->> '{field}'", persisted=True),
                nullable=False,
            ),
        )
        op.create_index(f"ix_incidents_{field}", "incidents", [field])


def downgrade():
    for field in ("severity", "status"):
        op.drop_index(f"ix_incidents_{field}", table_name="incidents")
        op.drop_column("incidents", field)
