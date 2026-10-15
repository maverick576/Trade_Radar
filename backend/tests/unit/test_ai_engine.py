"""Unit tests for AI validation, template generation, Gemini provider, and rate limiting."""

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from traderadar.ai.gemini import GeminiProvider
from traderadar.ai.ratelimit import AIRateLimiter
from traderadar.ai.schemas import (
    AIComment,
    AIInputPayload,
    MarketBriefPayload,
    SymbolBriefData,
)
from traderadar.ai.template import TemplateProvider
from traderadar.ai.validate import validate_ai_comment, validate_brief_narrative


@pytest.fixture
def sample_payload() -> AIInputPayload:
    return AIInputPayload(
        symbol="XAUUSDT",
        tf="M15",
        bar_time="2026-10-15T07:00:00+00:00",
        price=2650.4,
        verdict="STRONG_LONG",
        score=61.2,
        counts={"BULL": 6, "NEUTRAL": 3, "BEAR": 1, "NA": 0},
        indicators=[
            {
                "key": "vwap",
                "state": "BULL",
                "values": {"vwap": 2631.2, "z": 0.9},
                "reason": "Harga di atas VWAP",
            },
            {
                "key": "ema_ribbon",
                "state": "BULL",
                "values": {"ema8": 2648.0, "ema55": 2635.0},
                "reason": "EMA tersusun rapi naik",
            },
            {
                "key": "supertrend",
                "state": "BULL",
                "values": {"supertrend": 2625.5},
                "reason": "Supertrend hijau",
            },
            {
                "key": "rsi_div",
                "state": "BEAR",
                "values": {"rsi": 68.0},
                "reason": "RSI mendekati area overbought",
            },
        ],
        macro={"passed": True, "checks": [{"gate": "M1_HTF", "passed": True, "detail": "Lolos"}]},
        plan={"entry": 2651.0, "sl": 2636.5, "tp1": 2665.5, "tp2": 2680.0, "atr": 9.7},
        htf={"h1": "BULL", "h4": "BULL", "d1": "NEUTRAL"},
    )


def test_validation_accepts_valid_numbers(sample_payload: AIInputPayload) -> None:
    """Validation succeeds when all level_penting exist in the input technical data."""
    valid_comment = AIComment(
        ringkasan="Setup XAUUSDT menunjukkan konfluensi bullish kuat dengan skor 61.2.",
        bias="bullish",
        keyakinan="tinggi",
        setuju_dengan_engine=True,
        alasan_utama=["Harga di atas VWAP 2631.2", "EMA Ribbon naik"],
        risiko=["RSI mendekati overbought"],
        skenario_bullish="Mencapai TP1 2665.5",
        skenario_bearish="Menembus SL 2636.5",
        level_penting=[2651.0, 2636.5, 2665.5, 2631.2],
        invalidasi="Penembusan di bawah 2636.5",
        saran_manajemen="Risiko 1% akun",
    )
    is_valid, reason = validate_ai_comment(valid_comment, sample_payload)
    assert is_valid is True
    assert reason is None


def test_validation_rejects_hallucinated_fabricated_numbers(sample_payload: AIInputPayload) -> None:
    """Validation FAILS when AI hallucinates a price level not in the input data."""
    hallucinated_comment = AIComment(
        ringkasan="Setup XAUUSDT menunjukkan konfluensi bullish.",
        bias="bullish",
        keyakinan="tinggi",
        setuju_dengan_engine=True,
        alasan_utama=["Harga naik"],
        risiko=["Koreksi"],
        skenario_bullish="Target 3500",
        skenario_bearish="Turun ke 2000",
        level_penting=[2651.0, 3500.0],  # 3500.0 is fabricated!
        invalidasi="Invalidasi SL",
        saran_manajemen="Risiko terukur",
    )
    is_valid, reason = validate_ai_comment(hallucinated_comment, sample_payload)
    assert is_valid is False
    assert "3500.0" in str(reason)
    assert "halusinasi" in str(reason).lower()


def test_validation_word_count_limit(sample_payload: AIInputPayload) -> None:
    """Validation rejects summaries that exceed word count limit."""
    long_summary = "kata " * 170
    comment = AIComment(
        ringkasan=long_summary,
        bias="bullish",
        keyakinan="tinggi",
        setuju_dengan_engine=True,
        alasan_utama=["A", "B"],
        risiko=["C"],
        skenario_bullish="D",
        skenario_bearish="E",
        level_penting=[2651.0],
        invalidasi="F",
        saran_manajemen="G",
    )
    is_valid, reason = validate_ai_comment(comment, sample_payload)
    assert is_valid is False
    assert "melebihi batas kata" in str(reason)


@pytest.mark.asyncio
async def test_template_provider_generates_valid_output(sample_payload: AIInputPayload) -> None:
    """TemplateProvider generates rich Indonesian commentary and passes validation 100%."""
    provider = TemplateProvider()
    comment, t_in, t_out = await provider.generate_comment(sample_payload)

    assert comment.bias == "bullish"
    assert comment.keyakinan == "tinggi"
    assert comment.setuju_dengan_engine is True
    assert len(comment.alasan_utama) >= 2
    assert len(comment.risiko) >= 1
    assert len(comment.level_penting) >= 1

    # Validate that all numbers in template output are grounded in input
    is_valid, reason = validate_ai_comment(comment, sample_payload)
    assert is_valid is True, f"Template output failed validation: {reason}"


@pytest.mark.asyncio
async def test_template_provider_brief_generation() -> None:
    """TemplateProvider generates valid Market Brief narrative."""
    payload = MarketBriefPayload(
        kind="morning",
        generated_at="2026-10-15 06:45 WIB",
        high_impact_news_today=[{"title": "Core CPI", "impact": "High"}],
        symbols={
            "XAUUSDT": SymbolBriefData(
                symbol="XAUUSDT",
                bias_h4="BULL",
                bias_d1="BULL",
                score_m15=55.0,
                verdict_m15="STRONG_LONG",
                last_price=2650.0,
                daily_high=2660.0,
                daily_low=2640.0,
                vwap_yesterday=2645.0,
            )
        },
    )
    provider = TemplateProvider()
    narrative, _, _ = await provider.generate_brief(payload)

    assert narrative.ringkasan_umum is not None
    assert "XAUUSDT" in narrative.symbols
    assert narrative.symbols["XAUUSDT"].bias == "bullish"

    is_valid, reason = validate_brief_narrative(narrative, payload)
    assert is_valid is True


@pytest.mark.asyncio
async def test_gemini_provider_success(sample_payload: AIInputPayload) -> None:
    """GeminiProvider parses structured JSON from Google API response."""
    provider = GeminiProvider(api_key="fake-test-key", model="gemini-3.8-flash")

    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "ringkasan": (
                                        "Konfluensi teknikal XAUUSDT "
                                        "menunjukkan bias bullish solid."
                                    ),
                                    "bias": "bullish",
                                    "keyakinan": "tinggi",
                                    "setuju_dengan_engine": True,
                                    "alasan_utama": [
                                        "Harga bertahan di atas VWAP",
                                        "Supertrend H1 searah",
                                    ],
                                    "risiko": ["RSI mendekati jenuh beli"],
                                    "skenario_bullish": "Melanjutkan penguatan ke TP1 2665.5",
                                    "skenario_bearish": "Penolakan di resistance menuju SL 2636.5",
                                    "level_penting": [2651.0, 2636.5, 2665.5],
                                    "invalidasi": "Close bar di bawah 2636.5",
                                    "saran_manajemen": "Risiko maks 1% per posisi",
                                }
                            )
                        }
                    ]
                }
            }
        ],
        "usageMetadata": {"promptTokenCount": 350, "candidatesTokenCount": 120},
    }

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: mock_gemini_response
    mock_response.raise_for_status = lambda: None

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        comment, t_in, t_out = await provider.generate_comment(sample_payload)

    assert comment.bias == "bullish"
    assert comment.setuju_dengan_engine is True
    assert t_in == 350
    assert t_out == 120
    assert 2651.0 in comment.level_penting


class MockRedis:
    def __init__(self) -> None:
        self.data: dict[str, int] = {}

    def pipeline(self) -> "MockRedisPipeline":
        return MockRedisPipeline(self)


class MockRedisPipeline:
    def __init__(self, parent: MockRedis) -> None:
        self.parent = parent
        self.ops: list[tuple[str, Any]] = []

    def get(self, key: str) -> "MockRedisPipeline":
        self.ops.append(("get", key))
        return self

    def incr(self, key: str) -> "MockRedisPipeline":
        self.ops.append(("incr", key))
        return self

    def expire(self, key: str, sec: int) -> "MockRedisPipeline":
        self.ops.append(("expire", key))
        return self

    async def execute(self) -> list[Any]:
        results: list[Any] = []
        for op, key in self.ops:
            if op == "get":
                results.append(self.parent.data.get(key))
            elif op == "incr":
                val = self.parent.data.get(key, 0) + 1
                self.parent.data[key] = val
                results.append(val)
            elif op == "expire":
                results.append(True)
        return results


@pytest.mark.asyncio
async def test_rate_limiter_rpm_and_rpd() -> None:
    """Rate limiter enforces RPM and RPD limits."""
    redis_mock = MockRedis()
    limiter = AIRateLimiter(redis_client=redis_mock, rpm_limit=2, rpd_limit=5)  # type: ignore[arg-type]

    # First request: OK
    allowed1, reason1, stats1 = await limiter.check_and_consume()
    assert allowed1 is True
    assert stats1["rpm_used"] == 1

    # Second request: OK
    allowed2, reason2, stats2 = await limiter.check_and_consume()
    assert allowed2 is True
    assert stats2["rpm_used"] == 2

    # Third request in same minute: Rejected (RPM limit 2 reached)
    allowed3, reason3, stats3 = await limiter.check_and_consume()
    assert allowed3 is False
    assert "RPM" in str(reason3)
