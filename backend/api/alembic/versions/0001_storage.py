"""Initial service-owned storage."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None


def upgrade():
    op.create_table(
        "incidents",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("record", JSONB, nullable=False),
    )
    op.create_table(
        "audit_events",
        sa.Column("sequence", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("id", sa.String, nullable=False, unique=True),
        sa.Column(
            "incident_id", sa.String, sa.ForeignKey("incidents.id"), nullable=False
        ),
        sa.Column("record", JSONB, nullable=False),
    )


def downgrade():
    op.drop_table("audit_events")
    op.drop_table("incidents")
