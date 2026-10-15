"""REST API router for confluence analysis and signals."""

import json
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from traderadar.api.deps import get_current_user, get_db, get_redis_client
from traderadar.api.schemas.analysis import (
    AnalysisResponse,
    ScoreHistoryItem,
    ScoreHistoryResponse,
    SignalItem,
    SignalsResponse,
)
from traderadar.core.models import User
from traderadar.engine.strategies.konfluensi10 import ConfluencePipeline
from traderadar.services.analysis_store import (
    get_analysis_history,
    get_latest_analysis,
    get_signals,
    save_analysis_and_signals,
)
from traderadar.services.candle_store import get_candles
from traderadar.services.engine import build_market_context

router = APIRouter(prefix="", tags=["Analysis & Signals"])
pipeline = ConfluencePipeline()


@router.get("/analysis/{symbol}", response_model=AnalysisResponse)
async def get_latest_analysis_endpoint(
    symbol: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Any, Depends(get_redis_client)],
    tf: Annotated[str, Query(description="Timeframe e.g. M15")] = "M15",
    preview_live: Annotated[bool, Query(description="Evaluate on running bar if True")] = False,
) -> AnalysisResponse:
    """Get the latest confluence analysis for a symbol.

    If not cached or if preview_live is requested, computes on-the-fly.
    """
    sym_upper = symbol.upper()
    tf_upper = tf.upper()

    # 1. If not preview_live, check Redis cache first
    if not preview_live:
        try:
            cached_json = await redis_client.get(f"analysis:latest:{sym_upper}:{tf_upper}")
            if cached_json:
                data = json.loads(cached_json)
                return AnalysisResponse(**data)
        except Exception:
            pass

        # 2. Check Database record
        db_rec = await get_latest_analysis(db, sym_upper, tf_upper)
        if db_rec is not None:
            return AnalysisResponse(
                symbol=db_rec.symbol,
                tf=db_rec.tf,
                bar_time=db_rec.bar_time,
                source=db_rec.source,
                score=db_rec.score,
                verdict=db_rec.verdict,
                counts=db_rec.counts,
                indicators=db_rec.indicators,
                category_votes=db_rec.category_votes,
                htf=db_rec.htf,
                macro=db_rec.macro,
                strategy_b=db_rec.strategy_b,
                weights_version=db_rec.weights_version,
                created_at=db_rec.created_at,
            )

    # 3. If no record exists or preview_live, compute on-the-fly with available candles
    m15_rows = await get_candles(db, sym_upper, "M15", limit=300)
    if not m15_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data market candle belum tersedia untuk {sym_upper}",
        )

    def rows_to_df(rows: list[Any]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "open_time": r.open_time,
                    "open": r.open,
                    "high": r.high,
                    "low": r.low,
                    "close": r.close,
                    "volume": r.volume,
                    "taker_buy_volume": r.taker_buy_volume,
                }
                for r in rows
            ]
        )

    df_m15 = rows_to_df(m15_rows)

    # Append live unclosed bar from Redis if preview requested
    if preview_live:
        try:
            live_raw = await redis_client.get(f"live:bar:{sym_upper}:{tf_upper}")
            if live_raw:
                ld = json.loads(live_raw)
                live_row = pd.DataFrame(
                    [
                        {
                            "open_time": pd.to_datetime(ld["open_time"], utc=True),
                            "open": ld["open"],
                            "high": ld["high"],
                            "low": ld["low"],
                            "close": ld["close"],
                            "volume": ld["volume"],
                            "taker_buy_volume": None,
                        }
                    ]
                )
                df_m15 = pd.concat([df_m15, live_row], ignore_index=True)
        except Exception:
            pass

    h1_rows = await get_candles(db, sym_upper, "H1", limit=100)
    h4_rows = await get_candles(db, sym_upper, "H4", limit=100)
    d1_rows = await get_candles(db, sym_upper, "D1", limit=50)

    df_h1 = rows_to_df(h1_rows) if h1_rows else None
    df_h4 = rows_to_df(h4_rows) if h4_rows else None
    df_d1 = rows_to_df(d1_rows) if d1_rows else None

    context = await build_market_context(redis_client, sym_upper)

    source = m15_rows[-1].source if m15_rows else f"binance_futures:{sym_upper}"
    analysis, signals = pipeline.run_analysis(
        symbol=sym_upper,
        tf=tf_upper,
        source=source,
        df_m15=df_m15,
        df_h1=df_h1,
        df_h4=df_h4,
        df_d1=df_d1,
        context=context,
    )

    # If it's a closed bar evaluation and not in DB, save it
    if not preview_live:
        await save_analysis_and_signals(db, analysis, signals)

    return AnalysisResponse(
        symbol=analysis.symbol,
        tf=analysis.tf,
        bar_time=analysis.bar_time,
        source=analysis.source,
        score=analysis.score,
        verdict=analysis.verdict,
        counts=analysis.counts,
        indicators=analysis.indicators,
        category_votes=analysis.category_votes,
        htf=analysis.htf,
        macro=analysis.macro,
        strategy_b=analysis.strategy_b,
        weights_version=analysis.weights_version,
        created_at=analysis.created_at,
    )


@router.get("/analysis/{symbol}/history", response_model=ScoreHistoryResponse)
async def get_score_history_endpoint(
    symbol: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    tf: Annotated[str, Query(description="Timeframe e.g. M15")] = "M15",
    limit: Annotated[int, Query(ge=1, le=300, description="Max historical scores to return")] = 48,
) -> ScoreHistoryResponse:
    """Retrieve historical score time series for the 48-hour score history area chart."""
    sym_upper = symbol.upper()
    tf_upper = tf.upper()

    rows = await get_analysis_history(db, sym_upper, tf_upper, limit=limit)
    items = [
        ScoreHistoryItem(
            bar_time=r.bar_time,
            score=r.score,
            verdict=r.verdict,
        )
        for r in rows
    ]
    return ScoreHistoryResponse(
        symbol=sym_upper,
        tf=tf_upper,
        history=items,
    )


@router.get("/signals", response_model=SignalsResponse)
async def get_signals_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    symbol: Annotated[str | None, Query(description="Filter by symbol")] = None,
    strategy: Annotated[str | None, Query(description="Filter by strategy")] = None,
    status_filter: Annotated[
        str | None,
        Query(alias="status", description="Filter by status e.g. ticketed, blocked, watch"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Max signals to return")] = 50,
) -> SignalsResponse:
    """Retrieve trading signals including blocked and watch signals."""
    records = await get_signals(
        db,
        symbol=symbol,
        strategy=strategy,
        status=status_filter,
        limit=limit,
    )
    items = [
        SignalItem(
            id=r.id,
            analysis_id=r.analysis_id,
            strategy=r.strategy,
            symbol=r.symbol,
            tf=r.tf,
            side=r.side,
            verdict=r.verdict,
            bar_time=r.bar_time,
            status=r.status,
            blocked_by=r.blocked_by,
            confirmed_by_b=r.confirmed_by_b,
            created_at=r.created_at,
        )
        for r in records
    ]
    return SignalsResponse(signals=items, total=len(items))
