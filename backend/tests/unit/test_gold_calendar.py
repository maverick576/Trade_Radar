"""Unit tests for Gold trading session calendar and US DST rules."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from traderadar.core.time import (
    get_gold_market_status,
    is_gold_market_open,
    is_gold_rollover,
    is_us_dst,
)

NY_TZ = ZoneInfo("America/New_York")


def test_us_dst_detection() -> None:
    # Summer (July): EDT (UTC-4), dst is active
    summer_dt = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    assert is_us_dst(summer_dt) is True

    # Winter (January): EST (UTC-5), dst is not active
    winter_dt = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    assert is_us_dst(winter_dt) is False


def test_gold_market_hours_summer_edt() -> None:
    # 2026-07-10 is a Friday.
    # In New York (EDT), 16:30 is 20:30 UTC -> market should be OPEN
    fri_open = datetime(2026, 7, 10, 20, 30, tzinfo=UTC)
    assert is_gold_market_open(fri_open) is True

    # Friday 17:30 EDT = 21:30 UTC -> market should be CLOSED (weekend close)
    fri_close = datetime(2026, 7, 10, 21, 30, tzinfo=UTC)
    assert is_gold_market_open(fri_close) is False

    # Saturday all day -> CLOSED
    sat = datetime(2026, 7, 11, 15, 0, tzinfo=UTC)
    assert is_gold_market_open(sat) is False

    # Sunday 17:00 EDT = 21:00 UTC -> CLOSED (opens at 18:00 EDT)
    sun_early = datetime(2026, 7, 12, 21, 0, tzinfo=UTC)
    assert is_gold_market_open(sun_early) is False

    # Sunday 18:30 EDT = 22:30 UTC -> OPEN
    sun_open = datetime(2026, 7, 12, 22, 30, tzinfo=UTC)
    assert is_gold_market_open(sun_open) is True


def test_gold_daily_maintenance_break() -> None:
    # 2026-07-14 is a Tuesday.
    # 17:15 EDT = 21:15 UTC -> Daily maintenance break (17:00-18:00 ET) -> CLOSED
    tue_break = datetime(2026, 7, 14, 21, 15, tzinfo=UTC)
    assert is_gold_market_open(tue_break) is False

    # 18:05 EDT = 22:05 UTC -> Reopened -> OPEN
    tue_open = datetime(2026, 7, 14, 22, 5, tzinfo=UTC)
    assert is_gold_market_open(tue_open) is True


def test_gold_rollover_window() -> None:
    # 22:00 UTC falls inside default 20:45 - 01:15 window
    inside_rollover = datetime(2026, 7, 14, 22, 0, tzinfo=UTC)
    assert is_gold_rollover(inside_rollover) is True

    # 00:30 UTC next day also falls inside
    inside_rollover_next = datetime(2026, 7, 15, 0, 30, tzinfo=UTC)
    assert is_gold_rollover(inside_rollover_next) is True

    # 10:00 UTC is well outside
    outside_rollover = datetime(2026, 7, 14, 10, 0, tzinfo=UTC)
    assert is_gold_rollover(outside_rollover) is False


def test_get_gold_market_status_payload() -> None:
    status = get_gold_market_status()
    assert "is_open" in status
    assert "is_rollover" in status
    assert "is_dst" in status
    assert "ny_time" in status
    assert "utc_time" in status
    assert "wib_time" in status
