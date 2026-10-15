import json
from typing import Any

import pytest

from traderadar.services.binance import BinanceConnector


@pytest.mark.asyncio
async def test_build_stream_url() -> None:
    connector = BinanceConnector()
    url = await connector.build_stream_url(
        futures_symbols=["BTCUSDT", "XAUUSDT"],
        timeframes=["M15", "H1"],
        include_depth=True,
        include_mark_price=True,
    )
    assert url.startswith("wss://fstream.binance.com/stream?streams=")
    assert "btcusdt@kline_15m" in url
    assert "btcusdt@kline_1h" in url
    assert "btcusdt@depth20@500ms" in url
    assert "btcusdt@markPrice@1s" in url
    assert "xauusdt@kline_15m" in url


@pytest.mark.asyncio
async def test_stream_message_routing_kline_closed() -> None:
    connector = BinanceConnector()
    closed_candles: list[dict[str, Any]] = []

    async def on_closed(candle: dict[str, Any]) -> None:
        closed_candles.append(candle)

    connector.on_candle_closed = on_closed

    # Sample Binance futures kline closed event
    kline_msg = json.dumps(
        {
            "stream": "btcusdt@kline_15m",
            "data": {
                "s": "BTCUSDT",
                "k": {
                    "t": 1700000000000,
                    "T": 1700000899999,
                    "s": "BTCUSDT",
                    "i": "15m",
                    "o": "81000.00",
                    "c": "81200.50",
                    "h": "81300.00",
                    "l": "80950.00",
                    "v": "150.25",
                    "V": "80.10",  # Taker buy base asset volume
                    "x": True,  # Is closed
                },
            },
        }
    )

    await connector._process_stream_message(kline_msg)

    assert len(closed_candles) == 1
    c = closed_candles[0]
    assert c["symbol"] == "BTCUSDT"
    assert c["tf"] == "M15"
    assert c["open"] == 81000.0
    assert c["close"] == 81200.5
    assert c["high"] == 81300.0
    assert c["low"] == 80950.0
    assert c["volume"] == 150.25
    assert c["taker_buy_volume"] == 80.10
    assert c["is_closed"] is True


@pytest.mark.asyncio
async def test_stream_message_routing_depth() -> None:
    connector = BinanceConnector()
    depth_records: list[tuple[str, list[list[float]], list[list[float]]]] = []

    async def on_depth(symbol: str, bids: list[list[float]], asks: list[list[float]]) -> None:
        depth_records.append((symbol, bids, asks))

    connector.on_depth = on_depth

    depth_msg = json.dumps(
        {
            "stream": "btcusdt@depth20@500ms",
            "data": {
                "b": [["81200.00", "5.2"], ["81190.00", "3.1"]],
                "a": [["81201.00", "4.0"], ["81205.00", "2.5"]],
            },
        }
    )

    await connector._process_stream_message(depth_msg)

    assert len(depth_records) == 1
    sym, bids, asks = depth_records[0]
    assert sym == "BTCUSDT"
    assert bids[0] == [81200.0, 5.2]
    assert asks[0] == [81201.0, 4.0]
