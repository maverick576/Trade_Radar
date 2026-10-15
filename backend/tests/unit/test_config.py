"""Unit tests for configuration validation."""

import pytest
from pydantic import ValidationError

from traderadar.core.config import AppSettings, EnvSettings, WatchlistItem


def test_env_settings_defaults() -> None:
    """Test default values of EnvSettings."""
    env = EnvSettings(SECRET_KEY="a" * 32)
    assert env.APP_PORT == 8080
    assert env.APP_TIMEZONE == "Asia/Jakarta"
    assert env.DATABASE_URL is not None
    assert "postgresql+asyncpg://" in env.DATABASE_URL


def test_watchlist_validation_max_five() -> None:
    """Watchlist must enforce maximum 5 symbols."""
    items = [WatchlistItem(symbol=f"SYM{i}", display=f"SYM{i}", asset="crypto") for i in range(6)]
    with pytest.raises(ValidationError):
        AppSettings(watchlist=items)


def test_watchlist_validation_valid() -> None:
    """Watchlist with 4 symbols is valid."""
    items = [
        WatchlistItem(symbol="BTCUSDT", display="BTCUSD", asset="crypto"),
        WatchlistItem(symbol="ETHUSDT", display="ETHUSD", asset="crypto"),
        WatchlistItem(symbol="SOLUSDT", display="SOLUSD", asset="crypto"),
        WatchlistItem(symbol="XAUUSD", display="XAUUSD", asset="gold"),
    ]
    app_settings = AppSettings(watchlist=items)
    assert len(app_settings.watchlist) == 4
    assert app_settings.watchlist[3].asset == "gold"
