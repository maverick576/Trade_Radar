"""API routes for Paper Trading operations (BLUEPRINT.md §5.5 & API_AND_DATA.md §4)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from traderadar.api.deps import get_current_user, get_db
from traderadar.api.schemas.paper import (
    ClosePaperTradeRequest,
    PaperAccountResponse,
    PaperTradeResponse,
)
from traderadar.core.config import get_app_settings
from traderadar.core.models import User
from traderadar.services.paper_store import (
    close_paper_trade_in_db,
    get_paper_account_metrics,
    get_paper_trades,
)

router = APIRouter(prefix="/paper", tags=["Paper Trading"])


@router.get("/trades", response_model=list[PaperTradeResponse])
async def list_paper_trades(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    symbol: Annotated[str | None, Query(description="Filter by symbol")] = None,
    status_filter: Annotated[
        str | None, Query(alias="status", description="Filter by status OPEN or CLOSED")
    ] = None,
    is_virtual: Annotated[
        bool | None, Query(description="Filter virtual (simulated blocked signals)")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[PaperTradeResponse]:
    """List paper trading positions and history."""
    records = await get_paper_trades(
        session=session,
        symbol=symbol,
        status=status_filter,
        is_virtual=is_virtual,
        limit=limit,
    )
    return [
        PaperTradeResponse(
            id=r.id,
            ticket_id=r.ticket_id,
            signal_id=r.signal_id,
            strategy=r.strategy,
            symbol=r.symbol,
            side=r.side,  # type: ignore[arg-type]
            entry_time=r.entry_time,
            entry_price=r.entry_price,
            size=r.size,
            sl=r.sl,
            tp1=r.tp1,
            tp2=r.tp2,
            tp1_hit=r.tp1_hit,
            bars_held=r.bars_held,
            status=r.status,
            exit_time=r.exit_time,
            exit_price=r.exit_price,
            exit_reason=r.exit_reason,
            pnl_usd=r.pnl_usd,
            pnl_r=r.pnl_r,
            fees_usd=r.fees_usd,
            mfe_r=r.mfe_r,
            mae_r=r.mae_r,
            is_virtual=r.is_virtual,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in records
    ]


@router.get("/account", response_model=PaperAccountResponse)
async def get_paper_account(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaperAccountResponse:
    """Get current virtual account summary, PnL, and daily limits."""
    settings = get_app_settings()
    initial_equity = settings.paper.initial_equity_usd
    daily_limit_pct = settings.paper.daily_loss_limit_pct

    metrics = await get_paper_account_metrics(
        session=session,
        initial_equity=initial_equity,
        daily_loss_limit_pct=daily_limit_pct,
    )
    return PaperAccountResponse(**metrics)


@router.post("/trades/{trade_id}/close", response_model=PaperTradeResponse)
async def close_paper_trade(
    trade_id: int,
    body: ClosePaperTradeRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaperTradeResponse:
    """Manually close an open paper trade."""
    record = await close_paper_trade_in_db(
        session=session,
        trade_id=trade_id,
        exit_price=body.exit_price,
        exit_time=body.exit_time,
        exit_reason=body.exit_reason,
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Posisi paper trade {trade_id} tidak ditemukan atau sudah ditutup",
        )
    return PaperTradeResponse(
        id=record.id,
        ticket_id=record.ticket_id,
        signal_id=record.signal_id,
        strategy=record.strategy,
        symbol=record.symbol,
        side=record.side,  # type: ignore[arg-type]
        entry_time=record.entry_time,
        entry_price=record.entry_price,
        size=record.size,
        sl=record.sl,
        tp1=record.tp1,
        tp2=record.tp2,
        tp1_hit=record.tp1_hit,
        bars_held=record.bars_held,
        status=record.status,
        exit_time=record.exit_time,
        exit_price=record.exit_price,
        exit_reason=record.exit_reason,
        pnl_usd=record.pnl_usd,
        pnl_r=record.pnl_r,
        fees_usd=record.fees_usd,
        mfe_r=record.mfe_r,
        mae_r=record.mae_r,
        is_virtual=record.is_virtual,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
