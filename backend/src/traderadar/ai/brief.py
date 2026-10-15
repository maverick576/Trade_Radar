"""Market Brief compiler and builder."""

from datetime import timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from traderadar.ai.schemas import MarketBriefPayload, SymbolBriefData
from traderadar.ai.service import AIService
from traderadar.core.config import Settings
from traderadar.core.logging import get_logger
from traderadar.core.models import AnalysisRecord, Candle, TicketRecord
from traderadar.core.time import utc_now

logger = get_logger("traderadar.ai.brief")


async def compile_market_brief_data(
    session: AsyncSession,
    settings: Settings,
    kind: str = "morning",
) -> MarketBriefPayload:
    """Compile market technical snapshot for all watchlist symbols."""
    symbols = [w.symbol for w in settings.app.watchlist]
    if not symbols:
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XAUUSDT"]

    symbol_data_map: dict[str, SymbolBriefData] = {}
    now = utc_now()
    cutoff_24h = now - timedelta(hours=24)

    for sym in symbols:
        # 1. Fetch latest analysis M15
        stmt_analysis = (
            select(AnalysisRecord)
            .where(AnalysisRecord.symbol == sym, AnalysisRecord.tf == "M15")
            .order_by(desc(AnalysisRecord.bar_time))
            .limit(1)
        )
        res_a = await session.execute(stmt_analysis)
        latest_analysis = res_a.scalar_one_or_none()

        score_m15 = latest_analysis.score if latest_analysis else 0.0
        verdict_m15 = latest_analysis.verdict if latest_analysis else "NEUTRAL"
        htf = latest_analysis.htf if latest_analysis else {}
        bias_h4 = htf.get("h4", "NEUTRAL")
        bias_d1 = htf.get("d1", "NEUTRAL")

        # 2. Fetch candles in last 24h
        stmt_candles = (
            select(Candle)
            .where(Candle.symbol == sym, Candle.open_time >= cutoff_24h)
            .order_by(desc(Candle.open_time))
            .limit(100)
        )
        res_c = await session.execute(stmt_candles)
        candles = res_c.scalars().all()

        if candles:
            last_price = float(candles[0].close)
            daily_high = max(float(c.high) for c in candles)
            daily_low = min(float(c.low) for c in candles)
            sum_vp = sum(float((c.high + c.low + c.close) / 3.0) * float(c.volume) for c in candles)
            sum_v = sum(float(c.volume) for c in candles)
            vwap_yesterday = round(sum_vp / sum_v, 2) if sum_v > 0 else None
        else:
            last_price = 2650.0 if sym == "XAUUSDT" else 65000.0
            daily_high = last_price * 1.01
            daily_low = last_price * 0.99
            vwap_yesterday = last_price

        # 3. Check for active ticket
        stmt_ticket = (
            select(TicketRecord)
            .where(TicketRecord.symbol == sym, TicketRecord.status == "new")
            .order_by(desc(TicketRecord.created_at))
            .limit(1)
        )
        res_t = await session.execute(stmt_ticket)
        active_t = res_t.scalar_one_or_none()
        ticket_dict: dict[str, Any] | None = None
        if active_t:
            ticket_dict = {
                "id": active_t.id,
                "side": active_t.side,
                "entry": active_t.entry,
                "sl": active_t.sl,
                "tp1": active_t.tp1,
                "score": active_t.score,
            }

        symbol_data_map[sym] = SymbolBriefData(
            symbol=sym,
            bias_h4=bias_h4,
            bias_d1=bias_d1,
            score_m15=score_m15,
            verdict_m15=verdict_m15,
            last_price=last_price,
            vwap_yesterday=vwap_yesterday,
            daily_high=daily_high,
            daily_low=daily_low,
            active_ticket=ticket_dict,
        )

    # News events placeholder (to be enriched by NewsService in Phase 9)
    high_impact_news = [
        {"title": "US Core CPI m/m", "currency": "USD", "impact": "High", "time": "19:30 WIB"},
        {"title": "Unemployment Claims", "currency": "USD", "impact": "High", "time": "19:30 WIB"},
    ]

    return MarketBriefPayload(
        kind=kind,
        generated_at=now.strftime("%Y-%m-%d %H:%M WIB"),
        high_impact_news_today=high_impact_news,
        symbols=symbol_data_map,
    )


async def generate_market_brief(
    session: AsyncSession,
    ai_service: AIService,
    settings: Settings,
    kind: str = "morning",
) -> tuple[Any, Any]:
    """Compile data and generate Market Brief narrative."""
    payload = await compile_market_brief_data(session, settings, kind=kind)
    narrative, brief_rec = await ai_service.generate_brief(payload, session=session)
    return narrative, brief_rec
