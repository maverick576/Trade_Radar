"""API routes for Trade Tickets and Real Executions."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from traderadar.api.deps import get_current_user, get_db
from traderadar.api.schemas.tickets import (
    CloseTicketRequest,
    ExecuteTicketRequest,
    RealExecutionResponse,
    TicketResponse,
)
from traderadar.core.config import get_app_settings
from traderadar.core.models import TicketRecord, User
from traderadar.engine.ticket import (
    TradeTicket,
    apply_broker_offset,
    format_ticket_compact,
    format_ticket_full,
)
from traderadar.services.ticket_store import (
    close_real_execution,
    get_latest_broker_calibration,
    get_ticket_by_id,
    get_tickets,
    record_execution,
    update_ticket_status,
)

router = APIRouter(prefix="/tickets", tags=["Tickets & Real Executions"])


def _serialize_ticket(ticket: TicketRecord, offset: float | None = None) -> TicketResponse:
    """Helper to convert TicketRecord to TicketResponse with formatted texts."""
    settings = get_app_settings()
    profile = next((b for b in settings.brokers if b.name == ticket.broker_profile), None)
    if not profile and settings.brokers:
        profile = settings.brokers[0]

    t_side: Any = ticket.side
    t_status: Any = ticket.status
    t_engine = TradeTicket(
        id=ticket.id,
        signal_id=ticket.signal_id,
        symbol=ticket.symbol,
        side=t_side,
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
        reasons=ticket.reasons or [],
        risks=ticket.risks or [],
        valid_until=ticket.valid_until,
        status=t_status,
        broker_offset=offset if offset is not None else ticket.broker_offset,
        broker_profile=ticket.broker_profile or (profile.name if profile else None),
        suggested_lot=ticket.suggested_lot,
        actual_risk_usd=ticket.actual_risk_usd,
        actual_risk_pct=ticket.actual_risk_pct,
        min_lot_warning=ticket.min_lot_warning,
        warning_message=ticket.warning_message,
        created_at=ticket.created_at,
    )

    if offset is not None and offset != 0.0:
        t_engine = apply_broker_offset(t_engine, offset)

    text_full = format_ticket_full(t_engine, broker_profile=profile)
    text_compact = format_ticket_compact(t_engine)

    return TicketResponse(
        id=ticket.id,
        signal_id=ticket.signal_id,
        symbol=t_engine.symbol,
        side=t_engine.side,
        strategy=t_engine.strategy,
        score=t_engine.score,
        source=t_engine.source,
        entry=t_engine.entry,
        entry_low=t_engine.entry_low,
        entry_high=t_engine.entry_high,
        sl=t_engine.sl,
        tp1=t_engine.tp1,
        tp2=t_engine.tp2,
        atr=t_engine.atr,
        sl_points=t_engine.sl_points,
        sl_atr_mult=t_engine.sl_atr_mult,
        tp1_points=t_engine.tp1_points,
        tp2_points=t_engine.tp2_points,
        invalidation=t_engine.invalidation,
        reasons=t_engine.reasons,
        risks=t_engine.risks,
        valid_until=t_engine.valid_until,
        status=ticket.status,
        broker_offset=t_engine.broker_offset,
        broker_profile=t_engine.broker_profile,
        suggested_lot=t_engine.suggested_lot,
        actual_risk_usd=t_engine.actual_risk_usd,
        actual_risk_pct=t_engine.actual_risk_pct,
        min_lot_warning=t_engine.min_lot_warning,
        warning_message=t_engine.warning_message,
        text_full=text_full,
        text_compact=text_compact,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


@router.get("", response_model=list[TicketResponse])
async def list_tickets(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    symbol: Annotated[str | None, Query(description="Filter by symbol")] = None,
    status_filter: Annotated[
        str | None, Query(alias="status", description="Filter by status")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[TicketResponse]:
    """List trade tickets with optional filters."""
    records = await get_tickets(session, symbol=symbol, status=status_filter, limit=limit)
    res: list[TicketResponse] = []
    for r in records:
        cal = await get_latest_broker_calibration(session, r.symbol)
        offset = cal.offset if cal else None
        res.append(_serialize_ticket(r, offset=offset))
    return res


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TicketResponse:
    """Get single ticket details with active broker calibration."""
    record = await get_ticket_by_id(session, ticket_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} tidak ditemukan",
        )
    cal = await get_latest_broker_calibration(session, record.symbol)
    offset = cal.offset if cal else None
    return _serialize_ticket(record, offset=offset)


@router.post("/{ticket_id}/execute", response_model=RealExecutionResponse)
async def execute_ticket_endpoint(
    ticket_id: int,
    body: ExecuteTicketRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RealExecutionResponse:
    """Record that the user has manually executed the ticket at a broker."""
    try:
        execution, _ = await record_execution(
            session=session,
            ticket_id=ticket_id,
            broker_profile=body.broker_profile,
            fill_price=body.fill_price,
            lot=body.lot,
            fill_time=body.fill_time,
            source=body.source,
            notes=body.notes,
        )
        return RealExecutionResponse(
            id=execution.id,
            ticket_id=execution.ticket_id,
            broker_profile=execution.broker_profile,
            fill_price=execution.fill_price,
            lot=execution.lot,
            fill_time=execution.fill_time,
            exit_price=execution.exit_price,
            exit_time=execution.exit_time,
            pnl_usd=execution.pnl_usd,
            pnl_r=execution.pnl_r,
            slippage_points=execution.slippage_points,
            source=execution.source,
            notes=execution.notes,
            created_at=execution.created_at,
            updated_at=execution.updated_at,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/{ticket_id}/close", response_model=RealExecutionResponse)
async def close_ticket_endpoint(
    ticket_id: int,
    body: CloseTicketRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RealExecutionResponse:
    """Close an executed trade and record PnL in the real execution journal."""
    try:
        execution, _ = await close_real_execution(
            session=session,
            ticket_id=ticket_id,
            exit_price=body.exit_price,
            exit_time=body.exit_time,
            notes=body.notes,
        )
        return RealExecutionResponse(
            id=execution.id,
            ticket_id=execution.ticket_id,
            broker_profile=execution.broker_profile,
            fill_price=execution.fill_price,
            lot=execution.lot,
            fill_time=execution.fill_time,
            exit_price=execution.exit_price,
            exit_time=execution.exit_time,
            pnl_usd=execution.pnl_usd,
            pnl_r=execution.pnl_r,
            slippage_points=execution.slippage_points,
            source=execution.source,
            notes=execution.notes,
            created_at=execution.created_at,
            updated_at=execution.updated_at,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/{ticket_id}/skip", response_model=TicketResponse)
async def skip_ticket_endpoint(
    ticket_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TicketResponse:
    """Mark a trade ticket as skipped."""
    record = await update_ticket_status(session, ticket_id, "skipped")
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} tidak ditemukan",
        )
    return _serialize_ticket(record)
