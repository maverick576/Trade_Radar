"""Independent SQL verification script for TradeRadar Journal statistics.

Compares raw independent SQL aggregations against traderadar.stats service results
to strictly verify mathematical parity down to the decimal point (ROADMAP.md Fase 8).
"""

import asyncio
import sys
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from traderadar.core.db import close_db, get_db_session
from traderadar.stats.service import get_journal_stats


async def verify_stats_parity(session: AsyncSession) -> dict[str, Any]:
    """Run raw independent SQL queries and verify parity against traderadar.stats."""
    # 1. Raw SQL aggregation for Paper Trades
    paper_sql = text(
        """
        SELECT
            count(*) AS total,
            count(*) FILTER (WHERE pnl_r > 0) AS wins,
            count(*) FILTER (WHERE pnl_r < 0) AS losses,
            count(*) FILTER (WHERE pnl_r = 0) AS be,
            coalesce(sum(pnl_usd), 0.0) AS total_usd,
            coalesce(sum(pnl_r), 0.0) AS total_r,
            coalesce(sum(pnl_usd) FILTER (WHERE pnl_usd > 0), 0.0) AS gross_profit,
            coalesce(sum(abs(pnl_usd)) FILTER (WHERE pnl_usd < 0), 0.0) AS gross_loss
        FROM paper_trades
        WHERE status = 'CLOSED' AND is_virtual = false;
        """
    )
    raw_paper = (await session.execute(paper_sql)).mappings().one()

    raw_paper_total = int(raw_paper["total"])
    raw_paper_wins = int(raw_paper["wins"])
    raw_paper_losses = int(raw_paper["losses"])
    raw_paper_be = int(raw_paper["be"])
    raw_paper_usd = round(float(raw_paper["total_usd"]), 2)
    raw_paper_r = round(float(raw_paper["total_r"]), 4)
    raw_paper_wr = (
        round((raw_paper_wins / raw_paper_total * 100.0), 2) if raw_paper_total > 0 else 0.0
    )
    raw_gp = float(raw_paper["gross_profit"])
    raw_gl = float(raw_paper["gross_loss"])
    raw_paper_pf = (
        round(raw_gp / raw_gl, 2)
        if raw_gl > 0
        else (round(raw_gp, 2) if raw_gp > 0 else 0.0)
    )

    # 2. Raw SQL aggregation for Real Executions
    real_sql = text(
        """
        SELECT
            count(*) AS total,
            count(*) FILTER (WHERE pnl_r > 0) AS wins,
            count(*) FILTER (WHERE pnl_r < 0) AS losses,
            count(*) FILTER (WHERE pnl_r = 0) AS be,
            coalesce(sum(pnl_usd), 0.0) AS total_usd,
            coalesce(sum(pnl_r), 0.0) AS total_r,
            coalesce(avg(slippage_points), 0.0) AS avg_slippage
        FROM real_executions
        WHERE exit_price IS NOT NULL;
        """
    )
    raw_real = (await session.execute(real_sql)).mappings().one()

    raw_real_total = int(raw_real["total"])
    raw_real_wins = int(raw_real["wins"])
    raw_real_losses = int(raw_real["losses"])
    raw_real_be = int(raw_real["be"])
    raw_real_usd = round(float(raw_real["total_usd"]), 2)
    raw_real_r = round(float(raw_real["total_r"]), 4)
    raw_real_wr = (
        round((raw_real_wins / raw_real_total * 100.0), 2) if raw_real_total > 0 else 0.0
    )
    raw_real_slippage = round(float(raw_real["avg_slippage"]), 4)

    # 3. Call traderadar.stats service
    paper_res = await get_journal_stats(session, book="paper", range_str="all")
    real_res = await get_journal_stats(session, book="real", range_str="all")

    # 4. Compare Paper Trades Parity
    p_kpi = paper_res.kpis
    assert p_kpi.total_trades == raw_paper_total, (
        f"Paper total mismatch: {p_kpi.total_trades} vs {raw_paper_total}"
    )
    assert p_kpi.win_trades == raw_paper_wins, (
        f"Paper wins mismatch: {p_kpi.win_trades} vs {raw_paper_wins}"
    )
    assert p_kpi.loss_trades == raw_paper_losses, (
        f"Paper losses mismatch: {p_kpi.loss_trades} vs {raw_paper_losses}"
    )
    assert p_kpi.be_trades == raw_paper_be, (
        f"Paper BE mismatch: {p_kpi.be_trades} vs {raw_paper_be}"
    )
    assert abs(p_kpi.winrate_pct - raw_paper_wr) < 0.01, (
        f"Paper winrate mismatch: {p_kpi.winrate_pct} vs {raw_paper_wr}"
    )
    assert abs(p_kpi.total_pnl_usd - raw_paper_usd) < 0.05, (
        f"Paper USD mismatch: {p_kpi.total_pnl_usd} vs {raw_paper_usd}"
    )
    assert abs(p_kpi.total_pnl_r - raw_paper_r) < 0.001, (
        f"Paper R mismatch: {p_kpi.total_pnl_r} vs {raw_paper_r}"
    )
    if raw_paper_total > 0 and raw_gl > 0:
        assert p_kpi.profit_factor is not None and abs(p_kpi.profit_factor - raw_paper_pf) < 0.05, (
            f"Paper PF mismatch: {p_kpi.profit_factor} vs {raw_paper_pf}"
        )

    # 5. Compare Real Executions Parity
    r_kpi = real_res.kpis
    assert r_kpi.total_trades == raw_real_total, (
        f"Real total mismatch: {r_kpi.total_trades} vs {raw_real_total}"
    )
    assert r_kpi.win_trades == raw_real_wins, (
        f"Real wins mismatch: {r_kpi.win_trades} vs {raw_real_wins}"
    )
    assert r_kpi.loss_trades == raw_real_losses, (
        f"Real losses mismatch: {r_kpi.loss_trades} vs {raw_real_losses}"
    )
    assert r_kpi.be_trades == raw_real_be, (
        f"Real BE mismatch: {r_kpi.be_trades} vs {raw_real_be}"
    )
    assert abs(r_kpi.winrate_pct - raw_real_wr) < 0.01, (
        f"Real winrate mismatch: {r_kpi.winrate_pct} vs {raw_real_wr}"
    )
    assert abs(r_kpi.total_pnl_usd - raw_real_usd) < 0.05, (
        f"Real USD mismatch: {r_kpi.total_pnl_usd} vs {raw_real_usd}"
    )
    assert abs(r_kpi.total_pnl_r - raw_real_r) < 0.001, (
        f"Real R mismatch: {r_kpi.total_pnl_r} vs {raw_real_r}"
    )
    assert (
        abs(real_res.slippage_metrics.avg_slippage_points - raw_real_slippage) < 0.001
    ), (
        f"Real slippage mismatch: {real_res.slippage_metrics.avg_slippage_points} vs "
        f"{raw_real_slippage}"
    )

    return {
        "status": "PASSED",
        "paper": {
            "total_trades": raw_paper_total,
            "winrate_pct": raw_paper_wr,
            "total_pnl_usd": raw_paper_usd,
            "total_pnl_r": raw_paper_r,
            "profit_factor": raw_paper_pf,
        },
        "real": {
            "total_trades": raw_real_total,
            "winrate_pct": raw_real_wr,
            "total_pnl_usd": raw_real_usd,
            "total_pnl_r": raw_real_r,
            "avg_slippage": raw_real_slippage,
        },
    }


async def main() -> None:
    """Run verification script standalone."""
    print("=" * 60)
    print("TradeRadar — Verifikasi Paritas SQL Independen vs traderadar.stats")
    print("=" * 60)
    try:
        async with get_db_session() as session:
            result = await verify_stats_parity(session)
            print("Status: [PASS] Semua angka agregasi SQL persis identik dengan API stats.")
            print(f"Paper Trades: {result['paper']}")
            print(f"Real Executions: {result['real']}")
            print("=" * 60)
    except AssertionError as ae:
        print(f"FAILED (Parity Mismatch): {ae}")
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
