"""Pydantic schemas for Paper Trading endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PaperTradeResponse(BaseModel):
    """Schema for returning paper trade positions."""

    id: int
    ticket_id: int | None = None
    signal_id: int | None = None
    strategy: str
    symbol: str
    side: Literal["LONG", "SHORT"]
    entry_time: datetime
    entry_price: float
    size: float
    sl: float
    tp1: float
    tp2: float
    tp1_hit: bool
    bars_held: int
    status: str
    exit_time: datetime | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    pnl_usd: float | None = None
    pnl_r: float | None = None
    fees_usd: float
    mfe_r: float
    mae_r: float
    is_virtual: bool
    created_at: datetime
    updated_at: datetime


class PaperAccountResponse(BaseModel):
    """Schema for paper trading account summary metrics."""

    initial_equity: float
    equity: float
    realized_pnl_usd: float
    daily_pnl_usd: float
    daily_loss_limit_hit: bool
    open_positions_count: int
    total_closed_trades: int
    winrate_pct: float
    expectancy_r: float


class ClosePaperTradeRequest(BaseModel):
    """Request payload to manually close an open paper trade."""

    exit_price: float = Field(..., gt=0, description="Exit price")
    exit_time: datetime | None = Field(default=None, description="Optional exit timestamp")
    exit_reason: str = Field(default="MANUAL", description="Reason for closing")
