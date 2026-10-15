"""Order Book Imbalance (OBI) microstructure indicator filtering levels within 0.5% of mid price."""

import numpy as np
import pandas as pd

from traderadar.engine.indicators.base import IndicatorResult, MarketContext


class OrderbookIndicator:
    """Evaluates top-of-book depth volume imbalance within 0.5% of mid price."""

    def __init__(
        self,
        depth_pct: float = 0.5,
        smooth_seconds: int = 60,
        threshold: float = 0.15,
    ) -> None:
        self.depth_pct = depth_pct
        self.smooth_seconds = smooth_seconds
        self.threshold = threshold

    def evaluate(
        self,
        df: pd.DataFrame,
        context: MarketContext | None = None,
    ) -> IndicatorResult:
        if context is None:
            return IndicatorResult(
                key="orderbook",
                category="microstructure",
                state="NA",
                strength=0.0,
                values={},
                reason="Data order book live tidak tersedia.",
                live_only=True,
            )

        # If smoothed_obi is directly provided
        if context.smoothed_obi is not None:
            obi = context.smoothed_obi
            bid_vol = 0.0
            ask_vol = 0.0
            mid = 0.0
        elif (
            context.orderbook_bids is not None
            and context.orderbook_asks is not None
            and len(context.orderbook_bids) > 0
            and len(context.orderbook_asks) > 0
        ):
            best_bid = context.orderbook_bids[0][0]
            best_ask = context.orderbook_asks[0][0]
            mid = (best_bid + best_ask) / 2.0

            # Filter levels within depth_pct (0.5%)
            lower_limit = mid * (1.0 - self.depth_pct / 100.0)
            upper_limit = mid * (1.0 + self.depth_pct / 100.0)

            bid_vol = sum(qty for p, qty in context.orderbook_bids if p >= lower_limit)
            ask_vol = sum(qty for p, qty in context.orderbook_asks if p <= upper_limit)

            tot_vol = bid_vol + ask_vol
            obi = (bid_vol - ask_vol) / tot_vol if tot_vol > 0 else 0.0
        else:
            return IndicatorResult(
                key="orderbook",
                category="microstructure",
                state="NA",
                strength=0.0,
                values={},
                reason="Kedalaman order book kosong atau tidak tersedia.",
                live_only=True,
            )

        values = {
            "obi": round(obi, 4),
            "bid_volume": round(bid_vol, 2),
            "ask_volume": round(ask_vol, 2),
            "mid_price": round(mid, 2),
        }

        strength = float(np.clip(abs(obi) / 0.4, 0.0, 1.0))

        if obi > self.threshold:
            state = "BULL"
            reason = f"Tekanan beli di orderbook (OBI {obi:+.2f} > +0.15)."
        elif obi < -self.threshold:
            state = "BEAR"
            reason = f"Tekanan jual di orderbook (OBI {obi:+.2f} < -0.15)."
        else:
            state = "NEUTRAL"
            strength = 0.0
            reason = f"Keseimbangan orderbook simetris (OBI {obi:+.2f})."

        return IndicatorResult(
            key="orderbook",
            category="microstructure",
            state=state,
            strength=round(strength, 4),
            values=values,
            reason=reason,
            live_only=True,
        )
