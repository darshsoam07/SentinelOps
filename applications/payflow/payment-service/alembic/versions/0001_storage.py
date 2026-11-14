"""Initial service-owned storage."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None


def upgrade():
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("reason", sa.String),
    )
    op.create_index("payments_recent", "payments", ["created_at"])


def downgrade():
    op.drop_table("payments")
