"""Central AI Service orchestrating rate limiting, validation, providers, and persistence."""

import json
import time

import redis.asyncio as aioredis
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from traderadar.ai.base import AIProvider
from traderadar.ai.claude import ClaudeProvider
from traderadar.ai.gemini import GeminiProvider
from traderadar.ai.ratelimit import AIRateLimiter
from traderadar.ai.schemas import (
    AIInputPayload,
    AIResponse,
    MarketBriefNarrative,
    MarketBriefPayload,
)
from traderadar.ai.template import TemplateProvider
from traderadar.ai.validate import validate_ai_comment, validate_brief_narrative
from traderadar.core.config import Settings
from traderadar.core.events import CHANNEL_UI_EVENTS, UIEvent
from traderadar.core.logging import get_logger
from traderadar.core.models import AICommentRecord, MarketBriefRecord
from traderadar.core.time import utc_now

logger = get_logger("traderadar.ai.service")


class AIService:
    """Orchestrates AI analysis generation, rate-limits, validation, and fallbacks."""

    def __init__(self, settings: Settings, redis_client: aioredis.Redis) -> None:
        self.settings = settings
        self.redis = redis_client
        self.rate_limiter = AIRateLimiter(
            redis_client=redis_client,
            rpm_limit=settings.env.AI_MAX_RPM,
            rpd_limit=settings.env.AI_MAX_RPD,
        )
        self.template_provider = TemplateProvider()

        # Initialize primary provider
        provider_name = settings.env.AI_PROVIDER.lower()
        if provider_name == "claude" and settings.env.ANTHROPIC_API_KEY:
            self.primary_provider: AIProvider = ClaudeProvider(
                api_key=settings.env.ANTHROPIC_API_KEY,
                model=settings.env.CLAUDE_MODEL,
                timeout_seconds=settings.env.AI_TIMEOUT_SECONDS,
            )
        elif settings.env.GEMINI_API_KEY:
            self.primary_provider = GeminiProvider(
                api_key=settings.env.GEMINI_API_KEY,
                model=settings.env.GEMINI_MODEL,
                fallback_model=settings.env.GEMINI_FALLBACK_MODEL,
                timeout_seconds=settings.env.AI_TIMEOUT_SECONDS,
            )
        else:
            self.primary_provider = self.template_provider

    async def get_latest_comment_for_symbol(
        self, session: AsyncSession, symbol: str
    ) -> AICommentRecord | None:
        """Fetch the most recent AI comment for a given symbol."""
        stmt = (
            select(AICommentRecord)
            .where(AICommentRecord.kind.in_(["analysis", "ondemand"]))
            .order_by(desc(AICommentRecord.created_at))
            .limit(10)
        )
        res = await session.execute(stmt)
        records = res.scalars().all()
        for rec in records:
            # check content
            c = rec.content
            if c.get("symbol") == symbol.upper():
                return rec
        return records[0] if records else None

    async def generate_comment(
        self,
        payload: AIInputPayload,
        analysis_id: int | None = None,
        session: AsyncSession | None = None,
        is_ondemand: bool = False,
    ) -> AIResponse:
        """Generate structured AI technical analysis commentary with full validation."""
        t0 = time.monotonic()
        cache_key = f"cache:ai:comment:{payload.symbol}:{payload.tf}:{payload.bar_time}"

        # 1. Check Redis cache if not ondemand forced
        if not is_ondemand:
            cached_raw = await self.redis.get(cache_key)
            if cached_raw:
                try:
                    cached_dict = json.loads(cached_raw)
                    return AIResponse.model_validate(cached_dict)
                except Exception:
                    pass

        # 2. Check Rate Limit
        allowed, reason, quota_stats = await self.rate_limiter.check_and_consume()
        tokens_in = 0
        tokens_out = 0
        valid = True
        is_fallback = False

        if not allowed or isinstance(self.primary_provider, TemplateProvider):
            # Fallback directly to template
            is_fallback = True
            comment, _, _ = await self.template_provider.generate_comment(payload)
            provider_used = self.template_provider.name
            model_used = self.template_provider.model_name
        else:
            try:
                comment, tokens_in, tokens_out = await self.primary_provider.generate_comment(
                    payload
                )
                provider_used = self.primary_provider.name
                model_used = self.primary_provider.model_name

                # 3. Validate numbers against input data to prevent hallucination
                is_valid, validation_error = validate_ai_comment(comment, payload)
                if not is_valid:
                    logger.warning(
                        "ai_comment_validation_failed_hallucinated_numbers",
                        reason=validation_error,
                        symbol=payload.symbol,
                    )
                    valid = False
                    is_fallback = True
                    # Fallback to template provider
                    comment, _, _ = await self.template_provider.generate_comment(payload)
                    provider_used = "template"
                    model_used = "template-fallback-invalid-numbers"

            except Exception as exc:
                logger.warning(
                    "ai_primary_provider_failed_using_template",
                    error=str(exc),
                    symbol=payload.symbol,
                )
                is_fallback = True
                comment, _, _ = await self.template_provider.generate_comment(payload)
                provider_used = "template"
                model_used = "template-fallback-error"

        latency_ms = int((time.monotonic() - t0) * 1000)

        response = AIResponse(
            comment=comment,
            provider=provider_used,
            model=model_used,
            valid=valid,
            is_fallback=is_fallback,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )

        # 4. Persist to DB if session provided
        if session:
            try:
                db_content = comment.model_dump(mode="json")
                db_content["symbol"] = payload.symbol
                db_content["tf"] = payload.tf
                db_content["is_fallback"] = is_fallback

                rec = AICommentRecord(
                    analysis_id=analysis_id,
                    brief_id=None,
                    kind="ondemand" if is_ondemand else "analysis",
                    provider=provider_used,
                    model=model_used,
                    content=db_content,
                    valid=valid,
                    latency_ms=latency_ms,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    created_at=utc_now(),
                )
                session.add(rec)
                await session.flush()
            except Exception as exc:
                logger.error("failed_to_persist_ai_comment", error=str(exc))

        # 5. Cache response in Redis (1 day TTL)
        try:
            await self.redis.set(cache_key, response.model_dump_json(), ex=86400)
        except Exception:
            pass

        # 6. Publish UIEvent
        try:
            ui_evt = UIEvent(
                type="ai_comment",
                data={
                    "symbol": payload.symbol,
                    "tf": payload.tf,
                    "comment": comment.model_dump(mode="json"),
                    "provider": provider_used,
                    "model": model_used,
                    "valid": valid,
                    "is_fallback": is_fallback,
                    "latency_ms": latency_ms,
                },
                ts=utc_now(),
            )
            await self.redis.publish(CHANNEL_UI_EVENTS, ui_evt.model_dump_json())
        except Exception:
            pass

        return response

    async def generate_brief(
        self,
        payload: MarketBriefPayload,
        session: AsyncSession | None = None,
    ) -> tuple[MarketBriefNarrative, MarketBriefRecord | None]:
        """Generate structured Market Brief narrative, validate, and persist."""
        t0 = time.monotonic()
        allowed, reason, quota_stats = await self.rate_limiter.check_and_consume()

        tokens_in = 0
        tokens_out = 0
        valid = True
        is_fallback = False

        if not allowed or isinstance(self.primary_provider, TemplateProvider):
            is_fallback = True
            narrative, _, _ = await self.template_provider.generate_brief(payload)
            provider_used = self.template_provider.name
            model_used = self.template_provider.model_name
        else:
            try:
                narrative, tokens_in, tokens_out = await self.primary_provider.generate_brief(
                    payload
                )
                provider_used = self.primary_provider.name
                model_used = self.primary_provider.model_name

                is_valid, validation_error = validate_brief_narrative(narrative, payload)
                if not is_valid:
                    logger.warning(
                        "brief_narrative_validation_failed",
                        reason=validation_error,
                    )
                    valid = False
                    is_fallback = True
                    narrative, _, _ = await self.template_provider.generate_brief(payload)
                    provider_used = "template"
                    model_used = "template-fallback-invalid-numbers"

            except Exception as exc:
                logger.warning("brief_primary_provider_failed", error=str(exc))
                is_fallback = True
                narrative, _, _ = await self.template_provider.generate_brief(payload)
                provider_used = "template"
                model_used = "template-fallback-error"

        latency_ms = int((time.monotonic() - t0) * 1000)

        brief_rec: MarketBriefRecord | None = None
        if session:
            try:
                brief_rec = MarketBriefRecord(
                    kind=payload.kind,
                    generated_at=utc_now(),
                    payload=payload.model_dump(mode="json"),
                    narrative=narrative.model_dump(mode="json"),
                    created_at=utc_now(),
                )
                session.add(brief_rec)
                await session.flush()

                ai_rec = AICommentRecord(
                    analysis_id=None,
                    brief_id=brief_rec.id,
                    kind="brief",
                    provider=provider_used,
                    model=model_used,
                    content={
                        "narrative": narrative.model_dump(mode="json"),
                        "is_fallback": is_fallback,
                    },
                    valid=valid,
                    latency_ms=latency_ms,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    created_at=utc_now(),
                )
                session.add(ai_rec)
                await session.flush()
            except Exception as exc:
                logger.error("failed_to_persist_market_brief", error=str(exc))

        # Publish UIEvent for Brief
        try:
            ui_evt = UIEvent(
                type="brief",
                data={
                    "brief_id": brief_rec.id if brief_rec else None,
                    "kind": payload.kind,
                    "narrative": narrative.model_dump(mode="json"),
                    "generated_at": payload.generated_at,
                    "provider": provider_used,
                    "is_fallback": is_fallback,
                },
                ts=utc_now(),
            )
            await self.redis.publish(CHANNEL_UI_EVENTS, ui_evt.model_dump_json())
        except Exception:
            pass

        return narrative, brief_rec
