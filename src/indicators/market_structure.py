"""
Market Structure Analysis Module

Implements Smart Money Concepts (SMC) including:
- Break of Structure (BOS)
- Change of Character (CHoCH)
- Market Structure Shifts (MSS)
- Higher Highs/Lower Lows detection
- Swing points identification
- Fair Value Gaps (FVG)
- Order Blocks
- Liquidity zones
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Trend(Enum):
    """Market trend direction"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    RANGING = "ranging"


class StructureType(Enum):
    """Type of market structure event"""
    BOS = "break_of_structure"  # Continuation
    CHOCH = "change_of_character"  # Potential reversal
    MSS = "market_structure_shift"  # Confirmed reversal


@dataclass
class SwingPoint:
    """Swing high or low point"""
    timestamp: datetime
    price: float
    index: int
    is_high: bool  # True for swing high, False for swing low
    strength: int  # Number of bars to left/right that confirm this swing


@dataclass
class StructureEvent:
    """Market structure break or shift"""
    timestamp: datetime
    event_type: StructureType
    price: float
    previous_trend: Trend
    new_trend: Trend
    broken_level: float  # The level that was broken
    strength: float  # Confidence score 0-1


@dataclass
class FairValueGap:
    """Fair Value Gap (imbalance area)"""
    timestamp: datetime
    top: float
    bottom: float
    is_bullish: bool  # True for bullish FVG, False for bearish
    filled: bool = False


@dataclass
class OrderBlock:
    """Institutional order block"""
    timestamp: datetime
    top: float
    bottom: float
    is_bullish: bool
    volume: float
    tested: bool = False


class MarketStructureAnalyzer:
    """
    Analyzes market structure using Smart Money Concepts.

    Identifies key structural elements that institutional traders
    use for decision making.
    """

    def __init__(
        self,
        swing_lookback: int = 5,
        structure_confirmation: int = 2,
        fvg_min_size: float = 0.001,  # Minimum gap size as % of price
        orderblock_lookback: int = 10
    ):
        """
        Args:
            swing_lookback: Bars to look left/right for swing points
            structure_confirmation: Bars to wait before confirming structure
            fvg_min_size: Minimum FVG size as percentage
            orderblock_lookback: Lookback period for order block detection
        """
        self.swing_lookback = swing_lookback
        self.structure_confirmation = structure_confirmation
        self.fvg_min_size = fvg_min_size
        self.orderblock_lookback = orderblock_lookback

    def identify_swing_points(self, df: pd.DataFrame) -> List[SwingPoint]:
        """
        Identify swing highs and swing lows.

        A swing high has higher highs to the left and right.
        A swing low has lower lows to the left and right.

        Args:
            df: DataFrame with OHLC data

        Returns:
            List of SwingPoint objects
        """
        swing_points = []
        n = self.swing_lookback

        for i in range(n, len(df) - n):
            current_high = df.iloc[i]['high']
            current_low = df.iloc[i]['low']

            # Check for swing high
            is_swing_high = True
            for j in range(i - n, i + n + 1):
                if j != i and df.iloc[j]['high'] >= current_high:
                    is_swing_high = False
                    break

            if is_swing_high:
                swing_points.append(SwingPoint(
                    timestamp=df.iloc[i].get('timestamp', datetime.now()),
                    price=current_high,
                    index=i,
                    is_high=True,
                    strength=n
                ))

            # Check for swing low
            is_swing_low = True
            for j in range(i - n, i + n + 1):
                if j != i and df.iloc[j]['low'] <= current_low:
                    is_swing_low = False
                    break

            if is_swing_low:
                swing_points.append(SwingPoint(
                    timestamp=df.iloc[i].get('timestamp', datetime.now()),
                    price=current_low,
                    index=i,
                    is_high=False,
                    strength=n
                ))

        return sorted(swing_points, key=lambda x: x.index)

    def determine_trend(self, swing_points: List[SwingPoint]) -> Trend:
        """
        Determine current market trend based on swing points.

        Bullish: Higher highs and higher lows
        Bearish: Lower highs and lower lows
        Ranging: No clear pattern

        Args:
            swing_points: List of identified swing points

        Returns:
            Current market trend
        """
        if len(swing_points) < 4:
            return Trend.RANGING

        # Get last 4 swing points
        recent_swings = swing_points[-4:]

        highs = [s.price for s in recent_swings if s.is_high]
        lows = [s.price for s in recent_swings if not s.is_high]

        if len(highs) < 2 or len(lows) < 2:
            return Trend.RANGING

        # Check for higher highs and higher lows
        if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
            return Trend.BULLISH

        # Check for lower highs and lower lows
        if highs[-1] < highs[-2] and lows[-1] < lows[-2]:
            return Trend.BEARISH

        return Trend.RANGING

    def detect_bos_choch(
        self,
        df: pd.DataFrame,
        swing_points: List[SwingPoint]
    ) -> List[StructureEvent]:
        """
        Detect Break of Structure (BOS) and Change of Character (CHoCH).

        BOS: Price breaks structure in the direction of trend (continuation)
        CHoCH: Price breaks structure against trend (potential reversal)

        Args:
            df: DataFrame with price data
            swing_points: Identified swing points

        Returns:
            List of structure events
        """
        events = []
        current_trend = Trend.RANGING

        for i in range(len(swing_points) - 1):
            current_swing = swing_points[i]
            next_swing = swing_points[i + 1]

            # Determine if structure was broken
            if current_swing.is_high and not next_swing.is_high:
                # Check if low broke below previous swing low
                prev_lows = [s for s in swing_points[:i] if not s.is_high]
                if prev_lows and next_swing.price < min(p.price for p in prev_lows[-2:]):
                    # Structure broken to downside
                    previous_trend = current_trend

                    if current_trend == Trend.BEARISH:
                        event_type = StructureType.BOS  # Continuation
                        current_trend = Trend.BEARISH
                    else:
                        event_type = StructureType.CHOCH  # Reversal signal
                        current_trend = Trend.BEARISH

                    events.append(StructureEvent(
                        timestamp=next_swing.timestamp,
                        event_type=event_type,
                        price=next_swing.price,
                        previous_trend=previous_trend,
                        new_trend=current_trend,
                        broken_level=current_swing.price,
                        strength=0.8 if event_type == StructureType.BOS else 0.6
                    ))

            elif not current_swing.is_high and next_swing.is_high:
                # Check if high broke above previous swing high
                prev_highs = [s for s in swing_points[:i] if s.is_high]
                if prev_highs and next_swing.price > max(p.price for p in prev_highs[-2:]):
                    # Structure broken to upside
                    previous_trend = current_trend

                    if current_trend == Trend.BULLISH:
                        event_type = StructureType.BOS  # Continuation
                        current_trend = Trend.BULLISH
                    else:
                        event_type = StructureType.CHOCH  # Reversal signal
                        current_trend = Trend.BULLISH

                    events.append(StructureEvent(
                        timestamp=next_swing.timestamp,
                        event_type=event_type,
                        price=next_swing.price,
                        previous_trend=previous_trend,
                        new_trend=current_trend,
                        broken_level=current_swing.price,
                        strength=0.8 if event_type == StructureType.BOS else 0.6
                    ))

        return events

    def identify_fair_value_gaps(self, df: pd.DataFrame) -> List[FairValueGap]:
        """
        Identify Fair Value Gaps (FVG) - price imbalances.

        Bullish FVG: Gap between candle 1 high and candle 3 low
        Bearish FVG: Gap between candle 1 low and candle 3 high

        Args:
            df: DataFrame with OHLC data

        Returns:
            List of Fair Value Gaps
        """
        fvgs = []

        for i in range(2, len(df)):
            candle1 = df.iloc[i - 2]
            candle2 = df.iloc[i - 1]
            candle3 = df.iloc[i]

            # Bullish FVG: candle1.high < candle3.low
            if candle1['high'] < candle3['low']:
                gap_size = (candle3['low'] - candle1['high']) / candle1['high']

                if gap_size >= self.fvg_min_size:
                    fvgs.append(FairValueGap(
                        timestamp=candle3.get('timestamp', datetime.now()),
                        top=candle3['low'],
                        bottom=candle1['high'],
                        is_bullish=True
                    ))

            # Bearish FVG: candle1.low > candle3.high
            elif candle1['low'] > candle3['high']:
                gap_size = (candle1['low'] - candle3['high']) / candle3['high']

                if gap_size >= self.fvg_min_size:
                    fvgs.append(FairValueGap(
                        timestamp=candle3.get('timestamp', datetime.now()),
                        top=candle1['low'],
                        bottom=candle3['high'],
                        is_bullish=False
                    ))

        return fvgs

    def identify_order_blocks(self, df: pd.DataFrame) -> List[OrderBlock]:
        """
        Identify institutional order blocks.

        Order block: Last bearish/bullish candle before strong move.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            List of order blocks
        """
        order_blocks = []

        for i in range(self.orderblock_lookback, len(df) - 1):
            current = df.iloc[i]
            next_candle = df.iloc[i + 1]

            # Calculate price movement
            price_change = (next_candle['close'] - current['close']) / current['close']

            # Bullish order block: Bearish candle followed by strong bullish move
            if current['close'] < current['open'] and price_change > 0.02:  # 2% threshold
                order_blocks.append(OrderBlock(
                    timestamp=current.get('timestamp', datetime.now()),
                    top=current['open'],
                    bottom=current['close'],
                    is_bullish=True,
                    volume=current['volume']
                ))

            # Bearish order block: Bullish candle followed by strong bearish move
            elif current['close'] > current['open'] and price_change < -0.02:
                order_blocks.append(OrderBlock(
                    timestamp=current.get('timestamp', datetime.now()),
                    top=current['close'],
                    bottom=current['open'],
                    is_bullish=False,
                    volume=current['volume']
                ))

        return order_blocks

    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        Perform comprehensive market structure analysis.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Dictionary containing all structure analysis results
        """
        # Identify swing points
        swing_points = self.identify_swing_points(df)

        # Determine trend
        current_trend = self.determine_trend(swing_points)

        # Detect structure breaks
        structure_events = self.detect_bos_choch(df, swing_points)

        # Identify fair value gaps
        fvgs = self.identify_fair_value_gaps(df)

        # Identify order blocks
        order_blocks = self.identify_order_blocks(df)

        # Filter recent/relevant items
        recent_fvgs = [fvg for fvg in fvgs if not fvg.filled][-10:]  # Last 10 unfilled
        recent_order_blocks = order_blocks[-10:]  # Last 10 order blocks

        results = {
            'swing_points': swing_points,
            'current_trend': current_trend,
            'structure_events': structure_events,
            'fair_value_gaps': recent_fvgs,
            'order_blocks': recent_order_blocks,
            'latest_structure_event': structure_events[-1] if structure_events else None
        }

        logger.info(f"Market structure analysis complete. Trend: {current_trend.value}, "
                   f"Swing points: {len(swing_points)}, Events: {len(structure_events)}, "
                   f"FVGs: {len(recent_fvgs)}, Order blocks: {len(recent_order_blocks)}")

        return results


# Example usage
if __name__ == "__main__":
    # Create sample data
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=200, freq='1H')

    # Generate trending price data
    trend = np.linspace(0, 10, 200) + np.random.randn(200) * 2
    sample_df = pd.DataFrame({
        'timestamp': dates,
        'open': 50000 + trend * 100,
        'high': 50000 + trend * 100 + np.random.rand(200) * 100,
        'low': 50000 + trend * 100 - np.random.rand(200) * 100,
        'close': 50000 + trend * 100 + np.random.randn(200) * 50,
        'volume': np.random.randint(100, 1000, 200)
    })

    # Ensure OHLC relationship
    sample_df['high'] = sample_df[['open', 'high', 'close']].max(axis=1)
    sample_df['low'] = sample_df[['open', 'low', 'close']].min(axis=1)

    # Analyze market structure
    analyzer = MarketStructureAnalyzer()
    results = analyzer.analyze(sample_df)

    print("\n=== Market Structure Analysis ===")
    print(f"\nCurrent Trend: {results['current_trend'].value}")
    print(f"Swing Points Identified: {len(results['swing_points'])}")
    print(f"Structure Events: {len(results['structure_events'])}")
    print(f"Active Fair Value Gaps: {len(results['fair_value_gaps'])}")
    print(f"Recent Order Blocks: {len(results['order_blocks'])}")

    if results['latest_structure_event']:
        event = results['latest_structure_event']
        print(f"\nLatest Structure Event:")
        print(f"  Type: {event.event_type.value}")
        print(f"  Price: {event.price:.2f}")
        print(f"  Trend: {event.previous_trend.value} -> {event.new_trend.value}")
        print(f"  Strength: {event.strength:.2f}")
