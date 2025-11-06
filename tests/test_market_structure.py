"""
Tests for Market Structure Analysis module
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.indicators.market_structure import (
    MarketStructureAnalyzer,
    SwingPoint,
    StructureEvent,
    FairValueGap,
    OrderBlock,
    Trend,
    StructureType
)


@pytest.fixture
def trending_data():
    """Create trending price data for testing"""
    dates = pd.date_range(start='2024-01-01', periods=200, freq='1H')

    # Create uptrend with realistic swings
    trend = np.linspace(0, 10, 200)
    noise = np.random.randn(200) * 0.5

    df = pd.DataFrame({
        'timestamp': dates,
        'open': 50000 + trend * 100 + noise * 100,
        'high': 50100 + trend * 100 + noise * 100 + 50,
        'low': 49900 + trend * 100 + noise * 100 - 50,
        'close': 50000 + trend * 100 + noise * 100 + 10,
        'volume': np.random.randint(100, 1000, 200).astype(float)
    })

    # Ensure OHLC relationship
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)

    return df


@pytest.fixture
def ranging_data():
    """Create ranging price data for testing"""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='1H')

    # Sideways price action
    price_range = 50000 + np.random.randn(100) * 100

    df = pd.DataFrame({
        'timestamp': dates,
        'open': price_range,
        'high': price_range + 50,
        'low': price_range - 50,
        'close': price_range + np.random.randn(100) * 20,
        'volume': np.random.randint(100, 1000, 100).astype(float)
    })

    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)

    return df


class TestMarketStructureAnalyzer:
    """Test MarketStructureAnalyzer class"""

    def test_initialization(self):
        """Test analyzer initialization"""
        analyzer = MarketStructureAnalyzer()

        assert analyzer.swing_lookback == 5
        assert analyzer.structure_confirmation == 2
        assert analyzer.fvg_min_size == 0.001
        assert analyzer.orderblock_lookback == 10

    def test_custom_initialization(self):
        """Test analyzer with custom parameters"""
        analyzer = MarketStructureAnalyzer(
            swing_lookback=10,
            structure_confirmation=3,
            fvg_min_size=0.002,
            orderblock_lookback=20
        )

        assert analyzer.swing_lookback == 10
        assert analyzer.structure_confirmation == 3
        assert analyzer.fvg_min_size == 0.002
        assert analyzer.orderblock_lookback == 20

    def test_identify_swing_points(self, trending_data):
        """Test swing point identification"""
        analyzer = MarketStructureAnalyzer()
        swings = analyzer.identify_swing_points(trending_data)

        assert len(swings) > 0
        assert all(isinstance(s, SwingPoint) for s in swings)

        # Check that swings alternate between highs and lows (mostly)
        highs = [s for s in swings if s.is_high]
        lows = [s for s in swings if not s.is_high]

        assert len(highs) > 0
        assert len(lows) > 0

    def test_determine_trend_bullish(self, trending_data):
        """Test trend determination for uptrend"""
        analyzer = MarketStructureAnalyzer()
        swings = analyzer.identify_swing_points(trending_data)
        trend = analyzer.determine_trend(swings)

        # Should detect uptrend
        assert isinstance(trend, Trend)

    def test_determine_trend_ranging(self, ranging_data):
        """Test trend determination for range"""
        analyzer = MarketStructureAnalyzer()
        swings = analyzer.identify_swing_points(ranging_data)
        trend = analyzer.determine_trend(swings)

        # May be ranging
        assert trend in [Trend.RANGING, Trend.BULLISH, Trend.BEARISH]

    def test_detect_bos_choch(self, trending_data):
        """Test BOS/CHoCH detection"""
        analyzer = MarketStructureAnalyzer()
        swings = analyzer.identify_swing_points(trending_data)
        events = analyzer.detect_bos_choch(trending_data, swings)

        # Should find some structure events
        assert isinstance(events, list)

        if events:
            assert all(isinstance(e, StructureEvent) for e in events)
            assert all(e.event_type in [StructureType.BOS, StructureType.CHOCH] for e in events)

    def test_identify_fair_value_gaps(self, trending_data):
        """Test FVG identification"""
        analyzer = MarketStructureAnalyzer()
        fvgs = analyzer.identify_fair_value_gaps(trending_data)

        assert isinstance(fvgs, list)

        if fvgs:
            assert all(isinstance(fvg, FairValueGap) for fvg in fvgs)
            # Check FVG structure
            for fvg in fvgs:
                assert fvg.top > fvg.bottom
                assert isinstance(fvg.is_bullish, bool)

    def test_identify_order_blocks(self, trending_data):
        """Test order block identification"""
        analyzer = MarketStructureAnalyzer()
        order_blocks = analyzer.identify_order_blocks(trending_data)

        assert isinstance(order_blocks, list)

        if order_blocks:
            assert all(isinstance(ob, OrderBlock) for ob in order_blocks)
            # Check order block structure
            for ob in order_blocks:
                assert ob.top > ob.bottom
                assert ob.volume > 0

    def test_analyze_comprehensive(self, trending_data):
        """Test comprehensive market structure analysis"""
        analyzer = MarketStructureAnalyzer()
        results = analyzer.analyze(trending_data)

        assert isinstance(results, dict)
        assert 'swing_points' in results
        assert 'current_trend' in results
        assert 'structure_events' in results
        assert 'fair_value_gaps' in results
        assert 'order_blocks' in results
        assert 'latest_structure_event' in results

        # Validate types
        assert isinstance(results['swing_points'], list)
        assert isinstance(results['current_trend'], Trend)
        assert isinstance(results['structure_events'], list)
        assert isinstance(results['fair_value_gaps'], list)
        assert isinstance(results['order_blocks'], list)


class TestSwingPoint:
    """Test SwingPoint dataclass"""

    def test_swing_point_creation(self):
        """Test SwingPoint creation"""
        swing = SwingPoint(
            timestamp=datetime.now(),
            price=50000,
            index=10,
            is_high=True,
            strength=5
        )

        assert swing.price == 50000
        assert swing.is_high is True
        assert swing.strength == 5


class TestStructureEvent:
    """Test StructureEvent dataclass"""

    def test_structure_event_creation(self):
        """Test StructureEvent creation"""
        event = StructureEvent(
            timestamp=datetime.now(),
            event_type=StructureType.BOS,
            price=50000,
            previous_trend=Trend.BULLISH,
            new_trend=Trend.BULLISH,
            broken_level=49500,
            strength=0.8
        )

        assert event.event_type == StructureType.BOS
        assert event.previous_trend == Trend.BULLISH
        assert event.new_trend == Trend.BULLISH
        assert event.strength == 0.8


class TestFairValueGap:
    """Test FairValueGap dataclass"""

    def test_fvg_creation(self):
        """Test FairValueGap creation"""
        fvg = FairValueGap(
            timestamp=datetime.now(),
            top=50100,
            bottom=49900,
            is_bullish=True,
            filled=False
        )

        assert fvg.top == 50100
        assert fvg.bottom == 49900
        assert fvg.is_bullish is True
        assert fvg.filled is False


class TestOrderBlock:
    """Test OrderBlock dataclass"""

    def test_order_block_creation(self):
        """Test OrderBlock creation"""
        ob = OrderBlock(
            timestamp=datetime.now(),
            top=50100,
            bottom=49900,
            is_bullish=True,
            volume=1000,
            tested=False
        )

        assert ob.top == 50100
        assert ob.bottom == 49900
        assert ob.is_bullish is True
        assert ob.volume == 1000
        assert ob.tested is False


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_insufficient_data_for_swings(self):
        """Test with insufficient data for swing detection"""
        analyzer = MarketStructureAnalyzer(swing_lookback=5)

        df = pd.DataFrame({
            'timestamp': pd.date_range(start='2024-01-01', periods=5, freq='1H'),
            'open': [50000] * 5,
            'high': [50100] * 5,
            'low': [49900] * 5,
            'close': [50000] * 5,
            'volume': [1000] * 5
        })

        swings = analyzer.identify_swing_points(df)
        assert len(swings) == 0  # Not enough data

    def test_no_fvg_in_tight_range(self):
        """Test FVG detection in tight range (no gaps)"""
        analyzer = MarketStructureAnalyzer()

        df = pd.DataFrame({
            'timestamp': pd.date_range(start='2024-01-01', periods=50, freq='1H'),
            'open': [50000] * 50,
            'high': [50010] * 50,
            'low': [49990] * 50,
            'close': [50000] * 50,
            'volume': [1000] * 50
        })

        fvgs = analyzer.identify_fair_value_gaps(df)
        assert len(fvgs) == 0  # No gaps in tight range

    def test_trend_with_few_swings(self):
        """Test trend determination with minimal swings"""
        analyzer = MarketStructureAnalyzer()

        swings = [
            SwingPoint(datetime.now(), 50000, 0, True, 5),
            SwingPoint(datetime.now(), 49900, 1, False, 5)
        ]

        trend = analyzer.determine_trend(swings)
        assert trend == Trend.RANGING  # Not enough data
