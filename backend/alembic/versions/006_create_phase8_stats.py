"""Create Phase 8 TimescaleDB hypertables and continuous aggregates for journal statistics

Revision ID: 006_create_phase8_stats
Revises: 005_create_phase6_tables
Create Date: 2026-10-15 18:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006_create_phase8_stats"
down_revision: str | None = "005_create_phase6_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        # 1. Update paper_trades primary key to composite (id, entry_time) for hypertable
        op.execute("ALTER TABLE paper_trades DROP CONSTRAINT IF EXISTS paper_trades_pkey;")
        op.execute("ALTER TABLE paper_trades ADD PRIMARY KEY (id, entry_time);")

        # 2. Convert paper_trades to TimescaleDB hypertable
        op.execute(
            "SELECT create_hypertable('paper_trades', 'entry_time', "
            "chunk_time_interval => INTERVAL '30 days', "
            "if_not_exists => TRUE, migrate_data => TRUE);"
        )

        # 3. Create continuous aggregate daily_paper_stats
        op.execute(
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS daily_paper_stats
            WITH (timescaledb.continuous) AS
            SELECT time_bucket('1 day', entry_time) AS day,
                   symbol,
                   strategy,
                   is_virtual,
                   count(*) AS total_trades,
                   count(*) FILTER (WHERE pnl_r > 0) AS win_trades,
                   count(*) FILTER (WHERE pnl_r < 0) AS loss_trades,
                   sum(coalesce(pnl_usd, 0.0)) AS total_pnl_usd,
                   sum(coalesce(pnl_r, 0.0)) AS total_pnl_r,
                   avg(coalesce(pnl_r, 0.0)) AS avg_pnl_r
            FROM paper_trades
            WHERE status = 'CLOSED'
            GROUP BY day, symbol, strategy, is_virtual
            WITH NO DATA;
            """
        )

        # Continuous aggregate policy for daily_paper_stats (refresh hourly)
        op.execute(
            """
            SELECT add_continuous_aggregate_policy('daily_paper_stats',
                start_offset => INTERVAL '30 days',
                end_offset => INTERVAL '1 hour',
                schedule_interval => INTERVAL '1 hour',
                if_not_exists => TRUE);
            """
        )

        # 4. Update real_executions primary key to composite (id, fill_time) for hypertable
        op.execute("ALTER TABLE real_executions DROP CONSTRAINT IF EXISTS real_executions_pkey;")
        op.execute("ALTER TABLE real_executions ADD PRIMARY KEY (id, fill_time);")

        # 5. Convert real_executions to TimescaleDB hypertable
        op.execute(
            "SELECT create_hypertable('real_executions', 'fill_time', "
            "chunk_time_interval => INTERVAL '30 days', "
            "if_not_exists => TRUE, migrate_data => TRUE);"
        )

        # 6. Create continuous aggregate daily_real_stats
        op.execute(
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS daily_real_stats
            WITH (timescaledb.continuous) AS
            SELECT time_bucket('1 day', fill_time) AS day,
                   broker_profile,
                   source,
                   count(*) AS total_trades,
                   count(*) FILTER (WHERE pnl_r > 0) AS win_trades,
                   count(*) FILTER (WHERE pnl_r < 0) AS loss_trades,
                   sum(coalesce(pnl_usd, 0.0)) AS total_pnl_usd,
                   sum(coalesce(pnl_r, 0.0)) AS total_pnl_r,
                   avg(coalesce(pnl_r, 0.0)) AS avg_pnl_r,
                   avg(slippage_points) AS avg_slippage
            FROM real_executions
            WHERE exit_price IS NOT NULL
            GROUP BY day, broker_profile, source
            WITH NO DATA;
            """
        )

        # Continuous aggregate policy for daily_real_stats (refresh hourly)
        op.execute(
            """
            SELECT add_continuous_aggregate_policy('daily_real_stats',
                start_offset => INTERVAL '30 days',
                end_offset => INTERVAL '1 hour',
                schedule_interval => INTERVAL '1 hour',
                if_not_exists => TRUE);
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP MATERIALIZED VIEW IF EXISTS daily_real_stats CASCADE;")
        op.execute("DROP MATERIALIZED VIEW IF EXISTS daily_paper_stats CASCADE;")
        op.execute("ALTER TABLE real_executions DROP CONSTRAINT IF EXISTS real_executions_pkey;")
        op.execute("ALTER TABLE real_executions ADD PRIMARY KEY (id);")
        op.execute("ALTER TABLE paper_trades DROP CONSTRAINT IF EXISTS paper_trades_pkey;")
        op.execute("ALTER TABLE paper_trades ADD PRIMARY KEY (id);")
