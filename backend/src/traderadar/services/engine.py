"""Confluence analysis engine service consuming candles.closed events."""

import asyncio
import json
from typing import Any, Literal

import pandas as pd
from redis.asyncio import Redis

from traderadar.core.config import get_app_settings
from traderadar.core.db import get_db_session
from traderadar.core.events import (
    CHANNEL_UI_EVENTS,
    STREAM_CANDLES_CLOSED,
    STREAM_SIGNALS,
    CandleClosedEvent,
    SignalEvent,
    UIEvent,
)
from traderadar.core.logging import get_logger
from traderadar.core.redis import get_redis
from traderadar.core.time import utc_now
from traderadar.engine.indicators.base import MarketContext
from traderadar.engine.paper import (
    CandleBar,
    PaperTradeState,
    close_paper_trade_opposite,
    create_paper_position,
    update_paper_position_with_bar,
)
from traderadar.engine.risk import calculate_trade_levels
from traderadar.engine.strategies.konfluensi10 import ConfluencePipeline
from traderadar.engine.ticket import (
    TradeTicket,
    check_ticket_expiration,
    create_trade_ticket,
)
from traderadar.services.analysis_store import get_latest_analysis, save_analysis_and_signals
from traderadar.services.candle_store import get_candles
from traderadar.services.paper_store import (
    get_open_paper_trades,
    get_paper_account_metrics,
    save_paper_trade,
    update_paper_trade_record,
)
from traderadar.services.runner import run_service
from traderadar.services.ticket_store import (
    get_latest_broker_calibration,
    get_tickets,
    save_ticket,
    update_ticket_status,
)

logger = get_logger("traderadar.engine")


async def build_market_context(redis_client: Redis, symbol: str) -> MarketContext:
    """Fetch live market context (derivatives snapshot, sentiment) from Redis."""
    is_gold = "XAU" in symbol.upper() or "GOLD" in symbol.upper()
    ctx = MarketContext(is_gold=is_gold)

    try:
        deriv_raw = await redis_client.get(f"derivatives:{symbol.upper()}")
        if deriv_raw:
            deriv = json.loads(deriv_raw)
            ctx.funding_rate = deriv.get("funding")
            ctx.open_interest_current = deriv.get("open_interest")
            ctx.open_interest_4h_ago = deriv.get("open_interest_4h_ago")
            ctx.long_short_ratio = deriv.get("ls_ratio")

        fng_val = await redis_client.get("sentiment:fng")
        if fng_val:
            ctx.fear_and_greed = int(fng_val)
    except Exception as e:
        logger.warning("market_context_fetch_failed", symbol=symbol, error=str(e))

    return ctx


async def process_closed_candle(
    redis_client: Redis,
    pipeline: ConfluencePipeline,
    event: CandleClosedEvent,
) -> None:
    """Run confluence analysis and emit signals for closed M15 candle."""
    symbol = event.symbol.upper()
    tf = event.tf.upper()

    # We evaluate full 10-indicator confluence on entry timeframe M15
    if tf != "M15":
        return

    logger.info("processing_m15_confluence", symbol=symbol, bar_time=event.bar_time.isoformat())

    async with get_db_session() as session:
        # 1. Fetch candles for M15, H1, H4, D1
        m15_rows = await get_candles(session, symbol, "M15", limit=300)
        h1_rows = await get_candles(session, symbol, "H1", limit=100)
        h4_rows = await get_candles(session, symbol, "H4", limit=100)
        d1_rows = await get_candles(session, symbol, "D1", limit=50)

        if len(m15_rows) < 20:
            logger.warning("insufficient_m15_candles", symbol=symbol, count=len(m15_rows))
            return

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
        df_h1 = rows_to_df(h1_rows) if h1_rows else None
        df_h4 = rows_to_df(h4_rows) if h4_rows else None
        df_d1 = rows_to_df(d1_rows) if d1_rows else None

        # 2. Get previous analysis for cooldown detection
        prev_analysis = await get_latest_analysis(session, symbol, "M15")
        prev_side = None
        prev_bars_ago = None
        if prev_analysis is not None:
            if "LONG" in prev_analysis.verdict:
                prev_side = "LONG"
            elif "SHORT" in prev_analysis.verdict:
                prev_side = "SHORT"
            # Calculate bars ago approximately
            diff_sec = (event.bar_time - prev_analysis.bar_time).total_seconds()
            prev_bars_ago = int(diff_sec // 900)

        # 3. Build Market Context
        context = await build_market_context(redis_client, symbol)

        # 4. Execute Analysis Pipeline
        analysis, signals = pipeline.run_analysis(
            symbol=symbol,
            tf=tf,
            source=event.source,
            df_m15=df_m15,
            df_h1=df_h1,
            df_h4=df_h4,
            df_d1=df_d1,
            context=context,
            previous_signal_side=prev_side,
            previous_signal_bars_ago=prev_bars_ago,
        )

        # 5. Persist Analysis and Signals to Database
        record, saved_signals = await save_analysis_and_signals(session, analysis, signals)
        logger.info(
            "analysis_persisted",
            symbol=symbol,
            score=analysis.score,
            verdict=analysis.verdict,
            signals_count=len(saved_signals),
        )

        settings = get_app_settings()
        candle_bar = CandleBar(
            open_time=event.bar_time,
            open=event.open,
            high=event.high,
            low=event.low,
            close=event.close,
        )

        # 6. Update existing open paper trades on this new bar
        open_trades = await get_open_paper_trades(session, symbol=symbol)
        for p_rec in open_trades:
            p_side: Literal["LONG", "SHORT"] = "LONG" if p_rec.side == "LONG" else "SHORT"
            p_status: Literal["OPEN", "CLOSED"] = "OPEN" if p_rec.status == "OPEN" else "CLOSED"
            r_dist = max(abs(p_rec.entry_price - p_rec.sl), 1e-4)

            p_state = PaperTradeState(
                id=p_rec.id,
                ticket_id=p_rec.ticket_id,
                signal_id=p_rec.signal_id,
                strategy=p_rec.strategy,
                symbol=p_rec.symbol,
                side=p_side,
                entry_time=p_rec.entry_time,
                entry_price=p_rec.entry_price,
                size=p_rec.size,
                initial_sl=p_rec.sl,
                current_sl=p_rec.sl,
                tp1=p_rec.tp1,
                tp2=p_rec.tp2,
                r_distance=r_dist,
                tp1_hit=p_rec.tp1_hit,
                bars_held=p_rec.bars_held,
                status=p_status,
                fees_usd=p_rec.fees_usd,
                mfe_r=p_rec.mfe_r,
                mae_r=p_rec.mae_r,
                is_virtual=p_rec.is_virtual,
                created_at=p_rec.created_at,
            )
            # Check opposite STRONG signal
            is_opp = (
                (p_state.side == "LONG" and analysis.verdict == "STRONG_SHORT")
                or (p_state.side == "SHORT" and analysis.verdict == "STRONG_LONG")
            )
            if is_opp:
                updated_trade = close_paper_trade_opposite(
                    p_state, exit_price=event.close, exit_time=event.bar_time
                )
            else:
                updated_trade = update_paper_position_with_bar(
                    p_state, candle_bar, time_stop_bars=settings.paper.time_stop_bars
                )

            await update_paper_trade_record(session, updated_trade)
            if updated_trade.status != p_state.status or updated_trade.tp1_hit != p_state.tp1_hit:
                trade_ui = UIEvent(
                    type="paper_trade",
                    data=updated_trade.model_dump(mode="json"),
                    ts=utc_now(),
                )
                await redis_client.publish(CHANNEL_UI_EVENTS, trade_ui.model_dump_json())

        # 7. Check expiration on existing active tickets
        active_tickets = await get_tickets(session, symbol=symbol, status="new")
        for t_rec in active_tickets:
            t_side: Literal["LONG", "SHORT"] = "LONG" if t_rec.side == "LONG" else "SHORT"
            t_status: Literal["new", "executed", "skipped", "expired", "closed"] = (
                t_rec.status  # type: ignore[assignment]
                if t_rec.status in ("new", "executed", "skipped", "expired", "closed")
                else "new"
            )
            t_eng = TradeTicket(
                id=t_rec.id,
                signal_id=t_rec.signal_id,
                symbol=t_rec.symbol,
                side=t_side,
                strategy=t_rec.strategy,
                score=t_rec.score,
                source=t_rec.source,
                entry=t_rec.entry,
                entry_low=t_rec.entry_low,
                entry_high=t_rec.entry_high,
                sl=t_rec.sl,
                tp1=t_rec.tp1,
                tp2=t_rec.tp2,
                atr=t_rec.atr,
                sl_points=t_rec.sl_points,
                sl_atr_mult=t_rec.sl_atr_mult,
                tp1_points=t_rec.tp1_points,
                tp2_points=t_rec.tp2_points,
                invalidation=t_rec.invalidation,
                reasons=t_rec.reasons or [],
                risks=t_rec.risks or [],
                valid_until=t_rec.valid_until,
                status=t_status,
                created_at=t_rec.created_at,
            )
            is_exp, exp_reason = check_ticket_expiration(
                ticket=t_eng,
                current_time=event.bar_time,
                current_price=event.close,
                chase_limit_atr=settings.ticket.chase_limit_atr,
            )
            if is_exp:
                await update_ticket_status(session, t_rec.id, "expired")
                ticket_exp_ui = UIEvent(
                    type="ticket",
                    data={"id": t_rec.id, "status": "expired", "reason": exp_reason},
                    ts=utc_now(),
                )
                await redis_client.publish(CHANNEL_UI_EVENTS, ticket_exp_ui.model_dump_json())

        # 8. Extract ATR and indicators metadata for tickets and paper trades
        atr_val = 1.0
        for ind in analysis.indicators:
            if ind.key == "supertrend":
                atr_val = ind.values.get("atr", atr_val)

        # 9. Handle tickets and paper trading for newly generated signals
        ticket_map: dict[int, int] = {}
        for sig in saved_signals:
            side_literal: Literal["LONG", "SHORT"] = "LONG" if sig.side == "LONG" else "SHORT"
            if sig.status == "ACTIVE" and sig.verdict in ("STRONG_LONG", "STRONG_SHORT"):
                profile = settings.brokers[0] if settings.brokers else None
                cal = await get_latest_broker_calibration(session, symbol)
                offset = cal.offset if cal else None

                bull_reasons = [
                    ind.reason
                    for ind in analysis.indicators
                    if ind.state == ("BULL" if side_literal == "LONG" else "BEAR")
                ][:3]
                bear_risks = [
                    ind.reason
                    for ind in analysis.indicators
                    if ind.state == ("BEAR" if side_literal == "LONG" else "BULL")
                ][:2]

                ticket_obj = create_trade_ticket(
                    symbol=symbol,
                    side=side_literal,
                    entry_price=event.close,
                    atr14=atr_val,
                    score=analysis.score,
                    strategy=sig.strategy,
                    source=event.source,
                    bar_time=event.bar_time,
                    signal_id=sig.id,
                    reasons=bull_reasons,
                    risks=bear_risks,
                    risk_settings=settings.risk,
                    ticket_settings=settings.ticket,
                    broker_profile=profile,
                    broker_offset=offset,
                )
                saved_ticket = await save_ticket(session, ticket_obj)
                ticket_map[sig.id] = saved_ticket.id

                # Open simulated paper trade if daily loss limit not hit and open count < max
                acc = await get_paper_account_metrics(
                    session,
                    settings.paper.initial_equity_usd,
                    settings.paper.daily_loss_limit_pct,
                )
                if (
                    not acc["daily_loss_limit_hit"]
                    and acc["open_positions_count"] < settings.paper.max_open_positions
                ):
                    paper_pos = create_paper_position(
                        symbol=symbol,
                        side=side_literal,
                        bar_open=event.close,
                        bar_time=event.bar_time,
                        sl=saved_ticket.sl,
                        tp1=saved_ticket.tp1,
                        tp2=saved_ticket.tp2,
                        equity=acc["equity"],
                        risk_pct=settings.paper.risk_pct,
                        strategy=sig.strategy,
                        ticket_id=saved_ticket.id,
                        signal_id=sig.id,
                        slippage_bps=settings.paper.slippage_bps,
                        is_virtual=False,
                    )
                    await save_paper_trade(session, paper_pos)

                    paper_ui = UIEvent(
                        type="paper_trade",
                        data=paper_pos.model_dump(mode="json"),
                        ts=utc_now(),
                    )
                    await redis_client.publish(CHANNEL_UI_EVENTS, paper_ui.model_dump_json())

                # UI event for new ticket
                ticket_ui = UIEvent(
                    type="ticket",
                    data=ticket_obj.model_dump(mode="json"),
                    ts=utc_now(),
                )
                await redis_client.publish(CHANNEL_UI_EVENTS, ticket_ui.model_dump_json())

            elif sig.status == "BLOCKED":
                # Virtual paper trade for simulated blocked signals
                virtual_levels = calculate_trade_levels(
                    symbol=symbol,
                    side=side_literal,
                    entry_price=event.close,
                    atr14=atr_val,
                    risk_settings=settings.risk,
                    ticket_settings=settings.ticket,
                )
                virtual_pos = create_paper_position(
                    symbol=symbol,
                    side=side_literal,
                    bar_open=event.close,
                    bar_time=event.bar_time,
                    sl=virtual_levels.sl,
                    tp1=virtual_levels.tp1,
                    tp2=virtual_levels.tp2,
                    equity=settings.paper.initial_equity_usd,
                    risk_pct=settings.paper.risk_pct,
                    strategy=sig.strategy,
                    signal_id=sig.id,
                    slippage_bps=settings.paper.slippage_bps,
                    is_virtual=True,
                )
                await save_paper_trade(session, virtual_pos)

    # 10. Cache latest analysis in Redis for immediate UI access
    analysis_dict = analysis.model_dump(mode="json")
    await redis_client.set(f"analysis:latest:{symbol}:{tf}", json.dumps(analysis_dict))

    # 11. Publish UI Event via PubSub
    ui_evt = UIEvent(
        type="analysis",
        data={
            "symbol": symbol,
            "tf": tf,
            "analysis": analysis_dict,
        },
        ts=utc_now(),
    )
    await redis_client.publish(CHANNEL_UI_EVENTS, ui_evt.model_dump_json())

    # 12. Emit to Redis Stream `signals` if strong signals generated
    for sig in saved_signals:
        sig_evt = SignalEvent(
            event_id=f"sig:{sig.id}",
            signal_id=sig.id,
            ticket_id=ticket_map.get(sig.id),
            strategy=sig.strategy,
            symbol=sig.symbol,
            tf=sig.tf,
            side="LONG" if sig.side == "LONG" else "SHORT",
            verdict=(
                sig.verdict
                if sig.verdict in ("STRONG_LONG", "LONG", "NEUTRAL", "SHORT", "STRONG_SHORT")
                else "NEUTRAL"
            ),
            bar_time=sig.bar_time,
            created_at=sig.created_at,
        )
        await redis_client.xadd(
            STREAM_SIGNALS,
            {"data": sig_evt.model_dump_json()},
            maxlen=5000,
        )

        sig_ui_evt = UIEvent(
            type="signal",
            data={
                "signal_id": sig.id,
                "ticket_id": ticket_map.get(sig.id),
                "symbol": sig.symbol,
                "strategy": sig.strategy,
                "side": sig.side,
                "verdict": sig.verdict,
                "status": sig.status,
                "blocked_by": sig.blocked_by,
                "bar_time": sig.bar_time.isoformat(),
            },
            ts=utc_now(),
        )
        await redis_client.publish(CHANNEL_UI_EVENTS, sig_ui_evt.model_dump_json())


async def engine_loop() -> None:
    """Engine background routine consuming candles.closed events."""
    redis_client = get_redis()
    pipeline = ConfluencePipeline()

    group_name = "engine"
    consumer_name = "engine_worker_1"

    # Ensure stream and consumer group exist
    try:
        await redis_client.xgroup_create(
            STREAM_CANDLES_CLOSED,
            group_name,
            id="0",
            mkstream=True,
        )
        logger.info("consumer_group_created", stream=STREAM_CANDLES_CLOSED, group=group_name)
    except Exception as e:
        if "BUSYGROUP" in str(e):
            pass
        else:
            logger.warning("xgroup_create_notice", error=str(e))

    logger.info("engine_service_ready", stream=STREAM_CANDLES_CLOSED)

    while True:
        try:
            # Read new events from consumer group
            entries = await redis_client.xreadgroup(
                groupname=group_name,
                consumername=consumer_name,
                streams={STREAM_CANDLES_CLOSED: ">"},
                count=10,
                block=2000,
            )

            if not entries:
                continue

            for stream_name, messages in entries:
                for msg_id, data in messages:
                    try:
                        raw_payload = data.get("data") or data.get(b"data")
                        if raw_payload:
                            if isinstance(raw_payload, bytes):
                                raw_payload = raw_payload.decode("utf-8")
                            parsed = json.loads(raw_payload)
                            event = CandleClosedEvent(**parsed)
                            await process_closed_candle(redis_client, pipeline, event)

                        # Acknowledge processed message
                        await redis_client.xack(stream_name, group_name, msg_id)
                    except Exception as exc:
                        logger.error("candle_event_process_failed", msg_id=msg_id, error=str(exc))
                        # Still ack to prevent poison pills
                        await redis_client.xack(stream_name, group_name, msg_id)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("engine_loop_error", error=str(e))
            await asyncio.sleep(2)


def main() -> None:
    """CLI entrypoint."""
    run_service("engine", task_callback=engine_loop)


if __name__ == "__main__":
    main()
