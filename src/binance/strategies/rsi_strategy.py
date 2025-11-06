"""
RSI-based Trading Strategy
Buy when oversold, sell when overbought
"""

import pandas as pd
from typing import Dict
from ..trading_bot import TradingStrategy, SignalType
from ...indicators.rsi import RSICalculator


class RSIStrategy(TradingStrategy):
    """
    RSI (Relative Strength Index) based trading strategy.

    Strategy Logic:
    - BUY when RSI < oversold_threshold (default 30)
    - SELL when RSI > overbought_threshold (default 70)
    - Includes trend confirmation
    """

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30,
        overbought: float = 70,
        min_confidence: float = 0.6
    ):
        super().__init__(name=f"RSI_{period}")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.min_confidence = min_confidence
        self.rsi_calculator = RSICalculator(period, oversold, overbought)

    async def analyze(self, df: pd.DataFrame, symbol: str) -> Dict:
        """
        Analyze market data and generate trading signal.

        Args:
            df: DataFrame with OHLCV data
            symbol: Trading pair symbol

        Returns:
            Dict with keys: 'signal', 'confidence', 'reason'
        """

        # Calculate RSI
        df = self.rsi_calculator.calculate(df)

        # Get latest values
        if 'rsi' not in df.columns or df['rsi'].isna().all():
            return {
                'signal': SignalType.HOLD.value,
                'confidence': 0.0,
                'reason': 'Insufficient data for RSI calculation'
            }

        latest_rsi = df['rsi'].iloc[-1]
        latest_price = df['close'].iloc[-1]

        # Calculate trend (simple moving average comparison)
        df['sma_20'] = df['close'].rolling(window=20).mean()
        latest_sma = df['sma_20'].iloc[-1]

        is_uptrend = latest_price > latest_sma
        is_downtrend = latest_price < latest_sma

        # Generate signal
        signal = SignalType.HOLD.value
        confidence = 0.0
        reason = "No clear signal"

        # BUY Signal: RSI oversold + uptrend confirmation
        if latest_rsi < self.oversold:
            signal = SignalType.BUY.value

            # Higher confidence if price is in uptrend
            if is_uptrend:
                confidence = 0.8
                reason = f"RSI oversold ({latest_rsi:.2f}) with uptrend confirmation"
            else:
                confidence = 0.6
                reason = f"RSI oversold ({latest_rsi:.2f}) but no trend confirmation"

        # SELL Signal: RSI overbought
        elif latest_rsi > self.overbought:
            signal = SignalType.SELL.value

            # Higher confidence if price is in downtrend
            if is_downtrend:
                confidence = 0.8
                reason = f"RSI overbought ({latest_rsi:.2f}) with downtrend confirmation"
            else:
                confidence = 0.6
                reason = f"RSI overbought ({latest_rsi:.2f}) but no trend confirmation"

        # Check minimum confidence threshold
        if confidence < self.min_confidence:
            signal = SignalType.HOLD.value
            reason = f"Signal confidence too low ({confidence:.2f})"

        return {
            'signal': signal,
            'confidence': confidence,
            'reason': reason,
            'rsi': latest_rsi,
            'price': latest_price,
            'trend': 'UP' if is_uptrend else 'DOWN'
        }

    def get_parameters(self) -> Dict:
        """Return strategy parameters"""
        return {
            'period': self.period,
            'oversold': self.oversold,
            'overbought': self.overbought,
            'min_confidence': self.min_confidence
        }
