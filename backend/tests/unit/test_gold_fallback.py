import asyncio

import pytest

from traderadar.services.gold_source import GoldSourceManager


@pytest.mark.asyncio
async def test_gold_source_initial_state() -> None:
    manager = GoldSourceManager(switch_after_seconds=120.0)
    assert manager.active_source == "binance_futures:XAUUSDT"
    assert manager.active_symbol == "XAUUSDT"
    assert manager.active_provider == "binance_futures"
    assert manager.is_fallback is False


@pytest.mark.asyncio
async def test_gold_source_automatic_failover() -> None:
    # Set threshold to 0.1s for fast test
    manager = GoldSourceManager(switch_after_seconds=0.1)

    # First failure sets failure_start_time, but should not switch immediately (< 0.1s)
    await manager.record_failure("Transient network blip")
    # Immediate might be False
    assert manager.active_source == "binance_futures:XAUUSDT"

    # Simulate elapsed time > switch_after_seconds
    await asyncio.sleep(0.15)

    switched = await manager.record_failure("Timeout communicating with Binance Futures")
    assert switched is True
    assert manager.active_source == "binance_spot:PAXGUSDT"
    assert manager.active_symbol == "PAXGUSDT"
    assert manager.active_provider == "binance_spot"
    assert manager.is_fallback is True


@pytest.mark.asyncio
async def test_gold_source_recovery() -> None:
    manager = GoldSourceManager(switch_after_seconds=0.1)
    # Manually switch to PAXG
    await manager.switch_to("binance_spot:PAXGUSDT", reason="Simulated block")
    assert manager.active_source == "binance_spot:PAXGUSDT"
    assert manager.is_fallback is True

    # Recovery
    recovered = await manager.reset_to_primary(reason="XAUUSDT recovered")
    assert recovered is True
    assert manager.active_source == "binance_futures:XAUUSDT"
    assert manager.is_fallback is False


@pytest.mark.asyncio
async def test_gold_source_status_payload() -> None:
    manager = GoldSourceManager()
    status = manager.get_status()
    assert "active_source" in status
    assert "active_symbol" in status
    assert "is_fallback" in status
    assert "sources" in status
