"""Google Gemini AI provider using structured outputs and direct REST client."""

import asyncio
import json
from typing import Any

import httpx

from traderadar.ai.base import AIProvider
from traderadar.ai.prompts import (
    BRIEF_SYSTEM_PROMPT,
    COMMENT_SYSTEM_PROMPT,
    format_brief_user_prompt,
    format_comment_user_prompt,
)
from traderadar.ai.schemas import (
    AIComment,
    AIInputPayload,
    MarketBriefNarrative,
    MarketBriefPayload,
)
from traderadar.core.logging import get_logger

logger = get_logger("traderadar.ai.gemini")

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(AIProvider):
    """Google Gemini AI provider implementing structured JSON outputs."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.8-flash",
        fallback_model: str = "gemini-3.5-flash-lite",
        timeout_seconds: int = 30,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key.strip()
        self.primary_model = model
        self.fallback_model = fallback_model
        self.timeout = timeout_seconds
        self.max_retries = max_retries

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self.primary_model

    async def _call_gemini_api(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, Any],
    ) -> tuple[dict[str, Any], int, int]:
        """Make HTTP POST to Google Generative Language API with retries and exponential backoff."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY tidak dikonfigurasi.")

        url = f"{GEMINI_API_BASE}/{model}:generateContent?key={self.api_key}"

        request_body = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json",
                "responseSchema": response_schema,
            },
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, json=request_body)

                if resp.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        "gemini_temporary_status",
                        status=resp.status_code,
                        attempt=attempt,
                        body=resp.text[:200],
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(1.0 * (2**attempt))
                        continue
                    resp.raise_for_status()

                resp.raise_for_status()
                data = resp.json()

                candidates = data.get("candidates", [])
                if not candidates:
                    raise ValueError(f"Gemini response tidak memiliki candidates: {data}")

                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts or "text" not in parts[0]:
                    raise ValueError(f"Gemini response content kosong: {data}")

                raw_text = parts[0]["text"]
                parsed_json = json.loads(raw_text)

                usage = data.get("usageMetadata", {})
                tokens_in = usage.get("promptTokenCount", 0)
                tokens_out = usage.get("candidatesTokenCount", 0)

                return parsed_json, tokens_in, tokens_out

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "gemini_request_attempt_failed",
                    attempt=attempt,
                    model=model,
                    error=str(exc),
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(1.0 * (2**attempt))

        raise last_error or RuntimeError("Gemini request gagal setelah retry.")

    async def generate_comment(self, payload: AIInputPayload) -> tuple[AIComment, int, int]:
        user_prompt = format_comment_user_prompt(payload)
        schema = AIComment.model_json_schema()

        # Try primary model first, fallback model on failure
        models_to_try = [self.primary_model]
        if self.fallback_model and self.fallback_model != self.primary_model:
            models_to_try.append(self.fallback_model)

        last_exc: Exception | None = None
        for model in models_to_try:
            try:
                parsed_json, tokens_in, tokens_out = await self._call_gemini_api(
                    model=model,
                    system_prompt=COMMENT_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    response_schema=schema,
                )
                comment = AIComment.model_validate(parsed_json)
                return comment, tokens_in, tokens_out
            except Exception as exc:
                last_exc = exc
                logger.warning("gemini_model_failed_trying_fallback", model=model, error=str(exc))

        raise last_exc or RuntimeError("Semua model Gemini gagal merespons.")

    async def generate_brief(
        self, payload: MarketBriefPayload
    ) -> tuple[MarketBriefNarrative, int, int]:
        user_prompt = format_brief_user_prompt(payload)
        schema = MarketBriefNarrative.model_json_schema()

        models_to_try = [self.primary_model]
        if self.fallback_model and self.fallback_model != self.primary_model:
            models_to_try.append(self.fallback_model)

        last_exc: Exception | None = None
        for model in models_to_try:
            try:
                parsed_json, tokens_in, tokens_out = await self._call_gemini_api(
                    model=model,
                    system_prompt=BRIEF_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    response_schema=schema,
                )
                brief = MarketBriefNarrative.model_validate(parsed_json)
                return brief, tokens_in, tokens_out
            except Exception as exc:
                last_exc = exc
                logger.warning("gemini_brief_model_failed", model=model, error=str(exc))

        raise last_exc or RuntimeError("Semua model Gemini gagal untuk Market Brief.")
