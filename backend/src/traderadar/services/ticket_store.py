"""Persistence and retrieval operations for Trade Tickets, Calibrations, and Real Executions."""

from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from traderadar.core.logging import get_logger
from traderadar.core.models import BrokerCalibrationRecord, RealExecutionRecord, TicketRecord
from traderadar.core.time import ensure_utc, utc_now
from traderadar.engine.ticket import TradeTicket

logger = get_logger("traderadar.services.ticket_store")


async def save_ticket(session: AsyncSession, ticket: TradeTicket) -> TicketRecord:
    """Persist a new TradeTicket or return existing if already saved."""
    if ticket.signal_id:
        existing = await session.scalar(
            select(TicketRecord).where(TicketRecord.signal_id == ticket.signal_id)
        )
        if existing:
            return existing

    record = TicketRecord(
        signal_id=ticket.signal_id,
        symbol=ticket.symbol,
        side=ticket.side,
        strategy=ticket.strategy,
        score=ticket.score,
        source=ticket.source,
        entry=ticket.entry,
        entry_low=ticket.entry_low,
        entry_high=ticket.entry_high,
        sl=ticket.sl,
        tp1=ticket.tp1,
        tp2=ticket.tp2,
        atr=ticket.atr,
        sl_points=ticket.sl_points,
        sl_atr_mult=ticket.sl_atr_mult,
        tp1_points=ticket.tp1_points,
        tp2_points=ticket.tp2_points,
        invalidation=ticket.invalidation,
        reasons=ticket.reasons,
        risks=ticket.risks,
        valid_until=ticket.valid_until,
        status=ticket.status,
        broker_offset=ticket.broker_offset,
        broker_profile=ticket.broker_profile,
        suggested_lot=ticket.suggested_lot,
        actual_risk_usd=ticket.actual_risk_usd,
        actual_risk_pct=ticket.actual_risk_pct,
        min_lot_warning=ticket.min_lot_warning,
        warning_message=ticket.warning_message,
        created_at=ticket.created_at,
        updated_at=ticket.created_at,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def get_ticket_by_id(session: AsyncSession, ticket_id: int) -> TicketRecord | None:
    """Retrieve ticket by ID with eager-loaded signal relation."""
    stmt = (
        select(TicketRecord)
        .options(selectinload(TicketRecord.signal))
        .where(TicketRecord.id == ticket_id)
    )
    res = await session.scalar(stmt)
    if isinstance(res, TicketRecord):
        return res
    return None


async def get_tickets(
    session: AsyncSession,
    symbol: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[TicketRecord]:
    """Retrieve trade tickets ordered by creation time descending."""
    stmt = select(TicketRecord).order_by(desc(TicketRecord.created_at)).limit(limit)
    if symbol:
        clean_sym = symbol.upper().replace("USDT", "").replace("_", "")
        if clean_sym == "XAU":
            clean_sym = "XAUUSD"
        stmt = stmt.where(
            (TicketRecord.symbol == clean_sym) | (TicketRecord.symbol == symbol.upper())
        )
    if status:
        stmt = stmt.where(TicketRecord.status == status)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_ticket_status(
    session: AsyncSession, ticket_id: int, status: str
) -> TicketRecord | None:
    """Update status of a ticket."""
    ticket = await session.get(TicketRecord, ticket_id)
    if not ticket:
        return None
    ticket.status = status
    ticket.updated_at = utc_now()
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def record_execution(
    session: AsyncSession,
    ticket_id: int,
    broker_profile: str,
    fill_price: float,
    lot: float,
    fill_time: datetime | None = None,
    source: str = "ui",
    notes: str | None = None,
) -> tuple[RealExecutionRecord, TicketRecord]:
    """Record manual real execution for a ticket, updating its status to 'executed'."""
    ticket = await session.get(TicketRecord, ticket_id)
    if not ticket:
        raise ValueError(f"Ticket {ticket_id} not found")

    exec_time = fill_time or utc_now()

    # Direction-aware slippage in price points (fill - entry for LONG, entry - fill for SHORT)
    if ticket.side == "LONG":
        slippage = fill_price - ticket.entry
    else:
        slippage = ticket.entry - fill_price

    execution = RealExecutionRecord(
        ticket_id=ticket.id,
        broker_profile=broker_profile,
        fill_price=fill_price,
        lot=lot,
        fill_time=exec_time,
        slippage_points=round(slippage, 4),
        source=source,
        notes=notes,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(execution)

    ticket.status = "executed"
    ticket.updated_at = utc_now()

    await session.commit()
    await session.refresh(execution)
    await session.refresh(ticket)

    return execution, ticket


async def close_real_execution(
    session: AsyncSession,
    ticket_id: int,
    exit_price: float,
    exit_time: datetime | None = None,
    notes: str | None = None,
) -> tuple[RealExecutionRecord, TicketRecord]:
    """Close real execution and compute realized PnL."""
    ticket = await session.get(TicketRecord, ticket_id)
    if not ticket:
        raise ValueError(f"Ticket {ticket_id} not found")

    stmt = (
        select(RealExecutionRecord)
        .where(RealExecutionRecord.ticket_id == ticket_id)
        .order_by(desc(RealExecutionRecord.created_at))
        .limit(1)
    )
    execution = await session.scalar(stmt)
    if not execution:
        raise ValueError(f"No execution found for ticket {ticket_id}")

    close_time = exit_time or utc_now()
    execution.exit_price = exit_price
    execution.exit_time = close_time
    if notes:
        execution.notes = f"{execution.notes or ''}\n{notes}".strip()

    # PnL in USD and R
    # In Gold: lot * contract_size (100) * points. In crypto: lot * contract_size * points.
    contract_size = 100.0 if "XAU" in ticket.symbol.upper() else 1.0
    r_dist = abs(ticket.entry - ticket.sl)
    if r_dist <= 0:
        r_dist = 1.0

    if ticket.side == "LONG":
        points = exit_price - execution.fill_price
    else:
        points = execution.fill_price - exit_price

    pnl_usd = execution.lot * contract_size * points
    pnl_r = points / r_dist

    execution.pnl_usd = round(pnl_usd, 2)
    execution.pnl_r = round(pnl_r, 4)
    execution.updated_at = utc_now()

    ticket.status = "closed"
    ticket.updated_at = utc_now()

    await session.commit()
    await session.refresh(execution)
    await session.refresh(ticket)

    return execution, ticket


async def save_broker_calibration(
    session: AsyncSession,
    symbol: str,
    broker_profile: str,
    broker_price: float,
    source_price: float,
    expires_at: datetime,
) -> BrokerCalibrationRecord:
    """Save a new broker calibration offset record."""
    offset = round(broker_price - source_price, 4)
    clean_sym = symbol.upper().replace("USDT", "").replace("_", "")
    if clean_sym == "XAU":
        clean_sym = "XAUUSD"

    record = BrokerCalibrationRecord(
        symbol=clean_sym,
        broker_profile=broker_profile,
        broker_price=broker_price,
        source_price=source_price,
        offset=offset,
        created_at=utc_now(),
        expires_at=expires_at,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def get_latest_broker_calibration(
    session: AsyncSession,
    symbol: str,
    broker_profile: str | None = None,
) -> BrokerCalibrationRecord | None:
    """Retrieve the latest unexpired calibration for a symbol."""
    clean_sym = symbol.upper().replace("USDT", "").replace("_", "")
    if clean_sym == "XAU":
        clean_sym = "XAUUSD"

    now = utc_now()
    stmt = (
        select(BrokerCalibrationRecord)
        .where(BrokerCalibrationRecord.symbol == clean_sym)
        .order_by(desc(BrokerCalibrationRecord.created_at))
        .limit(1)
    )
    if broker_profile:
        stmt = stmt.where(BrokerCalibrationRecord.broker_profile == broker_profile)

    rec = await session.scalar(stmt)
    if rec and ensure_utc(rec.expires_at) <= now:
        return None
    return rec
