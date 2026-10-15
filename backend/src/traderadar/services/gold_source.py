"""Gold source chain management with automatic failover and event notification.

Priority chain:
1. binance_futures:XAUUSDT (default, TradFi perpetual)
2. binance_spot:PAXGUSDT (fallback crypto gold)
3. oanda:XAU_USD (optional practice CFD account)
"""

import json
import time
from typing import Any

from traderadar.core.config import get_settings
from traderadar.core.logging import get_logger
from traderadar.core.redis import get_redis
from traderadar.core.time import to_iso_utc, utc_now

logger = get_logger("traderadar.gold_source")


class GoldSourceManager:
    """Manages active gold source, tracks failures, and handles automatic fallback."""

    def __init__(self, switch_after_seconds: float = 120.0) -> None:
        self.settings = get_settings()
        self.sources = list(self.settings.app.gold.sources)
        self.switch_after_seconds = (
            switch_after_seconds or self.settings.app.gold.switch_after_seconds
        )
        self.active_index = 0
        self.last_success_time = time.time()
        self.failure_start_time: float | None = None
        self.last_error: str | None = None
        self.is_forced_fallback = False

    @property
    def active_source(self) -> str:
        """Return the current active gold source string (e.g. 'binance_futures:XAUUSDT')."""
        if 0 <= self.active_index < len(self.sources):
            return self.sources[self.active_index]
        return "binance_futures:XAUUSDT"

    @property
    def active_symbol(self) -> str:
        """Return raw market symbol for current source (e.g. 'XAUUSDT' or 'PAXGUSDT')."""
        src = self.active_source
        if ":" in src:
            return src.split(":", 1)[1]
        return src

    @property
    def active_provider(self) -> str:
        """Return provider type ('binance_futures', 'binance_spot', 'oanda')."""
        src = self.active_source
        if ":" in src:
            return src.split(":", 1)[0]
        return "binance_futures"

    @property
    def is_fallback(self) -> bool:
        """True if not using the primary source."""
        return self.active_index > 0

    def record_success(self) -> None:
        """Record successful communication with the active source."""
        self.last_success_time = time.time()
        self.failure_start_time = None
        self.last_error = None

    async def record_failure(self, error: str) -> bool:
        """Record a failure for the active source.

        Returns True if a source switch occurred.
        """
        now = time.time()
        self.last_error = error
        if self.failure_start_time is None:
            self.failure_start_time = now

        duration = now - self.failure_start_time
        logger.warning(
            "gold_source_failure",
            source=self.active_source,
            duration=round(duration, 1),
            error=error,
        )

        if duration >= self.switch_after_seconds and self.active_index < len(self.sources) - 1:
            prev = self.active_source
            self.active_index += 1
            new_source = self.active_source
            self.failure_start_time = None
            logger.error(
                "gold_source_switched",
                previous=prev,
                new=new_source,
                reason=f"Failed for {round(duration, 1)}s: {error}",
            )
            await self._broadcast_switch(prev, new_source, error)
            return True

        return False

    async def switch_to(self, target_source: str, reason: str = "Manual switch") -> bool:
        """Explicitly switch to a specific source in the chain."""
        if target_source in self.sources:
            prev = self.active_source
            self.active_index = self.sources.index(target_source)
            self.failure_start_time = None
            self.is_forced_fallback = self.active_index > 0
            logger.info("gold_source_manually_switched", target=target_source, reason=reason)
            await self._broadcast_switch(prev, target_source, reason)
            return True
        return False

    async def reset_to_primary(self, reason: str = "Primary recovered") -> bool:
        """Reset back to primary gold source."""
        if self.active_index != 0:
            prev = self.active_source
            self.active_index = 0
            self.failure_start_time = None
            self.is_forced_fallback = False
            logger.info("gold_source_reset_to_primary", reason=reason)
            await self._broadcast_switch(prev, self.active_source, reason)
            return True
        return False

    async def _broadcast_switch(self, previous: str, new_source: str, reason: str) -> None:
        """Publish gold source changed event to Redis."""
        try:
            r = await get_redis()
            payload = {
                "type": "gold_source_changed",
                "data": {
                    "active": new_source,
                    "previous": previous,
                    "is_fallback": self.is_fallback,
                    "reason": reason,
                    "ts": to_iso_utc(utc_now()),
                },
            }
            await r.publish("ui.events", json.dumps(payload))
        except Exception as exc:
            logger.warning("broadcast_switch_failed", error=str(exc))

    def get_status(self) -> dict[str, Any]:
        """Return status summary for API/UI."""
        return {
            "active_source": self.active_source,
            "active_symbol": self.active_symbol,
            "active_provider": self.active_provider,
            "is_fallback": self.is_fallback,
            "sources": self.sources,
            "last_error": self.last_error,
            "switch_after_seconds": self.switch_after_seconds,
        }
