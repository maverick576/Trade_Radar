"""Create market data tables (candles, derivatives_snapshots, sentiment_snapshots) and hypertables

Revision ID: 002_create_market_data_tables
Revises: 001_create_auth_tables
Create Date: 2026-10-15 13:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_create_market_data_tables"
down_revision: str | None = "001_create_auth_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. candles table
    op.create_table(
        "candles",
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("tf", sa.String(length=8), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("taker_buy_volume", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("symbol", "tf", "open_time"),
    )
    op.create_index("ix_candles_symbol_tf", "candles", ["symbol", "tf"], unique=False)

    # 2. derivatives_snapshots table
    op.create_table(
        "derivatives_snapshots",
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("funding", sa.Float(), nullable=True),
        sa.Column("mark", sa.Float(), nullable=True),
        sa.Column("open_interest", sa.Float(), nullable=True),
        sa.Column("ls_ratio", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("symbol", "ts"),
    )
    op.create_index("ix_derivatives_snapshots_symbol", "derivatives_snapshots", ["symbol"], unique=False)

    # 3. sentiment_snapshots table
    op.create_table(
        "sentiment_snapshots",
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("source", "ts"),
    )

    # TimescaleDB Hypertables and compression policies for PostgreSQL
    if is_postgres:
        op.execute(
            "SELECT create_hypertable('candles', 'open_time', "
            "chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);"
        )
        op.execute(
            "ALTER TABLE candles SET (timescaledb.compress, timescaledb.compress_segmentby = 'symbol, tf');"
        )
        op.execute(
            "SELECT add_compression_policy('candles', INTERVAL '30 days', if_not_exists => TRUE);"
        )

        op.execute(
            "SELECT create_hypertable('derivatives_snapshots', 'ts', "
            "chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);"
        )
        op.execute(
            "ALTER TABLE derivatives_snapshots SET (timescaledb.compress, timescaledb.compress_segmentby = 'symbol');"
        )
        op.execute(
            "SELECT add_compression_policy('derivatives_snapshots', INTERVAL '30 days', if_not_exists => TRUE);"
        )


def downgrade() -> None:
    op.drop_table("sentiment_snapshots")
    op.drop_table("derivatives_snapshots")
    op.drop_table("candles")
