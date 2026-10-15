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
