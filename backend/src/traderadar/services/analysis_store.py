"""Database store and repository for Analyses and Signals."""

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from traderadar.core.models import AnalysisRecord, SignalRecord
from traderadar.engine.strategies.konfluensi10 import Analysis, SignalRecordPayload


async def save_analysis_and_signals(
    session: AsyncSession,
    analysis: Analysis,
    signals: list[SignalRecordPayload],
) -> tuple[AnalysisRecord, list[SignalRecord]]:
    """Persist or update an Analysis and its generated Signals."""
    # Convert Pydantic models to dicts for JSON columns
    indicators_json = [ind.model_dump() for ind in analysis.indicators]
    macro_json = analysis.macro.model_dump()
    strategy_b_json = analysis.strategy_b.model_dump()

    stmt = select(AnalysisRecord).where(
        AnalysisRecord.symbol == analysis.symbol,
        AnalysisRecord.tf == analysis.tf,
        AnalysisRecord.bar_time == analysis.bar_time,
    )
    res = await session.execute(stmt)
    record = res.scalar_one_or_none()

    if record is None:
        record = AnalysisRecord(
            symbol=analysis.symbol,
            tf=analysis.tf,
            bar_time=analysis.bar_time,
            source=analysis.source,
            score=analysis.score,
            verdict=analysis.verdict,
            counts=analysis.counts,
            indicators=indicators_json,
            category_votes=analysis.category_votes,
            htf=analysis.htf,
            macro=macro_json,
            strategy_b=strategy_b_json,
            weights_version=analysis.weights_version,
            created_at=analysis.created_at,
        )
        session.add(record)
        await session.flush()
    else:
        record.source = analysis.source
        record.score = analysis.score
        record.verdict = analysis.verdict
        record.counts = analysis.counts
        record.indicators = indicators_json
        record.category_votes = analysis.category_votes
        record.htf = analysis.htf
        record.macro = macro_json
        record.strategy_b = strategy_b_json
        record.weights_version = analysis.weights_version
        await session.flush()

    saved_signals: list[SignalRecord] = []
    for sig in signals:
        sig_rec = SignalRecord(
            analysis_id=record.id,
            strategy=sig.strategy,
            symbol=sig.symbol,
            tf=sig.tf,
            side=sig.side,
            verdict=sig.verdict,
            bar_time=sig.bar_time,
            status=sig.status,
            blocked_by=sig.blocked_by,
            confirmed_by_b=sig.confirmed_by_b,
            created_at=sig.created_at,
        )
        session.add(sig_rec)
        saved_signals.append(sig_rec)

    await session.commit()
    await session.refresh(record)
    return record, saved_signals


async def get_latest_analysis(
    session: AsyncSession,
    symbol: str,
    tf: str = "M15",
) -> AnalysisRecord | None:
    """Retrieve the most recent closed-candle Analysis for a symbol and timeframe."""
    stmt = (
        select(AnalysisRecord)
        .where(AnalysisRecord.symbol == symbol.upper(), AnalysisRecord.tf == tf.upper())
        .order_by(desc(AnalysisRecord.bar_time))
        .limit(1)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_analysis_history(
    session: AsyncSession,
    symbol: str,
    tf: str = "M15",
    limit: int = 48,
) -> list[AnalysisRecord]:
    """Retrieve historical analyses for score history charting (ascending order)."""
    stmt = (
        select(AnalysisRecord)
        .where(AnalysisRecord.symbol == symbol.upper(), AnalysisRecord.tf == tf.upper())
        .order_by(desc(AnalysisRecord.bar_time))
        .limit(limit)
    )
    res = await session.execute(stmt)
    rows = list(res.scalars().all())
    rows.reverse()
    return rows


async def get_signals(
    session: AsyncSession,
    symbol: str | None = None,
    strategy: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[SignalRecord]:
    """Query recent signals with optional filters."""
    stmt = select(SignalRecord).order_by(desc(SignalRecord.bar_time)).limit(limit)
    if symbol:
        stmt = stmt.where(SignalRecord.symbol == symbol.upper())
    if strategy:
        stmt = stmt.where(SignalRecord.strategy == strategy.lower())
    if status:
        stmt = stmt.where(SignalRecord.status == status.lower())

    res = await session.execute(stmt)
    return list(res.scalars().all())
