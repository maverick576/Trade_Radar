"""Database service and repository for TradeRadar Journal statistics and reports."""

import csv
import io
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from traderadar.core.models import (
    AnalysisRecord,
    PaperTradeRecord,
    RealExecutionRecord,
    SignalRecord,
    TicketRecord,
)
from traderadar.core.time import format_wib, utc_now
from traderadar.stats.metrics import (
    build_equity_curve,
    calculate_breakdowns,
    calculate_heatmap,
    calculate_indicator_accuracy,
    calculate_kpis,
    calculate_macro_filter_impact,
    calculate_r_distribution,
    calculate_slippage_stats,
    get_trading_session_name,
)
from traderadar.stats.models import (
    JournalResponse,
    TradeAnalysisSnapshotResponse,
    TradeRecordItem,
)


def _resolve_date_range(
    range_str: str,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    """Parse range presets (7d, 30d, 90d, all) or custom datetimes."""
    now = utc_now()
    r = range_str.lower().strip()
    if r == "7d":
        return now - timedelta(days=7), now
    elif r == "30d":
        return now - timedelta(days=30), now
    elif r == "90d":
        return now - timedelta(days=90), now
    elif r == "custom" and from_dt:
        return from_dt, (to_dt or now)
    return from_dt, to_dt


async def _fetch_paper_trades(
    session: AsyncSession,
    from_dt: datetime | None,
    to_dt: datetime | None,
    symbol: str | None,
    strategy: str | None,
) -> list[PaperTradeRecord]:
    """Query closed paper trades (non-virtual)."""
    stmt = (
        select(PaperTradeRecord)
        .options(
            selectinload(PaperTradeRecord.signal).selectinload(SignalRecord.analysis),
            selectinload(PaperTradeRecord.ticket),
        )
        .where(
            PaperTradeRecord.status == "CLOSED",
            PaperTradeRecord.is_virtual.is_(False),
        )
    )

    if from_dt:
        stmt = stmt.where(PaperTradeRecord.entry_time >= from_dt)
    if to_dt:
        stmt = stmt.where(PaperTradeRecord.entry_time <= to_dt)
    if symbol:
        stmt = stmt.where(PaperTradeRecord.symbol == symbol)
    if strategy:
        stmt = stmt.where(PaperTradeRecord.strategy == strategy)

    stmt = stmt.order_by(PaperTradeRecord.entry_time.asc())
    res = await session.scalars(stmt)
    return list(res.all())


async def _fetch_real_executions(
    session: AsyncSession,
    from_dt: datetime | None,
    to_dt: datetime | None,
    symbol: str | None,
    strategy: str | None,
) -> tuple[list[RealExecutionRecord], dict[int, TicketRecord]]:
    """Query closed real executions with linked tickets."""
    stmt = (
        select(RealExecutionRecord)
        .options(
            selectinload(RealExecutionRecord.ticket)
            .selectinload(TicketRecord.signal)
            .selectinload(SignalRecord.analysis)
        )
        .where(RealExecutionRecord.exit_price.is_not(None))
    )

    if from_dt:
        stmt = stmt.where(RealExecutionRecord.fill_time >= from_dt)
    if to_dt:
        stmt = stmt.where(RealExecutionRecord.fill_time <= to_dt)

    stmt = stmt.order_by(RealExecutionRecord.fill_time.asc())
    res = await session.scalars(stmt)
    records = list(res.all())

    # Filter by symbol and strategy through ticket relation
    filtered: list[RealExecutionRecord] = []
    ticket_map: dict[int, TicketRecord] = {}

    for r in records:
        ticket = r.ticket
        if ticket:
            ticket_map[r.ticket_id] = ticket
            if symbol and ticket.symbol != symbol:
                continue
            if strategy and ticket.strategy != strategy:
                continue
            filtered.append(r)

    return filtered, ticket_map


def _normalize_paper_trade(p: PaperTradeRecord) -> TradeRecordItem:
    """Map PaperTradeRecord to standardized TradeRecordItem."""
    verdict = "NEUTRAL"
    analysis_id: int | None = None
    if p.signal:
        verdict = p.signal.verdict
        if p.signal.analysis:
            analysis_id = p.signal.analysis.id

    return TradeRecordItem(
        id=p.id,
        ticket_id=p.ticket_id,
        signal_id=p.signal_id,
        analysis_id=analysis_id,
        book="paper",
        symbol=p.symbol,
        strategy=p.strategy,
        side=p.side,
        entry_time=p.entry_time,
        entry_time_wib=format_wib(p.entry_time),
        entry_price=p.entry_price,
        exit_time=p.exit_time,
        exit_time_wib=format_wib(p.exit_time) if p.exit_time else None,
        exit_price=p.exit_price,
        exit_reason=p.exit_reason,
        bars_held=p.bars_held,
        pnl_usd=round(p.pnl_usd or 0.0, 2),
        pnl_r=round(p.pnl_r or 0.0, 4),
        fees_usd=round(p.fees_usd or 0.0, 2),
        slippage_points=0.0,
        verdict=verdict,
        session=get_trading_session_name(p.entry_time),
        broker_profile="Paper Exchange",
        is_virtual=p.is_virtual,
        notes=None,
    )


def _normalize_real_execution(r: RealExecutionRecord, ticket: TicketRecord) -> TradeRecordItem:
    """Map RealExecutionRecord to standardized TradeRecordItem."""
    verdict = "NEUTRAL"
    analysis_id: int | None = None
    if ticket.signal:
        verdict = ticket.signal.verdict
        if ticket.signal.analysis:
            analysis_id = ticket.signal.analysis.id

    return TradeRecordItem(
        id=r.id,
        ticket_id=r.ticket_id,
        signal_id=ticket.signal_id,
        analysis_id=analysis_id,
        book="real",
        symbol=ticket.symbol,
        strategy=ticket.strategy,
        side=ticket.side,
        entry_time=r.fill_time,
        entry_time_wib=format_wib(r.fill_time),
        entry_price=r.fill_price,
        exit_time=r.exit_time,
        exit_time_wib=format_wib(r.exit_time) if r.exit_time else None,
        exit_price=r.exit_price,
        exit_reason="Manual Execution Exit",
        bars_held=0,
        pnl_usd=round(r.pnl_usd or 0.0, 2),
        pnl_r=round(r.pnl_r or 0.0, 4),
        fees_usd=0.0,
        slippage_points=round(r.slippage_points, 4),
        verdict=verdict,
        session=get_trading_session_name(r.fill_time),
        broker_profile=r.broker_profile,
        is_virtual=False,
        notes=r.notes,
    )


async def get_journal_stats(
    session: AsyncSession,
    book: str = "paper",
    range_str: str = "all",
    symbol: str | None = None,
    strategy: str | None = None,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
) -> JournalResponse:
    """Retrieve complete journal metrics, equity curve, heatmap, breakdowns, and trade history."""
    clean_book = book.lower().strip()
    if clean_book not in ("paper", "real", "compare"):
        clean_book = "paper"

    f_dt, t_dt = _resolve_date_range(range_str, from_dt, to_dt)

    # 1. Fetch Paper and Real records
    paper_records = await _fetch_paper_trades(session, f_dt, t_dt, symbol, strategy)
    real_records, ticket_map = await _fetch_real_executions(session, f_dt, t_dt, symbol, strategy)

    paper_trades = [_normalize_paper_trade(p) for p in paper_records]
    real_trades = [_normalize_real_execution(r, ticket_map[r.ticket_id]) for r in real_records]

    paper_kpis = calculate_kpis(paper_trades)
    real_kpis = calculate_kpis(real_trades)

    # Select active book trades
    if clean_book == "real":
        active_trades = real_trades
        active_kpis = real_kpis
    elif clean_book == "compare":
        # In compare mode, active trades combine both for comprehensive review
        active_trades = sorted(
            paper_trades + real_trades, key=lambda t: t.exit_time or t.entry_time
        )
        active_kpis = paper_kpis  # primary kpi shows paper, with both compare kpis attached
    else:
        active_trades = paper_trades
        active_kpis = paper_kpis

    # 2. Charts & visual analytics
    equity_curve = build_equity_curve(active_trades)
    r_dist = calculate_r_distribution(active_trades)
    heatmap = calculate_heatmap(active_trades)
    breakdowns = calculate_breakdowns(active_trades)

    # 3. Akurasi per Indikator
    # Gather trades with analysis indicators according to chosen book
    trades_with_indicators: list[tuple[TradeRecordItem, list[dict[str, Any]]]] = []
    if clean_book in ("paper", "compare"):
        for p in paper_records:
            if p.signal and p.signal.analysis:
                trades_with_indicators.append(
                    (_normalize_paper_trade(p), p.signal.analysis.indicators or [])
                )
    if clean_book in ("real", "compare"):
        for r in real_records:
            t = ticket_map.get(r.ticket_id)
            if t and t.signal and t.signal.analysis:
                trades_with_indicators.append(
                    (_normalize_real_execution(r, t), t.signal.analysis.indicators or [])
                )

    indicator_accuracy = calculate_indicator_accuracy(trades_with_indicators)

    # 4. Nilai Macro Filter (evaluating blocked signals & virtual outcomes)
    blocked_stmt = (
        select(SignalRecord)
        .options(selectinload(SignalRecord.paper_trades))
        .where(SignalRecord.blocked_by.is_not(None))
    )
    if f_dt:
        blocked_stmt = blocked_stmt.where(SignalRecord.created_at >= f_dt)
    if t_dt:
        blocked_stmt = blocked_stmt.where(SignalRecord.created_at <= t_dt)

    blocked_signals = list((await session.scalars(blocked_stmt)).all())
    blocked_items: list[dict[str, Any]] = []

    for sig in blocked_signals:
        reasons = sig.blocked_by or []
        # Find if any virtual paper trade ran for this signal
        virtual_pnl_r: float | None = None
        for pt in sig.paper_trades:
            if pt.is_virtual and pt.status == "CLOSED":
                virtual_pnl_r = pt.pnl_r
                break
        blocked_items.append({"blocked_by": reasons, "virtual_pnl_r": virtual_pnl_r})

    macro_filter_impact = calculate_macro_filter_impact(blocked_items)

    # 5. Slippage Nyata
    # Query all real executions within range to calculate slippage stats
    all_tickets_stmt = select(TicketRecord)
    all_tickets = list((await session.scalars(all_tickets_stmt)).all())
    all_tickets_dict = {t.id: t for t in all_tickets}
    slippage_metrics = calculate_slippage_stats(real_records, all_tickets_dict)

    # Order trades list newest first for journal view
    ordered_trades = sorted(active_trades, key=lambda t: t.entry_time, reverse=True)

    return JournalResponse(
        book=clean_book,
        filter_range=range_str,
        filter_symbol=symbol,
        filter_strategy=strategy,
        kpis=active_kpis,
        compare_paper_kpis=paper_kpis if clean_book == "compare" else None,
        compare_real_kpis=real_kpis if clean_book == "compare" else None,
        equity_curve=equity_curve,
        r_distribution=r_dist,
        heatmap=heatmap,
        breakdowns=breakdowns,
        indicator_accuracy=indicator_accuracy,
        macro_filter_impact=macro_filter_impact,
        slippage_metrics=slippage_metrics,
        trades=ordered_trades,
    )


async def export_journal_csv(
    session: AsyncSession,
    book: str = "paper",
    range_str: str = "all",
    symbol: str | None = None,
    strategy: str | None = None,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
) -> str:
    """Generate RFC 4180 compliant CSV export for journal trades."""
    stats = await get_journal_stats(
        session=session,
        book=book,
        range_str=range_str,
        symbol=symbol,
        strategy=strategy,
        from_dt=from_dt,
        to_dt=to_dt,
    )

    output = io.StringIO()
    # Add UTF-8 BOM so Excel opens accented/Indonesian characters perfectly
    output.write("\ufeff")

    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    headers = [
        "ID",
        "Buku",
        "Simbol",
        "Strategi",
        "Arah",
        "Waktu Masuk (WIB)",
        "Harga Masuk",
        "Waktu Keluar (WIB)",
        "Harga Keluar",
        "Alasan Keluar",
        "Durasi (Bar)",
        "PnL (USD)",
        "PnL (R)",
        "Biaya (USD)",
        "Slippage (Poin)",
        "Sesi",
        "Verdict",
        "Broker",
        "Catatan",
    ]
    writer.writerow(headers)

    for t in stats.trades:
        writer.writerow(
            [
                t.id,
                t.book.upper(),
                t.symbol,
                t.strategy,
                t.side,
                t.entry_time_wib,
                f"{t.entry_price:.4f}",
                t.exit_time_wib or "-",
                f"{t.exit_price:.4f}" if t.exit_price is not None else "-",
                t.exit_reason or "-",
                t.bars_held,
                f"{t.pnl_usd:.2f}",
                f"{t.pnl_r:.4f}",
                f"{t.fees_usd:.2f}",
                f"{t.slippage_points:.4f}",
                t.session,
                t.verdict,
                t.broker_profile or "-",
                (t.notes or "").replace("\n", " "),
            ]
        )

    return output.getvalue()


async def get_trade_analysis_snapshot(
    session: AsyncSession,
    trade_id: int,
    book: str = "paper",
) -> TradeAnalysisSnapshotResponse | None:
    """Retrieve technical confluence snapshot and indicator votes at the moment trade was opened."""
    analysis: AnalysisRecord | None = None
    symbol = "UNKNOWN"

    if book.lower() == "real":
        execution = await session.get(RealExecutionRecord, trade_id)
        if execution and execution.ticket_id:
            ticket = await session.get(TicketRecord, execution.ticket_id)
            if ticket and ticket.signal_id:
                signal = await session.get(SignalRecord, ticket.signal_id)
                if signal and signal.analysis_id:
                    analysis = await session.get(AnalysisRecord, signal.analysis_id)
                    symbol = ticket.symbol
    else:
        paper = await session.get(PaperTradeRecord, trade_id)
        if paper and paper.signal_id:
            signal = await session.get(SignalRecord, paper.signal_id)
            if signal and signal.analysis_id:
                analysis = await session.get(AnalysisRecord, signal.analysis_id)
                symbol = paper.symbol

    if not analysis:
        return None

    return TradeAnalysisSnapshotResponse(
        trade_id=trade_id,
        symbol=symbol,
        tf=analysis.tf,
        bar_time=format_wib(analysis.bar_time),
        score=analysis.score,
        verdict=analysis.verdict,
        indicators=analysis.indicators or [],
        counts=analysis.counts or {},
        category_votes=analysis.category_votes or {},
        macro=analysis.macro or {},
        htf=analysis.htf or {},
        strategy_b=analysis.strategy_b or {},
        weights_version=analysis.weights_version,
    )
