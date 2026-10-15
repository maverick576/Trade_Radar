"""Persistence and management operations for Paper Trading positions and journal."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from traderadar.core.logging import get_logger
from traderadar.core.models import PaperTradeRecord
from traderadar.core.time import utc_now
from traderadar.engine.paper import PaperTradeState

logger = get_logger("traderadar.services.paper_store")
WIB = ZoneInfo("Asia/Jakarta")


async def save_paper_trade(session: AsyncSession, trade: PaperTradeState) -> PaperTradeRecord:
    """Persist a new paper trading position."""
    record = PaperTradeRecord(
        ticket_id=trade.ticket_id,
        signal_id=trade.signal_id,
        strategy=trade.strategy,
        symbol=trade.symbol,
        side=trade.side,
        entry_time=trade.entry_time,
        entry_price=trade.entry_price,
        size=trade.size,
        sl=trade.current_sl,
        tp1=trade.tp1,
        tp2=trade.tp2,
        tp1_hit=trade.tp1_hit,
        bars_held=trade.bars_held,
        status=trade.status,
        exit_time=trade.exit_time,
        exit_price=trade.exit_price,
        exit_reason=trade.exit_reason,
        pnl_usd=trade.pnl_usd,
        pnl_r=trade.pnl_r,
        fees_usd=trade.fees_usd,
        mfe_r=trade.mfe_r,
        mae_r=trade.mae_r,
        is_virtual=trade.is_virtual,
        created_at=trade.created_at,
        updated_at=trade.created_at,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def get_open_paper_trades(
    session: AsyncSession,
    symbol: str | None = None,
    is_virtual: bool | None = None,
) -> list[PaperTradeRecord]:
    """Retrieve all open paper trades."""
    stmt = select(PaperTradeRecord).where(PaperTradeRecord.status == "OPEN")
    if symbol:
        stmt = stmt.where(PaperTradeRecord.symbol == symbol.upper())
    if is_virtual is not None:
        stmt = stmt.where(PaperTradeRecord.is_virtual == is_virtual)
    stmt = stmt.order_by(PaperTradeRecord.entry_time.asc())

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_paper_trades(
    session: AsyncSession,
    symbol: str | None = None,
    status: str | None = None,
    is_virtual: bool | None = None,
    limit: int = 100,
) -> list[PaperTradeRecord]:
    """Retrieve paper trades with filtering ordered by entry time descending."""
    stmt = select(PaperTradeRecord).order_by(desc(PaperTradeRecord.entry_time)).limit(limit)
    if symbol:
        clean_sym = symbol.upper().replace("USDT", "").replace("_", "")
        if clean_sym == "XAU":
            clean_sym = "XAUUSD"
        stmt = stmt.where(
            (PaperTradeRecord.symbol == clean_sym)
            | (PaperTradeRecord.symbol == symbol.upper())
        )
    if status:
        stmt = stmt.where(PaperTradeRecord.status == status)
    if is_virtual is not None:
        stmt = stmt.where(PaperTradeRecord.is_virtual == is_virtual)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_paper_trade_record(
    session: AsyncSession, trade: PaperTradeState
) -> PaperTradeRecord | None:
    """Update database record from PaperTradeState."""
    if trade.id is None:
        return None
    record = await session.get(PaperTradeRecord, trade.id)
    if not record:
        return None

    record.sl = trade.current_sl
    record.tp1_hit = trade.tp1_hit
    record.bars_held = trade.bars_held
    record.status = trade.status
    record.exit_time = trade.exit_time
    record.exit_price = trade.exit_price
    record.exit_reason = trade.exit_reason
    record.pnl_usd = trade.pnl_usd
    record.pnl_r = trade.pnl_r
    record.fees_usd = trade.fees_usd
    record.mfe_r = trade.mfe_r
    record.mae_r = trade.mae_r
    record.updated_at = utc_now()

    await session.commit()
    await session.refresh(record)
    return record


async def close_paper_trade_in_db(
    session: AsyncSession,
    trade_id: int,
    exit_price: float,
    exit_time: datetime | None = None,
    exit_reason: str = "MANUAL",
) -> PaperTradeRecord | None:
    """Manually close an open paper trade in the database."""
    record = await session.get(PaperTradeRecord, trade_id)
    if not record or record.status != "OPEN":
        return None

    close_time = exit_time or utc_now()
    r = abs(record.entry_price - record.sl)
    if r <= 0:
        r = 1e-4

    # Calculate PnL
    if record.tp1_hit:
        tp1_r = 1.0
        if record.side == "LONG":
            rem_r = (exit_price - record.entry_price) / r
        else:
            rem_r = (record.entry_price - exit_price) / r
        pnl_r = 0.5 * tp1_r + 0.5 * rem_r
        gross_usd = pnl_r * (record.size * r)
    else:
        if record.side == "LONG":
            pts = exit_price - record.entry_price
        else:
            pts = record.entry_price - exit_price
        pnl_r = pts / r
        gross_usd = record.size * pts

    exit_fee = record.size * exit_price * 0.0005
    total_fees = record.fees_usd + exit_fee

    record.status = "CLOSED"
    record.exit_time = close_time
    record.exit_price = round(exit_price, 4)
    record.exit_reason = exit_reason
    record.fees_usd = round(total_fees, 4)
    record.pnl_usd = round(gross_usd - total_fees, 2)
    record.pnl_r = round(pnl_r, 4)
    record.updated_at = utc_now()

    await session.commit()
    await session.refresh(record)
    return record


async def get_paper_account_metrics(
    session: AsyncSession,
    initial_equity: float = 1000.0,
    daily_loss_limit_pct: float = 3.0,
) -> dict[str, Any]:
    """Calculate summary metrics for paper trading dashboard and risk limits."""
    # Closed real paper trades
    stmt = select(PaperTradeRecord).where(
        (PaperTradeRecord.is_virtual == False) & (PaperTradeRecord.status == "CLOSED")  # noqa: E712
    )
    result = await session.execute(stmt)
    closed_trades = list(result.scalars().all())

    total_realized_usd = sum((t.pnl_usd or 0.0) for t in closed_trades)
    current_equity = initial_equity + total_realized_usd

    # Daily realized PnL since 00:00 WIB today
    now_wib = utc_now().astimezone(WIB)
    start_of_day_wib = now_wib.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_day_utc = start_of_day_wib.astimezone(ZoneInfo("UTC"))

    daily_trades = [
        t for t in closed_trades if t.exit_time and t.exit_time >= start_of_day_utc
    ]
    daily_pnl_usd = sum((t.pnl_usd or 0.0) for t in daily_trades)
    daily_loss_limit_hit = daily_pnl_usd <= -(initial_equity * (daily_loss_limit_pct / 100.0))

    # Count open positions
    open_stmt = select(func.count(PaperTradeRecord.id)).where(
        (PaperTradeRecord.is_virtual == False) & (PaperTradeRecord.status == "OPEN")  # noqa: E712
    )
    open_count = await session.scalar(open_stmt) or 0

    # Winrate and Expectancy
    wins = [t for t in closed_trades if (t.pnl_r or 0.0) > 0]
    winrate = (len(wins) / len(closed_trades) * 100.0) if closed_trades else 0.0
    avg_r = (
        sum((t.pnl_r or 0.0) for t in closed_trades) / len(closed_trades)
        if closed_trades
        else 0.0
    )

    return {
        "initial_equity": initial_equity,
        "equity": round(current_equity, 2),
        "realized_pnl_usd": round(total_realized_usd, 2),
        "daily_pnl_usd": round(daily_pnl_usd, 2),
        "daily_loss_limit_hit": daily_loss_limit_hit,
        "open_positions_count": open_count,
        "total_closed_trades": len(closed_trades),
        "winrate_pct": round(winrate, 1),
        "expectancy_r": round(avg_r, 2),
    }
