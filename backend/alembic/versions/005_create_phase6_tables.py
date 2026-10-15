"""Create market_briefs and ai_comments tables

Revision ID: 005_create_phase6_tables
Revises: 004_create_phase5_tables
Create Date: 2026-10-15 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005_create_phase6_tables"
down_revision: str | None = "004_create_phase5_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    json_type = postgresql.JSONB if is_postgres else sa.JSON

    # 1. market_briefs table
    op.create_table(
        "market_briefs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="morning"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", json_type, nullable=False),
        sa.Column("narrative", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_briefs_generated_at", "market_briefs", ["generated_at"], unique=False)
    op.create_index("ix_market_briefs_kind", "market_briefs", ["kind"], unique=False)

    # 2. ai_comments table
    op.create_table(
        "ai_comments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "analysis_id",
            sa.BigInteger(),
            sa.ForeignKey("analyses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "brief_id",
            sa.BigInteger(),
            sa.ForeignKey("market_briefs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="analysis"),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("content", json_type, nullable=False),
        sa.Column("valid", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_in", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_comments_analysis_id", "ai_comments", ["analysis_id"], unique=False)
    op.create_index("ix_ai_comments_brief_id", "ai_comments", ["brief_id"], unique=False)
    op.create_index("ix_ai_comments_kind", "ai_comments", ["kind"], unique=False)
    op.create_index("ix_ai_comments_created_at", "ai_comments", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("ai_comments")
    op.drop_table("market_briefs")
