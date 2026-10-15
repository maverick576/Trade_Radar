"""API routes for broker price calibrations (BLUEPRINT.md §5.3 & API_AND_DATA.md §4)."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from traderadar.api.deps import get_current_user, get_db, get_redis_client
from traderadar.api.schemas.tickets import CalibrationRequest, CalibrationResponse
from traderadar.core.models import User
from traderadar.core.time import ensure_utc, utc_now
from traderadar.services.candle_store import get_latest_candle
from traderadar.services.ticket_store import (
    get_latest_broker_calibration,
    save_broker_calibration,
)

router = APIRouter(prefix="/calibrations", tags=["Broker Calibrations"])


@router.post("", response_model=CalibrationResponse)
async def create_calibration(
    body: CalibrationRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CalibrationResponse:
    """Set broker price offset valid for 30 minutes."""
    clean_sym = body.symbol.upper().replace("USDT", "").replace("_", "")
    if clean_sym == "XAU":
        clean_sym = "XAUUSD"

    # Try to find current source price: 1. From Redis tick or 2. From DB candle
    source_price = None
    tick_raw = await redis_client.get(f"tick:{body.symbol.upper()}")
    if not tick_raw and "XAU" in clean_sym:
        tick_raw = await redis_client.get("tick:XAUUSDT")

    if tick_raw:
        try:
            source_price = float(tick_raw)
        except (ValueError, TypeError):
            pass

    if source_price is None:
        candle = await get_latest_candle(session, body.symbol.upper(), "M15")
        if not candle and "XAU" in clean_sym:
            candle = await get_latest_candle(session, "XAUUSDT", "M15")
        if candle:
            source_price = candle.close

    if source_price is None:
        # Fallback to broker price if no candle exists yet
        source_price = body.broker_price

    expires_at = utc_now() + timedelta(minutes=30)
    record = await save_broker_calibration(
        session=session,
        symbol=clean_sym,
        broker_profile=body.broker_profile,
        broker_price=body.broker_price,
        source_price=source_price,
        expires_at=expires_at,
    )

    # Cache active offset in Redis with 30m TTL
    await redis_client.set(
        f"calibration:{clean_sym}",
        str(record.offset),
        ex=1800,
    )

    return CalibrationResponse(
        id=record.id,
        symbol=record.symbol,
        broker_profile=record.broker_profile,
        broker_price=record.broker_price,
        source_price=record.source_price,
        offset=record.offset,
        created_at=record.created_at,
        expires_at=record.expires_at,
        is_active=True,
    )


@router.get("/latest", response_model=CalibrationResponse)
async def get_latest_calibration_endpoint(
    symbol: Annotated[str, Query(description="Symbol e.g. XAUUSD")],
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    broker_profile: Annotated[str | None, Query(description="Broker profile filter")] = None,
) -> CalibrationResponse:
    """Retrieve active broker calibration offset if not expired."""
    clean_sym = symbol.upper().replace("USDT", "").replace("_", "")
    if clean_sym == "XAU":
        clean_sym = "XAUUSD"

    record = await get_latest_broker_calibration(session, clean_sym, broker_profile)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tidak ada kalibrasi aktif untuk {symbol}",
        )

    return CalibrationResponse(
        id=record.id,
        symbol=record.symbol,
        broker_profile=record.broker_profile,
        broker_price=record.broker_price,
        source_price=record.source_price,
        offset=record.offset,
        created_at=record.created_at,
        expires_at=record.expires_at,
        is_active=ensure_utc(record.expires_at) > utc_now(),
    )
