"""Pydantic schemas for AI and Market Brief API endpoints."""

from datetime import datetime

from pydantic import BaseModel

from traderadar.ai.schemas import AIComment, MarketBriefNarrative, MarketBriefPayload


class AICommentResponse(BaseModel):
    """Response containing structured AI commentary and metadata."""

    symbol: str
    tf: str
    comment: AIComment
    provider: str
    model: str
    valid: bool
    is_fallback: bool
    latency_ms: int
    tokens_in: int = 0
    tokens_out: int = 0
    created_at: datetime
    analysis_id: int | None = None


class AIQuotaResponse(BaseModel):
    """Current usage and quota limits for AI provider."""

    rpm_used: int
    rpm_limit: int
    rpm_remaining: int
    rpd_used: int
    rpd_limit: int
    rpd_remaining: int
    provider: str
    model: str


class MarketBriefResponse(BaseModel):
    """Market Brief response model for latest and ondemand briefs."""

    id: int | None = None
    kind: str = "morning"
    generated_at: str
    narrative: MarketBriefNarrative
    payload: MarketBriefPayload
    provider: str = "gemini"
    model: str = "gemini-3.8-flash"
    is_fallback: bool = False
    created_at: datetime
