"""Create analyses and signals tables

Revision ID: 003_create_analyses_and_signals_tables
Revises: 002_create_market_data_tables
Create Date: 2026-10-15 15:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_create_analyses_and_signals_tables"
down_revision: str | None = "002_create_market_data_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    json_type = postgresql.JSONB if is_postgres else sa.JSON
    array_type = postgresql.ARRAY(sa.String) if is_postgres else sa.JSON

    # 1. analyses table
    op.create_table(
        "analyses",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("tf", sa.String(length=8), nullable=False),
        sa.Column("bar_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("verdict", sa.String(length=32), nullable=False),
        sa.Column("counts", json_type, nullable=False),
        sa.Column("indicators", json_type, nullable=False),
        sa.Column("category_votes", json_type, nullable=False),
        sa.Column("htf", json_type, nullable=False),
        sa.Column("macro", json_type, nullable=False),
        sa.Column("strategy_b", json_type, nullable=False),
        sa.Column("weights_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "tf", "bar_time", name="uq_analyses_symbol_tf_bar_time"),
    )
    op.create_index("ix_analyses_symbol_tf_bar_time", "analyses", ["symbol", "tf", "bar_time"], unique=False)
    op.create_index("ix_analyses_verdict", "analyses", ["verdict"], unique=False)

    # 2. signals table
    op.create_table(
        "signals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("analysis_id", sa.BigInteger(), sa.ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("strategy", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("tf", sa.String(length=8), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("verdict", sa.String(length=32), nullable=False),
        sa.Column("bar_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("blocked_by", array_type, nullable=True),
        sa.Column("confirmed_by_b", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signals_symbol", "signals", ["symbol"], unique=False)
    op.create_index("ix_signals_strategy", "signals", ["strategy"], unique=False)
    op.create_index("ix_signals_status", "signals", ["status"], unique=False)
    op.create_index("ix_signals_bar_time", "signals", ["bar_time"], unique=False)


def downgrade() -> None:
    op.drop_table("signals")
    op.drop_table("analyses")
