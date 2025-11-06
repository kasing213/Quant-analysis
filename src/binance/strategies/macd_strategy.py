"""
MACD-based Trading Strategy
Uses MACD crossovers with trend confirmation for signal generation.
"""

from __future__ import annotations

from typing import Dict

import pandas as pd

from ..trading_bot import TradingStrategy, SignalType


class MACDStrategy(TradingStrategy):
    """
    Moving Average Convergence Divergence (MACD) strategy.

    Logic:
    - BUY when MACD crosses above signal line with positive histogram and bullish trend bias
    - SELL when MACD crosses below signal line with negative histogram
    """

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        min_confidence: float = 0.55
    ):
        super().__init__(name=f"MACD_{fast_period}_{slow_period}_{signal_period}")
        if fast_period >= slow_period:
            raise ValueError("fast_period must be less than slow_period for MACD strategy")

        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.min_confidence = min_confidence

    async def analyze(self, df: pd.DataFrame, symbol: str) -> Dict:
        required_bars = max(self.slow_period + self.signal_period, self.slow_period * 2)
        if df.empty or len(df) < required_bars:
            return {
                "signal": SignalType.HOLD.value,
                "confidence": 0.0,
                "reason": "Insufficient data for MACD calculation"
            }

        data = df.copy()

        data["ema_fast"] = data["close"].ewm(span=self.fast_period, adjust=False).mean()
        data["ema_slow"] = data["close"].ewm(span=self.slow_period, adjust=False).mean()
        data["macd"] = data["ema_fast"] - data["ema_slow"]
        data["macd_signal"] = data["macd"].ewm(span=self.signal_period, adjust=False).mean()
        data["macd_hist"] = data["macd"] - data["macd_signal"]
        data["ema_trend"] = data["close"].ewm(span=self.slow_period * 2, adjust=False).mean()

        if data[["macd", "macd_signal", "macd_hist"]].tail(5).isna().any().any():
            return {
                "signal": SignalType.HOLD.value,
                "confidence": 0.0,
                "reason": "MACD indicators contain NaN values"
            }

        latest = data.iloc[-1]
        previous = data.iloc[-2]

        macd = latest["macd"]
        macd_signal = latest["macd_signal"]
        macd_hist = latest["macd_hist"]
        price = latest["close"]
        ema_trend = latest["ema_trend"]

        cross_up = previous["macd"] <= previous["macd_signal"] and macd > macd_signal
        cross_down = previous["macd"] >= previous["macd_signal"] and macd < macd_signal
        trend_bias = (price - ema_trend) / ema_trend if ema_trend else 0.0

        signal = SignalType.HOLD.value
        confidence = 0.0
        reason = "No actionable MACD signal"

        if cross_up and macd_hist > 0:
            signal = SignalType.BUY.value
            base_confidence = min(abs(macd_hist) * 6, 0.4)
            trend_bonus = max(min(trend_bias * 3, 0.3), -0.1)
            confidence = max(0.0, min(1.0, 0.5 + base_confidence + trend_bonus))
            reason = (
                f"MACD bullish crossover ({macd:.4f} > {macd_signal:.4f}) "
                f"with histogram {macd_hist:.4f}"
            )
        elif cross_down and macd_hist < 0:
            signal = SignalType.SELL.value
            base_confidence = min(abs(macd_hist) * 6, 0.4)
            trend_penalty = max(min(-trend_bias * 3, 0.3), -0.1)
            confidence = max(0.0, min(1.0, 0.5 + base_confidence + trend_penalty))
            reason = (
                f"MACD bearish crossover ({macd:.4f} < {macd_signal:.4f}) "
                f"with histogram {macd_hist:.4f}"
            )

        if confidence < self.min_confidence:
            signal = SignalType.HOLD.value
            reason = f"MACD signal confidence too low ({confidence:.2f})"
            confidence = 0.0

        return {
            "signal": signal,
            "confidence": confidence,
            "reason": reason,
            "macd": macd,
            "macd_signal": macd_signal,
            "macd_hist": macd_hist,
            "trend_bias": trend_bias,
            "price": price
        }

    def get_parameters(self) -> Dict:
        return {
            "fast_period": self.fast_period,
            "slow_period": self.slow_period,
            "signal_period": self.signal_period,
            "min_confidence": self.min_confidence
        }
