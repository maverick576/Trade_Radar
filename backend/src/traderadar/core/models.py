"""SQLAlchemy models for TradeRadar core tables."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from traderadar.core.time import utc_now


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass


class User(Base):
    """User account model for admin and authentication."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="user")


class RefreshToken(Base):
    """Refresh tokens issued for user sessions."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(
        Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")


class AuditLog(Base):
    """Security and action audit logs."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(
        Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    detail: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    user: Mapped["User | None"] = relationship("User", back_populates="audit_logs")


class AppSetting(Base):
    """Dynamic application settings stored in database."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class TelegramChat(Base):
    """Authorized telegram chats."""

    __tablename__ = "telegram_chats"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class Candle(Base):
    """Candlestick market data (hypertable partitioned by open_time)."""

    __tablename__ = "candles"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    tf: Mapped[str] = mapped_column(String(8), primary_key=True)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    taker_buy_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)


class DerivativesSnapshot(Base):
    """Snapshot of derivatives metrics (funding, mark, OI, LS ratio)."""

    __tablename__ = "derivatives_snapshots"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    funding: Mapped[float | None] = mapped_column(Float, nullable=True)
    mark: Mapped[float | None] = mapped_column(Float, nullable=True)
    open_interest: Mapped[float | None] = mapped_column(Float, nullable=True)
    ls_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)


class SentimentSnapshot(Base):
    """Snapshot of sentiment indicators (Fear & Greed index)."""

    __tablename__ = "sentiment_snapshots"

    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AnalysisRecord(Base):
    """Historical technical confluence analysis results."""

    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(
        Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    tf: Mapped[str] = mapped_column(String(8), nullable=False)
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    counts: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    indicators: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    category_votes: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    htf: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    macro: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    strategy_b: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    weights_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    signals: Mapped[list["SignalRecord"]] = relationship(
        "SignalRecord", back_populates="analysis", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("symbol", "tf", "bar_time", name="uq_analyses_symbol_tf_bar_time"),
    )


class SignalRecord(Base):
    """Trading signals produced by Strategy A or Strategy B (including blocked signals)."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(
        Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True
    )
    analysis_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    strategy: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    tf: Mapped[str] = mapped_column(String(8), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    blocked_by: Mapped[list[str] | None] = mapped_column(
        JSON().with_variant(ARRAY(String), "postgresql"), nullable=True
    )
    confirmed_by_b: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    analysis: Mapped["AnalysisRecord | None"] = relationship(
        "AnalysisRecord", back_populates="signals"
    )
    ticket: Mapped["TicketRecord | None"] = relationship(
        "TicketRecord", back_populates="signal", uselist=False
    )
    paper_trades: Mapped[list["PaperTradeRecord"]] = relationship(
        "PaperTradeRecord", back_populates="signal"
    )


class TicketRecord(Base):
    """Trade tickets ready for execution (BLUEPRINT.md §5.3)."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(
        Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True
    )
    signal_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("signals.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="Konfluensi-10")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    entry: Mapped[float] = mapped_column(Float, nullable=False)
    entry_low: Mapped[float] = mapped_column(Float, nullable=False)
    entry_high: Mapped[float] = mapped_column(Float, nullable=False)
    sl: Mapped[float] = mapped_column(Float, nullable=False)
    tp1: Mapped[float] = mapped_column(Float, nullable=False)
    tp2: Mapped[float] = mapped_column(Float, nullable=False)
    atr: Mapped[float] = mapped_column(Float, nullable=False)
    sl_points: Mapped[float] = mapped_column(Float, nullable=False)
    sl_atr_mult: Mapped[float] = mapped_column(Float, nullable=False)
    tp1_points: Mapped[float] = mapped_column(Float, nullable=False)
    tp2_points: Mapped[float] = mapped_column(Float, nullable=False)
    invalidation: Mapped[str] = mapped_column(String(255), nullable=False)
    reasons: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )
    risks: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )
    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False, default="new"
    )  # new | executed | skipped | expired | closed
    broker_offset: Mapped[float | None] = mapped_column(Float, nullable=True)
    broker_profile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    suggested_lot: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_risk_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_risk_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_lot_warning: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    warning_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    signal: Mapped["SignalRecord | None"] = relationship(
        "SignalRecord", back_populates="ticket"
    )
    executions: Mapped[list["RealExecutionRecord"]] = relationship(
        "RealExecutionRecord", back_populates="ticket", cascade="all, delete-orphan"
    )
    paper_trades: Mapped[list["PaperTradeRecord"]] = relationship(
        "PaperTradeRecord", back_populates="ticket"
    )


class RealExecutionRecord(Base):
    """Manual real execution journal entry (BLUEPRINT.md §5.3)."""

    __tablename__ = "real_executions"

    id: Mapped[int] = mapped_column(
        Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True
    )
    ticket_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    broker_profile: Mapped[str] = mapped_column(String(64), nullable=False)
    fill_price: Mapped[float] = mapped_column(Float, nullable=False)
    lot: Mapped[float] = mapped_column(Float, nullable=False)
    fill_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pnl_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    slippage_points: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ui"
    )  # ui | telegram
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    ticket: Mapped["TicketRecord"] = relationship(
        "TicketRecord", back_populates="executions"
    )


class PaperTradeRecord(Base):
    """Simulated paper trading position and history (BLUEPRINT.md §5.5)."""

    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(
        Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True
    )
    ticket_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    signal_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("signals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    strategy: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    entry_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    size: Mapped[float] = mapped_column(Float, nullable=False)
    sl: Mapped[float] = mapped_column(Float, nullable=False)
    tp1: Mapped[float] = mapped_column(Float, nullable=False)
    tp2: Mapped[float] = mapped_column(Float, nullable=False)
    tp1_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bars_held: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False, default="OPEN"
    )  # OPEN | CLOSED
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pnl_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    fees_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    mfe_r: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    mae_r: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_virtual: Mapped[bool] = mapped_column(
        Boolean, index=True, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    ticket: Mapped["TicketRecord | None"] = relationship(
        "TicketRecord", back_populates="paper_trades"
    )
    signal: Mapped["SignalRecord | None"] = relationship(
        "SignalRecord", back_populates="paper_trades"
    )


class BrokerCalibrationRecord(Base):
    """Broker price calibration offset record (BLUEPRINT.md §5.3)."""

    __tablename__ = "broker_calibrations"

    id: Mapped[int] = mapped_column(
        Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    broker_profile: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    broker_price: Mapped[float] = mapped_column(Float, nullable=False)
    source_price: Mapped[float] = mapped_column(Float, nullable=False)
    offset: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
