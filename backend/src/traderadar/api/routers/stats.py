"""Journal & statistics API routes (BLUEPRINT.md §5.9, API_AND_DATA.md §4)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from traderadar.api.deps import get_current_user, get_db
from traderadar.core.models import User
from traderadar.stats.models import (
    JournalResponse,
    TradeAnalysisSnapshotResponse,
)
from traderadar.stats.service import (
    export_journal_csv,
    get_journal_stats,
    get_trade_analysis_snapshot,
)

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=JournalResponse)
async def get_stats_endpoint(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    book: Annotated[
        str,
        Query(
            description="Trading book to analyze: paper, real, or compare",
            pattern="^(paper|real|compare)$",
        ),
    ] = "paper",
    range_str: Annotated[
        str,
        Query(
            alias="range",
            description="Time range filter preset: 7d, 30d, 90d, all, or custom",
        ),
    ] = "all",
    symbol: Annotated[str | None, Query(description="Optional symbol filter")] = None,
    strategy: Annotated[str | None, Query(description="Optional strategy filter")] = None,
    from_dt: Annotated[
        datetime | None, Query(description="Start datetime for custom range (UTC)")
    ] = None,
    to_dt: Annotated[
        datetime | None, Query(description="End datetime for custom range (UTC)")
    ] = None,
) -> JournalResponse:
    """Get full trading journal statistics, KPIs, equity curve, heatmap, and breakdowns."""
    return await get_journal_stats(
        session=session,
        book=book,
        range_str=range_str,
        symbol=symbol,
        strategy=strategy,
        from_dt=from_dt,
        to_dt=to_dt,
    )


@router.get("/export.csv")
async def export_journal_csv_endpoint(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    book: Annotated[
        str,
        Query(
            description="Trading book to export: paper, real, or compare",
            pattern="^(paper|real|compare)$",
        ),
    ] = "paper",
    range_str: Annotated[
        str,
        Query(
            alias="range",
            description="Time range filter preset: 7d, 30d, 90d, all, or custom",
        ),
    ] = "all",
    symbol: Annotated[str | None, Query(description="Optional symbol filter")] = None,
    strategy: Annotated[str | None, Query(description="Optional strategy filter")] = None,
    from_dt: Annotated[
        datetime | None, Query(description="Start datetime for custom range (UTC)")
    ] = None,
    to_dt: Annotated[
        datetime | None, Query(description="End datetime for custom range (UTC)")
    ] = None,
) -> Response:
    """Export filtered trading journal as RFC 4180 CSV file."""
    csv_content = await export_journal_csv(
        session=session,
        book=book,
        range_str=range_str,
        symbol=symbol,
        strategy=strategy,
        from_dt=from_dt,
        to_dt=to_dt,
    )

    filename = f"traderadar_journal_{book}_{range_str}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


@router.get("/trades/{trade_id}/snapshot", response_model=TradeAnalysisSnapshotResponse)
async def get_trade_snapshot_endpoint(
    trade_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    book: Annotated[str, Query(pattern="^(paper|real)$")] = "paper",
) -> TradeAnalysisSnapshotResponse:
    """Get technical analysis and 10-indicator snapshot at the time the trade was initiated."""
    snapshot = await get_trade_analysis_snapshot(session, trade_id=trade_id, book=book)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot analisa teknikal untuk trade {trade_id} ({book}) tidak ditemukan",
        )
    return snapshot
