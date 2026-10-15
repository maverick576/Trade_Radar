"""High-performance Candlestick Chart rendering for Telegram alerts and on-demand analysis.

Uses mplfinance with an Agg headless backend to generate clean dark-theme chart PNGs
matching TradeRadar UI aesthetics (confluence indicators, volume, key levels).
"""

import io
from typing import Any

import matplotlib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Headless non-GUI backend
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd

from traderadar.core.logging import get_logger
from traderadar.core.models import Candle

logger = get_logger("traderadar.telegram.charts")


def render_candlestick_chart(
    candles: list[dict[str, Any]] | list[Candle],
    symbol: str,
    tf: str,
    levels: dict[str, float] | None = None,
) -> bytes:
    """Render a dark-mode candlestick chart PNG buffer from candle data."""
    if not candles:
        raise ValueError("Candles data cannot be empty")

    # Format into DataFrame records
    rows: list[dict[str, Any]] = []
    for c in candles:
        if isinstance(c, dict):
            rows.append(
                {
                    "Date": pd.to_datetime(c["open_time"]),
                    "Open": float(c["open"]),
                    "High": float(c["high"]),
                    "Low": float(c["low"]),
                    "Close": float(c["close"]),
                    "Volume": float(c.get("volume", 0.0)),
                }
            )
        else:
            rows.append(
                {
                    "Date": pd.to_datetime(c.open_time),
                    "Open": float(c.open),
                    "High": float(c.high),
                    "Low": float(c.low),
                    "Close": float(c.close),
                    "Volume": float(c.volume),
                }
            )

    df = pd.DataFrame(rows)
    df.set_index("Date", inplace=True)
    df.sort_index(inplace=True)

    # Compute fast exponential moving averages if sufficient data
    addplots: list[Any] = []
    if len(df) >= 21:
        df["EMA8"] = df["Close"].ewm(span=8, adjust=False).mean()
        df["EMA21"] = df["Close"].ewm(span=21, adjust=False).mean()
        addplots.append(
            mpf.make_addplot(
                df["EMA8"],
                color="#38BDF8",
                width=1.0,
                alpha=0.8,
            )
        )
        addplots.append(
            mpf.make_addplot(
                df["EMA21"],
                color="#F59E0B",
                width=1.1,
                alpha=0.85,
            )
        )
    if len(df) >= 55:
        df["EMA55"] = df["Close"].ewm(span=55, adjust=False).mean()
        addplots.append(
            mpf.make_addplot(
                df["EMA55"],
                color="#A855F7",
                width=1.2,
                alpha=0.9,
            )
        )

    # Define custom TradeRadar dark style
    mc = mpf.make_marketcolors(
        up="#00C076",
        down="#FF5353",
        edge="inherit",
        wick="inherit",
        volume={"up": "#00C076", "down": "#FF5353"},
    )
    custom_style = mpf.make_mpf_style(
        base_mpf_style="nightclouds",
        marketcolors=mc,
        facecolor="#0B0E14",
        edgecolor="#1E293B",
        figcolor="#0B0E14",
        gridcolor="#161F2E",
        gridstyle="--",
        y_on_right=True,
    )

    # Prepare horizontal price levels if provided (Entry, SL, TP1, TP2)
    hlines_dict: dict[str, Any] | None = None
    if levels:
        hlines_prices: list[float] = []
        hlines_colors: list[str] = []
        hlines_styles: list[str] = []

        if "entry" in levels:
            hlines_prices.append(levels["entry"])
            hlines_colors.append("#FACC15")  # Yellow
            hlines_styles.append("-")

        if "sl" in levels:
            hlines_prices.append(levels["sl"])
            hlines_colors.append("#EF4444")  # Red
            hlines_styles.append("--")

        if "tp1" in levels:
            hlines_prices.append(levels["tp1"])
            hlines_colors.append("#10B981")  # Green
            hlines_styles.append("--")

        if "tp2" in levels:
            hlines_prices.append(levels["tp2"])
            hlines_colors.append("#059669")  # Dark green
            hlines_styles.append("-.")

        if hlines_prices:
            hlines_dict = {
                "hlines": hlines_prices,
                "colors": hlines_colors,
                "linestyle": hlines_styles,
                "linewidths": 1.2,
            }

    buf = io.BytesIO()
    clean_sym = symbol.upper()
    title_text = f"\nTradeRadar · {clean_sym} [{tf.upper()}]"

    # Plot figure
    plot_kwargs: dict[str, Any] = {
        "type": "candle",
        "style": custom_style,
        "volume": True,
        "title": title_text,
        "savefig": {"fname": buf, "dpi": 110, "bbox_inches": "tight", "pad_inches": 0.15},
        "figsize": (9.2, 5.2),
        "returnfig": True,
    }
    if addplots:
        plot_kwargs["addplot"] = addplots
    if hlines_dict:
        plot_kwargs["hlines"] = hlines_dict

    fig, _ = mpf.plot(df, **plot_kwargs)
    plt.close(fig)

    buf.seek(0)
    image_bytes = buf.getvalue()
    buf.close()
    return image_bytes


async def load_candles_and_render_chart(
    session: AsyncSession,
    symbol: str,
    tf: str = "M15",
    levels: dict[str, float] | None = None,
    limit: int = 60,
) -> bytes | None:
    """Load latest closed candles from database and render chart PNG."""
    clean_sym = symbol.upper().replace("USDT", "").replace("_", "")
    if clean_sym == "XAU":
        clean_sym = "XAUUSD"

    # Try both clean symbol (e.g. XAUUSD) and USDT suffix (e.g. XAUUSDT)
    stmt = (
        select(Candle)
        .where(
            (Candle.symbol == clean_sym)
            | (Candle.symbol == f"{clean_sym}USDT")
            | (Candle.symbol == symbol.upper())
        )
        .where(Candle.tf == tf.upper())
        .order_by(Candle.open_time.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    candles = list(result.scalars().all())

    if not candles or len(candles) < 5:
        # Fallback without tf case sensitivity if needed
        stmt_lower = (
            select(Candle)
            .where(
                (Candle.symbol == clean_sym)
                | (Candle.symbol == f"{clean_sym}USDT")
                | (Candle.symbol == symbol.upper())
            )
            .where(Candle.tf == tf.lower())
            .order_by(Candle.open_time.desc())
            .limit(limit)
        )
        res_lower = await session.execute(stmt_lower)
        candles = list(res_lower.scalars().all())

    if not candles or len(candles) < 5:
        logger.warning("insufficient_candles_for_chart", symbol=symbol, tf=tf, count=len(candles))
        return None

    candles.reverse()  # Chronological order
    return render_candlestick_chart(candles=candles, symbol=clean_sym, tf=tf, levels=levels)
