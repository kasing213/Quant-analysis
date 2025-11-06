"""
Order Flow Analysis Module

Provides institutional-grade order flow analytics including:
- Cumulative Volume Delta (CVD)
- Volume Profile (POC, VAH, VAL)
- Absorption and Exhaustion detection
- Imbalance detection
- Market auction theory metrics
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class OrderFlowMetrics:
    """Order flow analysis results"""
    timestamp: datetime
    cvd: float  # Cumulative Volume Delta
    delta: float  # Current bar delta
    delta_percent: float  # Delta as % of total volume
    buy_volume: float
    sell_volume: float
    total_volume: float
    absorption_detected: bool
    exhaustion_detected: bool
    imbalance_ratio: float  # Buy/Sell ratio


@dataclass
class VolumeProfile:
    """Volume Profile analysis results"""
    poc: float  # Point of Control (price with highest volume)
    vah: float  # Value Area High
    val: float  # Value Area Low
    value_area_volume_pct: float  # % of volume in value area (typically 70%)
    volume_nodes: Dict[float, float]  # Price -> Volume mapping
    high_volume_nodes: List[float]  # Significant volume levels
    low_volume_nodes: List[float]  # Low volume nodes (potential targets)


class OrderFlowAnalyzer:
    """
    Analyzes order flow to identify institutional activity and market structure.

    Order flow analysis helps identify:
    - Buying/selling pressure
    - Institutional accumulation/distribution
    - Support/resistance based on volume
    - Market imbalances
    """

    def __init__(
        self,
        imbalance_threshold: float = 1.5,
        absorption_threshold: float = 2.0,
        value_area_pct: float = 0.70,
        price_precision: int = 2
    ):
        """
        Args:
            imbalance_threshold: Ratio threshold for buy/sell imbalance detection
            absorption_threshold: Volume ratio for absorption detection
            value_area_pct: Percentage of volume to include in value area (0.70 = 70%)
            price_precision: Decimal places for price rounding in volume profile
        """
        self.imbalance_threshold = imbalance_threshold
        self.absorption_threshold = absorption_threshold
        self.value_area_pct = value_area_pct
        self.price_precision = price_precision

    def calculate_delta(
        self,
        df: pd.DataFrame,
        use_tape_reading: bool = False
    ) -> pd.DataFrame:
        """
        Calculate volume delta (buying pressure - selling pressure).

        Args:
            df: DataFrame with OHLCV data
            use_tape_reading: If True, use close vs open for classification
                             If False, requires buy_volume and sell_volume columns

        Returns:
            DataFrame with added delta columns
        """
        df = df.copy()

        if use_tape_reading:
            # Classify volume based on price action
            # Close > Open = buying pressure
            # Close < Open = selling pressure
            df['delta'] = df.apply(
                lambda row: row['volume'] if row['close'] > row['open']
                else -row['volume'] if row['close'] < row['open']
                else 0,
                axis=1
            )
        else:
            # Use actual buy/sell volume if available
            if 'buy_volume' in df.columns and 'sell_volume' in df.columns:
                df['delta'] = df['buy_volume'] - df['sell_volume']
            else:
                logger.warning("No buy/sell volume columns found, using tape reading method")
                return self.calculate_delta(df, use_tape_reading=True)

        # Calculate cumulative delta
        df['cvd'] = df['delta'].cumsum()

        # Delta as percentage of total volume
        df['delta_percent'] = (df['delta'] / df['volume'] * 100).fillna(0)

        return df

    def detect_absorption(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect absorption - when large volume doesn't move price significantly.

        Absorption indicates strong support/resistance where institutional
        players are absorbing selling/buying pressure.

        Args:
            df: DataFrame with OHLCV and delta data

        Returns:
            DataFrame with absorption_detected column
        """
        df = df.copy()

        # Calculate price change
        df['price_change'] = df['close'].pct_change().abs()

        # Calculate volume percentile
        volume_median = df['volume'].rolling(20).median()
        df['volume_ratio'] = df['volume'] / volume_median

        # Absorption: high volume but low price movement
        df['absorption_detected'] = (
            (df['volume_ratio'] > self.absorption_threshold) &
            (df['price_change'] < df['price_change'].rolling(20).mean())
        )

        return df

    def detect_exhaustion(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect exhaustion - when delta diverges from price.

        Exhaustion signals potential reversals when:
        - Price makes new highs but CVD doesn't (bearish)
        - Price makes new lows but CVD doesn't (bullish)

        Args:
            df: DataFrame with price and CVD data

        Returns:
            DataFrame with exhaustion columns
        """
        df = df.copy()

        lookback = 20

        # Calculate rolling highs/lows
        df['price_high'] = df['high'].rolling(lookback).max()
        df['price_low'] = df['low'].rolling(lookback).min()
        df['cvd_high'] = df['cvd'].rolling(lookback).max()
        df['cvd_low'] = df['cvd'].rolling(lookback).min()

        # Bearish exhaustion: new price high, CVD not confirming
        df['bearish_exhaustion'] = (
            (df['high'] >= df['price_high']) &
            (df['cvd'] < df['cvd_high'])
        )

        # Bullish exhaustion: new price low, CVD not confirming
        df['bullish_exhaustion'] = (
            (df['low'] <= df['price_low']) &
            (df['cvd'] > df['cvd_low'])
        )

        df['exhaustion_detected'] = df['bearish_exhaustion'] | df['bullish_exhaustion']

        return df

    def detect_imbalances(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect order flow imbalances.

        Strong imbalances indicate directional conviction.

        Args:
            df: DataFrame with delta data

        Returns:
            DataFrame with imbalance metrics
        """
        df = df.copy()

        # Calculate buy/sell volume
        if 'buy_volume' not in df.columns:
            df['buy_volume'] = df.apply(
                lambda row: row['volume'] if row['close'] > row['open'] else 0,
                axis=1
            )
            df['sell_volume'] = df.apply(
                lambda row: row['volume'] if row['close'] < row['open'] else 0,
                axis=1
            )

        # Calculate imbalance ratio
        df['imbalance_ratio'] = df.apply(
            lambda row: row['buy_volume'] / row['sell_volume']
            if row['sell_volume'] > 0
            else 10.0,  # Cap at 10x
            axis=1
        )

        # Detect significant imbalances
        df['bullish_imbalance'] = df['imbalance_ratio'] > self.imbalance_threshold
        df['bearish_imbalance'] = df['imbalance_ratio'] < (1 / self.imbalance_threshold)

        return df

    def calculate_volume_profile(
        self,
        df: pd.DataFrame,
        num_bins: int = 50
    ) -> VolumeProfile:
        """
        Calculate Volume Profile for the given price range.

        Volume Profile shows price levels with most trading activity.

        Args:
            df: DataFrame with OHLCV data
            num_bins: Number of price bins to create

        Returns:
            VolumeProfile object with key levels
        """
        # Create price bins
        price_min = df['low'].min()
        price_max = df['high'].max()
        price_step = (price_max - price_min) / num_bins

        # Round prices to precision
        price_bins = [
            round(price_min + i * price_step, self.price_precision)
            for i in range(num_bins + 1)
        ]

        # Initialize volume nodes
        volume_nodes = {price: 0.0 for price in price_bins}

        # Distribute volume across price levels
        for _, row in df.iterrows():
            low, high, volume = row['low'], row['high'], row['volume']

            # Find bins this candle touches
            touching_bins = [
                price for price in price_bins
                if low <= price <= high
            ]

            if touching_bins:
                # Distribute volume evenly across touched price levels
                volume_per_bin = volume / len(touching_bins)
                for price in touching_bins:
                    volume_nodes[price] += volume_per_bin

        # Find Point of Control (POC)
        poc = max(volume_nodes.items(), key=lambda x: x[1])[0]

        # Calculate Value Area (70% of volume)
        sorted_nodes = sorted(volume_nodes.items(), key=lambda x: x[1], reverse=True)
        total_volume = sum(v for _, v in sorted_nodes)
        target_volume = total_volume * self.value_area_pct

        value_area_prices = []
        cumulative_volume = 0

        for price, vol in sorted_nodes:
            value_area_prices.append(price)
            cumulative_volume += vol
            if cumulative_volume >= target_volume:
                break

        # Value Area High and Low
        vah = max(value_area_prices)
        val = min(value_area_prices)

        # Identify high and low volume nodes
        volume_threshold_high = np.percentile(list(volume_nodes.values()), 80)
        volume_threshold_low = np.percentile(list(volume_nodes.values()), 20)

        high_volume_nodes = [
            price for price, vol in volume_nodes.items()
            if vol >= volume_threshold_high
        ]

        low_volume_nodes = [
            price for price, vol in volume_nodes.items()
            if vol <= volume_threshold_low and vol > 0
        ]

        return VolumeProfile(
            poc=poc,
            vah=vah,
            val=val,
            value_area_volume_pct=self.value_area_pct,
            volume_nodes=volume_nodes,
            high_volume_nodes=sorted(high_volume_nodes),
            low_volume_nodes=sorted(low_volume_nodes)
        )

    def analyze(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, VolumeProfile]:
        """
        Perform comprehensive order flow analysis.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Tuple of (analyzed DataFrame, VolumeProfile)
        """
        # Calculate delta
        df = self.calculate_delta(df, use_tape_reading=True)

        # Detect patterns
        df = self.detect_absorption(df)
        df = self.detect_exhaustion(df)
        df = self.detect_imbalances(df)

        # Calculate volume profile
        volume_profile = self.calculate_volume_profile(df)

        logger.info(f"Order flow analysis complete. POC: {volume_profile.poc}, "
                   f"VAH: {volume_profile.vah}, VAL: {volume_profile.val}")

        return df, volume_profile

    def get_latest_metrics(self, df: pd.DataFrame) -> OrderFlowMetrics:
        """
        Get current order flow metrics from analyzed data.

        Args:
            df: Analyzed DataFrame with order flow columns

        Returns:
            OrderFlowMetrics for the latest bar
        """
        latest = df.iloc[-1]

        return OrderFlowMetrics(
            timestamp=latest.get('timestamp', datetime.now()),
            cvd=latest['cvd'],
            delta=latest['delta'],
            delta_percent=latest['delta_percent'],
            buy_volume=latest.get('buy_volume', 0),
            sell_volume=latest.get('sell_volume', 0),
            total_volume=latest['volume'],
            absorption_detected=latest.get('absorption_detected', False),
            exhaustion_detected=latest.get('exhaustion_detected', False),
            imbalance_ratio=latest.get('imbalance_ratio', 1.0)
        )


# Example usage and testing
if __name__ == "__main__":
    # Create sample data
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='1H')

    sample_df = pd.DataFrame({
        'timestamp': dates,
        'open': 50000 + np.cumsum(np.random.randn(100) * 100),
        'high': 50000 + np.cumsum(np.random.randn(100) * 100) + 50,
        'low': 50000 + np.cumsum(np.random.randn(100) * 100) - 50,
        'close': 50000 + np.cumsum(np.random.randn(100) * 100),
        'volume': np.random.randint(100, 1000, 100)
    })

    # Ensure high >= close >= low
    sample_df['high'] = sample_df[['high', 'close']].max(axis=1)
    sample_df['low'] = sample_df[['low', 'close']].min(axis=1)

    # Analyze order flow
    analyzer = OrderFlowAnalyzer()
    analyzed_df, volume_profile = analyzer.analyze(sample_df)

    print("\n=== Order Flow Analysis ===")
    print(f"\nLatest Metrics:")
    metrics = analyzer.get_latest_metrics(analyzed_df)
    print(f"CVD: {metrics.cvd:.2f}")
    print(f"Delta: {metrics.delta:.2f}")
    print(f"Delta %: {metrics.delta_percent:.2f}%")
    print(f"Imbalance Ratio: {metrics.imbalance_ratio:.2f}")
    print(f"Absorption Detected: {metrics.absorption_detected}")
    print(f"Exhaustion Detected: {metrics.exhaustion_detected}")

    print(f"\n=== Volume Profile ===")
    print(f"POC (Point of Control): {volume_profile.poc:.2f}")
    print(f"VAH (Value Area High): {volume_profile.vah:.2f}")
    print(f"VAL (Value Area Low): {volume_profile.val:.2f}")
    print(f"High Volume Nodes: {len(volume_profile.high_volume_nodes)}")
    print(f"Low Volume Nodes: {len(volume_profile.low_volume_nodes)}")
