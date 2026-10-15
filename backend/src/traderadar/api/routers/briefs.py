"""REST API router for Market Briefs and AI quota monitoring."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from traderadar.ai.brief import generate_market_brief
from traderadar.ai.ratelimit import AIRateLimiter
from traderadar.ai.schemas import MarketBriefNarrative, MarketBriefPayload
from traderadar.ai.service import AIService
from traderadar.api.deps import get_current_user, get_db, get_redis_client
from traderadar.api.schemas.ai import AIQuotaResponse, MarketBriefResponse
from traderadar.core.config import get_settings
from traderadar.core.models import AICommentRecord, MarketBriefRecord, User

router = APIRouter(prefix="", tags=["Market Brief & AI"])


@router.get("/briefs/latest", response_model=MarketBriefResponse)
async def get_latest_brief_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Any, Depends(get_redis_client)],
) -> MarketBriefResponse:
    """Retrieve the latest Market Brief (morning or midday)."""
    stmt = select(MarketBriefRecord).order_by(desc(MarketBriefRecord.generated_at)).limit(1)
    res = await db.execute(stmt)
    brief_rec = res.scalar_one_or_none()

    if not brief_rec:
        # If no brief generated yet, compile and generate initial brief
        settings = get_settings()
        ai_service = AIService(settings=settings, redis_client=redis_client)
        narrative, brief_rec = await generate_market_brief(
            session=db,
            ai_service=ai_service,
            settings=settings,
            kind="morning",
        )
        await db.commit()

    if not brief_rec:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal membuat Market Brief awal.",
        )

    # Find associated AI comment to check provider/model/fallback
    stmt_ai = select(AICommentRecord).where(AICommentRecord.brief_id == brief_rec.id).limit(1)
    res_ai = await db.execute(stmt_ai)
    c_rec = res_ai.scalar_one_or_none()

    provider = c_rec.provider if c_rec else "gemini"
    model = c_rec.model if c_rec else "gemini-3.8-flash"
    is_fallback = c_rec.content.get("is_fallback", False) if c_rec else False

    return MarketBriefResponse(
        id=brief_rec.id,
        kind=brief_rec.kind,
        generated_at=brief_rec.generated_at.strftime("%Y-%m-%d %H:%M WIB"),
        narrative=MarketBriefNarrative.model_validate(brief_rec.narrative),
        payload=MarketBriefPayload.model_validate(brief_rec.payload),
        provider=provider,
        model=model,
        is_fallback=is_fallback,
        created_at=brief_rec.created_at,
    )


@router.post("/briefs", response_model=MarketBriefResponse)
async def generate_brief_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Any, Depends(get_redis_client)],
    kind: Annotated[
        str, Query(description="Brief kind e.g. morning, midday, ondemand")
    ] = "ondemand",
) -> MarketBriefResponse:
    """Generate a new Market Brief on-demand."""
    settings = get_settings()
    ai_service = AIService(settings=settings, redis_client=redis_client)

    narrative, brief_rec = await generate_market_brief(
        session=db,
        ai_service=ai_service,
        settings=settings,
        kind=kind,
    )
    await db.commit()

    if not brief_rec:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal menghasilkan Market Brief on-demand.",
        )

    stmt_ai = select(AICommentRecord).where(AICommentRecord.brief_id == brief_rec.id).limit(1)
    res_ai = await db.execute(stmt_ai)
    c_rec = res_ai.scalar_one_or_none()

    provider = c_rec.provider if c_rec else "gemini"
    model = c_rec.model if c_rec else "gemini-3.8-flash"
    is_fallback = c_rec.content.get("is_fallback", False) if c_rec else False

    return MarketBriefResponse(
        id=brief_rec.id,
        kind=brief_rec.kind,
        generated_at=brief_rec.generated_at.strftime("%Y-%m-%d %H:%M WIB"),
        narrative=narrative,
        payload=MarketBriefPayload.model_validate(brief_rec.payload),
        provider=provider,
        model=model,
        is_fallback=is_fallback,
        created_at=brief_rec.created_at,
    )


@router.get("/ai/quota", response_model=AIQuotaResponse)
async def get_ai_quota_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    redis_client: Annotated[Any, Depends(get_redis_client)],
) -> AIQuotaResponse:
    """Retrieve AI rate limits and remaining daily quota."""
    settings = get_settings()
    limiter = AIRateLimiter(
        redis_client=redis_client,
        rpm_limit=settings.env.AI_MAX_RPM,
        rpd_limit=settings.env.AI_MAX_RPD,
    )
    stats = await limiter.get_quota_stats()

    provider = settings.env.AI_PROVIDER
    if provider == "gemini":
        model = settings.env.GEMINI_MODEL
        if not settings.env.GEMINI_API_KEY:
            provider = "template"
            model = "template-offline"
    elif provider == "claude":
        model = settings.env.CLAUDE_MODEL
        if not settings.env.ANTHROPIC_API_KEY:
            provider = "template"
            model = "template-offline"
    else:
        provider = "template"
        model = "template-rule-engine-v1"

    return AIQuotaResponse(
        rpm_used=stats["rpm_used"],
        rpm_limit=stats["rpm_limit"],
        rpm_remaining=stats["rpm_remaining"],
        rpd_used=stats["rpd_used"],
        rpd_limit=stats["rpd_limit"],
        rpd_remaining=stats["rpd_remaining"],
        provider=provider,
        model=model,
    )
