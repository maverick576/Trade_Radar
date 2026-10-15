"""Pydantic schemas for Trade Tickets, Broker Calibrations, and Real Executions."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TicketResponse(BaseModel):
    """Schema for returning Trade Tickets."""

    id: int
    signal_id: int | None = None
    symbol: str
    side: Literal["LONG", "SHORT"]
    strategy: str
    score: float
    source: str
    entry: float
    entry_low: float
    entry_high: float
    sl: float
    tp1: float
    tp2: float
    atr: float
    sl_points: float
    sl_atr_mult: float
    tp1_points: float
    tp2_points: float
    invalidation: str
    reasons: list[str]
    risks: list[str]
    valid_until: datetime
    status: str
    broker_offset: float | None = None
    broker_profile: str | None = None
    suggested_lot: float | None = None
    actual_risk_usd: float | None = None
    actual_risk_pct: float | None = None
    min_lot_warning: bool = False
    warning_message: str | None = None
    text_full: str | None = None
    text_compact: str | None = None
    created_at: datetime
    updated_at: datetime


class ExecuteTicketRequest(BaseModel):
    """Request payload to record real trade execution."""

    broker_profile: str = Field(..., description="Broker profile name, e.g. 'Exness Standard'")
    fill_price: float = Field(..., gt=0, description="Actual filled price at the broker")
    lot: float = Field(..., gt=0, description="Actual executed lot size")
    fill_time: datetime | None = Field(default=None, description="Execution time (UTC)")
    source: str = Field(default="ui", description="Origin of execution: 'ui' or 'telegram'")
    notes: str | None = Field(default=None, description="Optional notes or trade tags")


class CloseTicketRequest(BaseModel):
    """Request payload to record real trade close."""

    exit_price: float = Field(..., gt=0, description="Actual exit fill price")
    exit_time: datetime | None = Field(default=None, description="Exit time (UTC)")
    notes: str | None = Field(default=None, description="Optional notes")


class RealExecutionResponse(BaseModel):
    """Schema for returned real execution record."""

    id: int
    ticket_id: int
    broker_profile: str
    fill_price: float
    lot: float
    fill_time: datetime
    exit_price: float | None = None
    exit_time: datetime | None = None
    pnl_usd: float | None = None
    pnl_r: float | None = None
    slippage_points: float
    source: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class CalibrationRequest(BaseModel):
    """Request payload to set broker price offset."""

    symbol: str = Field(..., description="Symbol, e.g. 'XAUUSD'")
    broker_profile: str = Field(..., description="Broker profile name")
    broker_price: float = Field(..., gt=0, description="Current price displayed at broker terminal")


class CalibrationResponse(BaseModel):
    """Schema for broker price calibration offset."""

    id: int
    symbol: str
    broker_profile: str
    broker_price: float
    source_price: float
    offset: float
    created_at: datetime
    expires_at: datetime
    is_active: bool = True
