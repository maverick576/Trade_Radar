"""Create tickets, real_executions, paper_trades, and broker_calibrations tables

Revision ID: 004_create_phase5_tables
Revises: 003_create_analyses_and_signals_tables
Create Date: 2026-10-15 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_create_phase5_tables"
down_revision: str | None = "003_create_analyses_and_signals_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    json_type = postgresql.JSONB if is_postgres else sa.JSON

    # 1. tickets table
    op.create_table(
        "tickets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "signal_id",
            sa.BigInteger(),
            sa.ForeignKey("signals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("strategy", sa.String(length=32), nullable=False, server_default="Konfluensi-10"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("entry", sa.Float(), nullable=False),
        sa.Column("entry_low", sa.Float(), nullable=False),
        sa.Column("entry_high", sa.Float(), nullable=False),
        sa.Column("sl", sa.Float(), nullable=False),
        sa.Column("tp1", sa.Float(), nullable=False),
        sa.Column("tp2", sa.Float(), nullable=False),
        sa.Column("atr", sa.Float(), nullable=False),
        sa.Column("sl_points", sa.Float(), nullable=False),
        sa.Column("sl_atr_mult", sa.Float(), nullable=False),
        sa.Column("tp1_points", sa.Float(), nullable=False),
        sa.Column("tp2_points", sa.Float(), nullable=False),
        sa.Column("invalidation", sa.String(length=255), nullable=False),
        sa.Column("reasons", json_type, nullable=False),
        sa.Column("risks", json_type, nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("broker_offset", sa.Float(), nullable=True),
        sa.Column("broker_profile", sa.String(length=64), nullable=True),
        sa.Column("suggested_lot", sa.Float(), nullable=True),
        sa.Column("actual_risk_usd", sa.Float(), nullable=True),
        sa.Column("actual_risk_pct", sa.Float(), nullable=True),
        sa.Column("min_lot_warning", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("warning_message", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("signal_id", name="uq_tickets_signal_id"),
    )
    op.create_index("ix_tickets_symbol", "tickets", ["symbol"], unique=False)
    op.create_index("ix_tickets_status", "tickets", ["status"], unique=False)
    op.create_index("ix_tickets_valid_until", "tickets", ["valid_until"], unique=False)

    # 2. real_executions table
    op.create_table(
        "real_executions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "ticket_id",
            sa.BigInteger(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("broker_profile", sa.String(length=64), nullable=False),
        sa.Column("fill_price", sa.Float(), nullable=False),
        sa.Column("lot", sa.Float(), nullable=False),
        sa.Column("fill_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pnl_usd", sa.Float(), nullable=True),
        sa.Column("pnl_r", sa.Float(), nullable=True),
        sa.Column("slippage_points", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="ui"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_real_executions_ticket_id", "real_executions", ["ticket_id"], unique=False)

    # 3. paper_trades table
    op.create_table(
        "paper_trades",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "ticket_id",
            sa.BigInteger(),
            sa.ForeignKey("tickets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "signal_id",
            sa.BigInteger(),
            sa.ForeignKey("signals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("strategy", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("size", sa.Float(), nullable=False),
        sa.Column("sl", sa.Float(), nullable=False),
        sa.Column("tp1", sa.Float(), nullable=False),
        sa.Column("tp2", sa.Float(), nullable=False),
        sa.Column("tp1_hit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("bars_held", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="OPEN"),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("exit_reason", sa.String(length=32), nullable=True),
        sa.Column("pnl_usd", sa.Float(), nullable=True),
        sa.Column("pnl_r", sa.Float(), nullable=True),
        sa.Column("fees_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("mfe_r", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("mae_r", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("is_virtual", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_trades_symbol", "paper_trades", ["symbol"], unique=False)
    op.create_index("ix_paper_trades_strategy", "paper_trades", ["strategy"], unique=False)
    op.create_index("ix_paper_trades_status", "paper_trades", ["status"], unique=False)
    op.create_index("ix_paper_trades_is_virtual", "paper_trades", ["is_virtual"], unique=False)

    # 4. broker_calibrations table
    op.create_table(
        "broker_calibrations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("broker_profile", sa.String(length=64), nullable=False),
        sa.Column("broker_price", sa.Float(), nullable=False),
        sa.Column("source_price", sa.Float(), nullable=False),
        sa.Column("offset", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_broker_calibrations_symbol", "broker_calibrations", ["symbol"], unique=False
    )
    op.create_index(
        "ix_broker_calibrations_expires_at", "broker_calibrations", ["expires_at"], unique=False
    )


def downgrade() -> None:
    op.drop_table("broker_calibrations")
    op.drop_table("paper_trades")
    op.drop_table("real_executions")
    op.drop_table("tickets")
