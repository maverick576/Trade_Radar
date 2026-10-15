"""Abstract base class for AI providers."""

from abc import ABC, abstractmethod

from traderadar.ai.schemas import (
    AIComment,
    AIInputPayload,
    MarketBriefNarrative,
    MarketBriefPayload,
)


class AIProvider(ABC):
    """Abstract interface for technical commentary and brief generation."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (gemini, claude, template)."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Specific model name (e.g. gemini-3.8-flash, claude-3-7-sonnet)."""
        pass

    @abstractmethod
    async def generate_comment(self, payload: AIInputPayload) -> tuple[AIComment, int, int]:
        """Generate structured AIComment from technical input payload.

        Returns:
            (comment, tokens_in, tokens_out)
        """
        pass

    @abstractmethod
    async def generate_brief(
        self, payload: MarketBriefPayload
    ) -> tuple[MarketBriefNarrative, int, int]:
        """Generate structured MarketBriefNarrative from market snapshot data.

        Returns:
            (brief_narrative, tokens_in, tokens_out)
        """
        pass
