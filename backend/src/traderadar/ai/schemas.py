"""Pydantic schemas for AI input payload and structured output."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class AIComment(BaseModel):
    """Structured AI technical commentary schema (SIGNAL_ENGINE.md §8)."""

    ringkasan: str = Field(
        description="Ringkasan analisis teknikal maksimal 120 kata tanpa janji profit"
    )
    bias: Literal["bullish", "bearish", "netral"] = Field(description="Arah bias teknikal")
    keyakinan: Literal["rendah", "sedang", "tinggi"] = Field(
        description="Derajat keyakinan terhadap setup"
    )
    setuju_dengan_engine: bool = Field(
        description="Apakah sepakat dengan arah sinyal deterministic engine"
    )
    alasan_utama: list[str] = Field(description="2-4 butir alasan teknikal utama pendukung bias")
    risiko: list[str] = Field(description="1-3 butir risiko utama atau indikator yang bertentangan")
    skenario_bullish: str = Field(description="Skenario pergerakan harga bila pembeli mendominasi")
    skenario_bearish: str = Field(description="Skenario pergerakan harga bila penjual mendominasi")
    level_penting: list[float] = Field(
        description="Daftar level harga penting (harus bersumber dari data input)"
    )
    invalidasi: str = Field(
        description="Kondisi atau level penembusan struktur yang membatalkan tesis"
    )
    saran_manajemen: str = Field(description="Saran pengelolaan risiko dan money management")


class AIInputPayload(BaseModel):
    """Complete structured technical input payload passed to AI providers."""

    symbol: str
    tf: str
    bar_time: str
    price: float
    verdict: str
    score: float
    counts: dict[str, int]
    indicators: list[dict[str, Any]]
    macro: dict[str, Any]
    plan: dict[str, Any] | None = None
    htf: dict[str, Any] = Field(default_factory=dict)
    news_24h: list[dict[str, Any]] = Field(default_factory=list)
    stats_30d_similar: dict[str, Any] = Field(default_factory=dict)
    strategy_b: dict[str, Any] = Field(default_factory=dict)


class SymbolBriefNarrative(BaseModel):
    """Narrative commentary for an individual symbol in the Market Brief."""

    symbol: str
    bias: Literal["bullish", "bearish", "netral"]
    ringkasan: str = Field(description="Narasi teknikal simbol maksimal 200 kata")
    level_kunci: list[float] = Field(
        description="Level harga krusial hari ini (VWAP kemarin, high/low, dll.)"
    )
    skenario: str = Field(description="Skenario aksi trading yang perlu diperhatikan")
    fokus_perhatian: str = Field(description="Fokus katalis atau konfluensi utama")


class MarketBriefNarrative(BaseModel):
    """Complete narrative structure of the morning/midday Market Brief."""

    ringkasan_umum: str = Field(description="Resume kondisi pasar makro dan volatilitas hari ini")
    market_sentiment: str = Field(
        description="Sentimen pasar keseluruhan (risk-on, risk-off, konsolidasi)"
    )
    symbols: dict[str, SymbolBriefNarrative] = Field(default_factory=dict)


class SymbolBriefData(BaseModel):
    """Technical snapshot data compiled for an individual symbol."""

    symbol: str
    bias_h4: str = "NEUTRAL"
    bias_d1: str = "NEUTRAL"
    score_m15: float = 0.0
    verdict_m15: str = "NEUTRAL"
    last_price: float
    vwap_yesterday: float | None = None
    daily_high: float
    daily_low: float
    swing_h4: float | None = None
    supertrend_h1: float | None = None
    active_ticket: dict[str, Any] | None = None
    stats_7d: dict[str, Any] | None = None


class MarketBriefPayload(BaseModel):
    """Complete input data aggregated for generating Market Brief."""

    kind: str = "morning"  # morning | midday | ondemand
    generated_at: str
    high_impact_news_today: list[dict[str, Any]] = Field(default_factory=list)
    symbols: dict[str, SymbolBriefData] = Field(default_factory=dict)


class AIResponse(BaseModel):
    """Wrapper response model from AI commentary evaluation."""

    comment: AIComment
    provider: str
    model: str
    valid: bool
    is_fallback: bool
    latency_ms: int
    tokens_in: int = 0
    tokens_out: int = 0
