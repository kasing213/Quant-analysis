"""
RSI (Relative Strength Index) Calculator
Reads from Redis cache for smooth, real-time calculations
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate RSI indicator

    Args:
        prices: Series of closing prices
        period: RSI period (default 14)

    Returns:
        Series with RSI values
    """
    if len(prices) < period:
        logger.warning(f"Not enough data for RSI calculation. Need {period}, got {len(prices)}")
        return pd.Series(dtype=float)

    # Calculate price changes
    delta = prices.diff()

    # Separate gains and losses
    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)

    # Calculate average gains and losses using EMA
    avg_gains = gains.ewm(span=period, adjust=False).mean()
    avg_losses = losses.ewm(span=period, adjust=False).mean()

    # Calculate RS and RSI
    rs = avg_gains / avg_losses
    rsi = 100 - (100 / (1 + rs))

    return rsi


class RSICalculator:
    """
    RSI Calculator that works with Redis-cached data
    Provides buy/sell signals based on RSI thresholds
    """

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0
    ):
        """
        Initialize RSI Calculator

        Args:
            period: RSI calculation period
            oversold: Oversold threshold (buy signal)
            overbought: Overbought threshold (sell signal)
        """
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate RSI from DataFrame

        Args:
            df: DataFrame with 'close' column

        Returns:
            DataFrame with added 'rsi' column
        """
        if df.empty or 'close' not in df.columns:
            logger.error("Invalid DataFrame for RSI calculation")
            return df

        df = df.copy()
        df['rsi'] = calculate_rsi(df['close'], self.period)

        return df

    def get_signal(self, df: pd.DataFrame) -> Optional[str]:
        """
        Generate trading signal based on RSI

        Args:
            df: DataFrame with RSI calculated

        Returns:
            'BUY', 'SELL', or None
        """
        if df.empty or 'rsi' not in df.columns:
            return None

        # Get latest RSI value
        latest_rsi = df['rsi'].iloc[-1]

        if pd.isna(latest_rsi):
            return None

        # Generate signals
        if latest_rsi < self.oversold:
            return 'BUY'
        elif latest_rsi > self.overbought:
            return 'SELL'

        return None

    def get_signal_with_context(self, df: pd.DataFrame) -> Dict:
        """
        Get signal with additional context and metrics

        Args:
            df: DataFrame with RSI calculated

        Returns:
            Dictionary with signal, RSI value, and other metrics
        """
        if df.empty or 'rsi' not in df.columns:
            return {
                'signal': None,
                'rsi': None,
                'price': None,
                'trend': None
            }

        latest_rsi = df['rsi'].iloc[-1]
        latest_price = df['close'].iloc[-1]

        # Determine signal
        signal = self.get_signal(df)

        # Determine trend (simple: based on RSI movement)
        trend = None
        if len(df) >= 2:
            prev_rsi = df['rsi'].iloc[-2]
            if not pd.isna(prev_rsi) and not pd.isna(latest_rsi):
                trend = 'UP' if latest_rsi > prev_rsi else 'DOWN'

        # Calculate signal strength (how far from threshold)
        signal_strength = None
        if signal == 'BUY':
            signal_strength = abs(latest_rsi - self.oversold)
        elif signal == 'SELL':
            signal_strength = abs(latest_rsi - self.overbought)

        return {
            'signal': signal,
            'rsi': float(latest_rsi) if not pd.isna(latest_rsi) else None,
            'price': float(latest_price),
            'trend': trend,
            'signal_strength': signal_strength,
            'oversold_threshold': self.oversold,
            'overbought_threshold': self.overbought
        }

    def is_oversold(self, rsi_value: float) -> bool:
        """Check if RSI indicates oversold condition"""
        return rsi_value < self.oversold

    def is_overbought(self, rsi_value: float) -> bool:
        """Check if RSI indicates overbought condition"""
        return rsi_value > self.overbought


# Example usage
def example():
    """Example RSI calculation"""
    # Sample price data
    prices = pd.Series([
        100, 102, 101, 103, 105, 104, 106, 108, 107, 109,
        111, 110, 112, 114, 113, 115, 117, 116, 118, 120
    ])

    # Calculate RSI
    rsi = calculate_rsi(prices, period=14)
    print("RSI Values:")
    print(rsi.tail())

    # Using RSI Calculator
    df = pd.DataFrame({'close': prices})
    calculator = RSICalculator(period=14, oversold=30, overbought=70)

    df = calculator.calculate(df)
    signal_info = calculator.get_signal_with_context(df)

    print(f"\nSignal Info: {signal_info}")


if __name__ == "__main__":
    example()
