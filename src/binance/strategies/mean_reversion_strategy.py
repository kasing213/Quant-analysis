"""
Mean Reversion Strategy
Uses Bollinger-style z-score to identify reversion opportunities.
"""

from __future__ import annotations

from typing import Dict

import pandas as pd

from ..trading_bot import TradingStrategy, SignalType


class MeanReversionStrategy(TradingStrategy):
    """
    Simple mean reversion strategy using rolling mean and standard deviation.

    Logic:
    - BUY when price deviates below mean by zscore_threshold standard deviations
    - SELL when price deviates above mean by zscore_threshold standard deviations
    - HOLD when deviation is within exit_threshold
    """

    def __init__(
        self,
        lookback_window: int = 20,
        zscore_threshold: float = 1.5,
        exit_threshold: float = 0.5,
        min_confidence: float = 0.55
    ):
        super().__init__(name=f"MEAN_REVERSION_{lookback_window}")
        if lookback_window < 5:
            raise ValueError("lookback_window must be at least 5 for mean reversion strategy")

        self.lookback_window = lookback_window
        self.zscore_threshold = zscore_threshold
        self.exit_threshold = exit_threshold
        self.min_confidence = min_confidence

    async def analyze(self, df: pd.DataFrame, symbol: str) -> Dict:
        if df.empty or len(df) < self.lookback_window + 5:
            return {
                "signal": SignalType.HOLD.value,
                "confidence": 0.0,
                "reason": "Insufficient data for mean reversion analysis"
            }

        data = df.copy()

        data["rolling_mean"] = data["close"].rolling(window=self.lookback_window).mean()
        data["rolling_std"] = data["close"].rolling(window=self.lookback_window).std(ddof=0)

        if data["rolling_std"].iloc[-1] == 0 or pd.isna(data["rolling_std"].iloc[-1]):
            return {
                "signal": SignalType.HOLD.value,
                "confidence": 0.0,
                "reason": "Rolling standard deviation unavailable"
            }

        data["zscore"] = (data["close"] - data["rolling_mean"]) / data["rolling_std"]
        data["band_width"] = data["rolling_std"] / data["rolling_mean"]

        latest = data.iloc[-1]
        previous = data.iloc[-2]

        zscore = latest["zscore"]
        mean_price = latest["rolling_mean"]
        std_dev = latest["rolling_std"]
        price = latest["close"]
        band_width = latest["band_width"]
        mean_slope = (latest["rolling_mean"] - previous["rolling_mean"]) / previous["rolling_mean"] if previous["rolling_mean"] else 0.0

        signal = SignalType.HOLD.value
        confidence = 0.0
        reason = "No mean reversion signal"

        if abs(zscore) <= self.exit_threshold:
            signal = SignalType.HOLD.value
            reason = f"Deviation within neutral zone (|z|={abs(zscore):.2f} <= {self.exit_threshold:.2f})"
        elif zscore <= -self.zscore_threshold:
            signal = SignalType.BUY.value
            overshoot = abs(zscore) - self.zscore_threshold
            volatility_boost = min(max(band_width, 0.0) * 4, 0.4)
            trend_penalty = min(max(mean_slope * 25, -0.3), 0.3)
            confidence = max(0.0, min(1.0, 0.5 + overshoot * 0.3 + volatility_boost - abs(trend_penalty)))
            reason = (
                f"Price {price:.2f} below mean {mean_price:.2f} "
                f"by {zscore:.2f} standard deviations"
            )
        elif zscore >= self.zscore_threshold:
            signal = SignalType.SELL.value
            overshoot = zscore - self.zscore_threshold
            volatility_boost = min(max(band_width, 0.0) * 4, 0.4)
            trend_penalty = min(max(-mean_slope * 25, -0.3), 0.3)
            confidence = max(0.0, min(1.0, 0.5 + overshoot * 0.3 + volatility_boost - abs(trend_penalty)))
            reason = (
                f"Price {price:.2f} above mean {mean_price:.2f} "
                f"by {zscore:.2f} standard deviations"
            )

        if confidence < self.min_confidence:
            signal = SignalType.HOLD.value
            reason = f"Mean reversion signal confidence too low ({confidence:.2f})"
            confidence = 0.0

        return {
            "signal": signal,
            "confidence": confidence,
            "reason": reason,
            "zscore": zscore,
            "mean_price": mean_price,
            "std_dev": std_dev,
            "band_width": band_width,
            "mean_slope": mean_slope,
            "price": price
        }

    def get_parameters(self) -> Dict:
        return {
            "lookback_window": self.lookback_window,
            "zscore_threshold": self.zscore_threshold,
            "exit_threshold": self.exit_threshold,
            "min_confidence": self.min_confidence
        }
