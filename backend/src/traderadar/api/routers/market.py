"""REST API router for market data (/symbols, /candles)."""

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from traderadar.api.deps import get_current_user, get_db, get_redis_client
from traderadar.api.schemas.market import CandleItem, SymbolItem, SymbolsResponse
from traderadar.core.config import get_settings
from traderadar.core.models import User
from traderadar.core.time import get_gold_market_status
from traderadar.services.candle_store import get_candles, get_latest_candle
from traderadar.services.gold_source import GoldSourceManager

router = APIRouter(tags=["Market Data"])
gold_manager = GoldSourceManager()


@router.get("/symbols", response_model=SymbolsResponse)
async def get_symbols(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Any, Depends(get_redis_client)],
) -> SymbolsResponse:
    """Retrieve watchlist symbols, live prices, capabilities, and active sources."""
    settings = get_settings()
    items: list[SymbolItem] = []

    for item in settings.app.watchlist:
        sym = item.symbol
        asset = item.asset
        is_gold = asset == "gold"

        active_source = (
            gold_manager.active_source if is_gold else f"binance_futures:{sym}"
        )
        is_fallback = gold_manager.is_fallback if is_gold else False

        # Live price from Redis with graceful fallback
        price: float | None = None
        try:
            price_str = await redis_client.get(f"price:{sym}")
            price = float(price_str) if price_str else None
        except Exception:
            pass

        # Fallback to DB latest candle close if Redis is cold
        if price is None:
            latest = await get_latest_candle(db, sym, "M15")
            if latest:
                price = latest.close

        # Daily stats from D1 candle
        latest_d1 = await get_latest_candle(db, sym, "D1")
        change_24h: float | None = None
        high_24h: float | None = None
        low_24h: float | None = None
        if latest_d1 and latest_d1.open > 0:
            diff = (price or latest_d1.close) - latest_d1.open
            change_24h = round((diff / latest_d1.open) * 100, 2)
            high_24h = latest_d1.high
            low_24h = latest_d1.low

        capabilities = [
            "vwap",
            "ema_ribbon",
            "supertrend",
            "rsi_div",
            "bollinger",
            "cvd_obv",
            "orderbook",
        ]
        if not is_gold or not is_fallback:
            capabilities.extend(["funding_oi", "sentiment"])

        gold_status = get_gold_market_status() if is_gold else None

        items.append(
            SymbolItem(
                symbol=sym,
                display=item.display,
                asset=asset,
                active_source=active_source,
                is_fallback=is_fallback,
                price=price,
                change_24h=change_24h,
                high_24h=high_24h,
                low_24h=low_24h,
                capabilities=capabilities,
                gold_status=gold_status,
            )
        )

    return SymbolsResponse(symbols=items)


@router.get("/candles", response_model=list[CandleItem])
async def get_candles_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Any, Depends(get_redis_client)],
    symbol: Annotated[str, Query(description="Market symbol e.g. BTCUSDT or XAUUSD")],
    tf: Annotated[str, Query(description="Timeframe e.g. M15, H1, H4, D1")] = "M15",
    limit: Annotated[int, Query(ge=1, le=1500, description="Max candles to return")] = 300,
) -> list[CandleItem]:
    """Retrieve historical closed candles plus the latest running bar if active."""
    sym_upper = symbol.upper()
    tf_upper = tf.upper()

    db_rows = await get_candles(db, sym_upper, tf_upper, limit=limit)
    candles: list[CandleItem] = [
        CandleItem(
            symbol=row.symbol,
            tf=row.tf,
            open_time=row.open_time,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
            taker_buy_volume=row.taker_buy_volume,
            source=row.source,
            is_closed=True,
        )
        for row in db_rows
    ]

    # Append live unclosed bar from Redis if available
    live_raw = None
    try:
        live_raw = await redis_client.get(f"live:bar:{sym_upper}:{tf_upper}")
    except Exception:
        pass
    if live_raw:
        try:
            live_dict = json.loads(live_raw)
            # Only append if newer than latest closed candle
            from datetime import datetime
            open_dt = datetime.fromisoformat(live_dict["open_time"])
            if not candles or open_dt >= candles[-1].open_time:
                if candles and open_dt == candles[-1].open_time:
                    # Update the bar
                    candles[-1] = CandleItem(
                        symbol=sym_upper,
                        tf=tf_upper,
                        open_time=open_dt,
                        open=live_dict["open"],
                        high=live_dict["high"],
                        low=live_dict["low"],
                        close=live_dict["close"],
                        volume=live_dict["volume"],
                        taker_buy_volume=None,
                        source="live",
                        is_closed=False,
                    )
                else:
                    candles.append(
                        CandleItem(
                            symbol=sym_upper,
                            tf=tf_upper,
                            open_time=open_dt,
                            open=live_dict["open"],
                            high=live_dict["high"],
                            low=live_dict["low"],
                            close=live_dict["close"],
                            volume=live_dict["volume"],
                            taker_buy_volume=None,
                            source="live",
                            is_closed=False,
                        )
                    )
        except Exception:
            pass

    return candles
