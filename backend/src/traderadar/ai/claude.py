"""Optional Anthropic Claude AI provider."""

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

logger = get_logger("traderadar.ai.claude")

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


class ClaudeProvider(AIProvider):
    """Anthropic Claude provider using tool-use for structured output."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        timeout_seconds: int = 30,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model or "claude-3-5-sonnet-20241022"
        self.timeout = timeout_seconds

    @property
    def name(self) -> str:
        return "claude"

    @property
    def model_name(self) -> str:
        return self.model

    async def _call_claude_tool(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_name: str,
        tool_schema: dict[str, Any],
    ) -> tuple[dict[str, Any], int, int]:
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY tidak dikonfigurasi.")

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        body = {
            "model": self.model,
            "max_tokens": 1500,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "tools": [
                {
                    "name": tool_name,
                    "description": "Output structured response",
                    "input_schema": tool_schema,
                }
            ],
            "tool_choice": {"type": "tool", "name": tool_name},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(ANTHROPIC_API_URL, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        for content_block in data.get("content", []):
            if content_block.get("type") == "tool_use" and content_block.get("name") == tool_name:
                usage = data.get("usage", {})
                tokens_in = usage.get("input_tokens", 0)
                tokens_out = usage.get("output_tokens", 0)
                return content_block.get("input", {}), tokens_in, tokens_out

        raise ValueError(f"Claude tidak mengembalikan tool_use output yang diharapkan: {data}")

    async def generate_comment(self, payload: AIInputPayload) -> tuple[AIComment, int, int]:
        user_prompt = format_comment_user_prompt(payload)
        schema = AIComment.model_json_schema()
        parsed_json, tokens_in, tokens_out = await self._call_claude_tool(
            system_prompt=COMMENT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tool_name="record_ai_comment",
            tool_schema=schema,
        )
        return AIComment.model_validate(parsed_json), tokens_in, tokens_out

    async def generate_brief(
        self, payload: MarketBriefPayload
    ) -> tuple[MarketBriefNarrative, int, int]:
        user_prompt = format_brief_user_prompt(payload)
        schema = MarketBriefNarrative.model_json_schema()
        parsed_json, tokens_in, tokens_out = await self._call_claude_tool(
            system_prompt=BRIEF_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tool_name="record_market_brief",
            tool_schema=schema,
        )
        return MarketBriefNarrative.model_validate(parsed_json), tokens_in, tokens_out
