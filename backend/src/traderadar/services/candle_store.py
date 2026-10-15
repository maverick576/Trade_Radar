"""Candle and market snapshot persistence helpers supporting TimescaleDB and SQLite."""

from datetime import datetime
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from traderadar.core.logging import get_logger
from traderadar.core.models import Candle, DerivativesSnapshot, SentimentSnapshot

logger = get_logger("traderadar.candle_store")


CANDLE_COLUMNS = {
    "open_time",
    "symbol",
    "tf",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "taker_buy_volume",
    "source",
}

DERIVATIVES_COLUMNS = {
    "ts",
    "symbol",
    "funding",
    "mark",
    "open_interest",
    "ls_ratio",
}

SENTIMENT_COLUMNS = {
    "ts",
    "source",
    "value",
    "label",
}


async def upsert_candles(session: AsyncSession, candles_data: list[dict[str, Any]]) -> int:
    """Idempotently insert or update a batch of candles."""
    if not candles_data:
        return 0

    clean_data = [
        {k: v for k, v in item.items() if k in CANDLE_COLUMNS}
        for item in candles_data
    ]

    bind = session.bind
    is_postgres = bind is not None and bind.dialect.name == "postgresql"

    if is_postgres:
        stmt = pg_insert(Candle).values(clean_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["open_time", "symbol", "tf"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "taker_buy_volume": stmt.excluded.taker_buy_volume,
                "source": stmt.excluded.source,
            },
        )
        await session.execute(stmt)
    else:
        # Generic fallback for SQLite / tests
        for item in clean_data:
            # Delete any existing
            del_stmt = delete(Candle).where(
                Candle.symbol == item["symbol"],
                Candle.tf == item["tf"],
                Candle.open_time == item["open_time"],
            )
            await session.execute(del_stmt)
            obj = Candle(**item)
            session.add(obj)

    await session.commit()
    return len(clean_data)


async def get_latest_candle(
    session: AsyncSession, symbol: str, tf: str
) -> Candle | None:
    """Retrieve the most recent closed candle for symbol and tf."""
    stmt = (
        select(Candle)
        .where(Candle.symbol == symbol.upper(), Candle.tf == tf.upper())
        .order_by(desc(Candle.open_time))
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_candles(
    session: AsyncSession,
    symbol: str,
    tf: str,
    limit: int = 300,
    before: datetime | None = None,
) -> list[Candle]:
    """Fetch candles ordered chronologically ascending."""
    stmt = select(Candle).where(
        Candle.symbol == symbol.upper(),
        Candle.tf == tf.upper(),
    )
    if before:
        stmt = stmt.where(Candle.open_time < before)

    stmt = stmt.order_by(desc(Candle.open_time)).limit(limit)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    rows.reverse()  # Return in chronological order (oldest to newest)
    return rows


async def insert_derivatives_snapshot(
    session: AsyncSession, snapshot_data: dict[str, Any]
) -> None:
    """Insert snapshot of funding, mark, OI, and LS ratio."""
    clean_data = {k: v for k, v in snapshot_data.items() if k in DERIVATIVES_COLUMNS}
    bind = session.bind
    is_postgres = bind is not None and bind.dialect.name == "postgresql"

    if is_postgres:
        stmt = pg_insert(DerivativesSnapshot).values(clean_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ts", "symbol"],
            set_={
                "funding": stmt.excluded.funding,
                "mark": stmt.excluded.mark,
                "open_interest": stmt.excluded.open_interest,
                "ls_ratio": stmt.excluded.ls_ratio,
            },
        )
        await session.execute(stmt)
    else:
        obj = DerivativesSnapshot(**clean_data)
        session.add(obj)
    await session.commit()


async def insert_sentiment_snapshot(
    session: AsyncSession, sentiment_data: dict[str, Any]
) -> None:
    """Insert sentiment snapshot (Fear & Greed index)."""
    clean_data = {k: v for k, v in sentiment_data.items() if k in SENTIMENT_COLUMNS}
    bind = session.bind
    is_postgres = bind is not None and bind.dialect.name == "postgresql"

    if is_postgres:
        stmt = pg_insert(SentimentSnapshot).values(clean_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ts", "source"],
            set_={
                "value": stmt.excluded.value,
                "label": stmt.excluded.label,
            },
        )
        await session.execute(stmt)
    else:
        obj = SentimentSnapshot(**clean_data)
        session.add(obj)
    await session.commit()
