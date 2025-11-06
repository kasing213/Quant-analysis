"""
Tests for Order Flow Analysis module
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.indicators.order_flow import (
    OrderFlowAnalyzer,
    OrderFlowMetrics,
    VolumeProfile
)


@pytest.fixture
def sample_data():
    """Create sample OHLCV data for testing"""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='1H')

    df = pd.DataFrame({
        'timestamp': dates,
        'open': 50000 + np.cumsum(np.random.randn(100) * 100),
        'high': 50100 + np.cumsum(np.random.randn(100) * 100),
        'low': 49900 + np.cumsum(np.random.randn(100) * 100),
        'close': 50000 + np.cumsum(np.random.randn(100) * 100),
        'volume': np.random.randint(100, 1000, 100).astype(float)
    })

    # Ensure OHLC relationship
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)

    return df


class TestOrderFlowAnalyzer:
    """Test OrderFlowAnalyzer class"""

    def test_initialization(self):
        """Test analyzer initialization"""
        analyzer = OrderFlowAnalyzer()

        assert analyzer.imbalance_threshold == 1.5
        assert analyzer.absorption_threshold == 2.0
        assert analyzer.value_area_pct == 0.70
        assert analyzer.price_precision == 2

    def test_custom_initialization(self):
        """Test analyzer with custom parameters"""
        analyzer = OrderFlowAnalyzer(
            imbalance_threshold=2.0,
            absorption_threshold=3.0,
            value_area_pct=0.80,
            price_precision=4
        )

        assert analyzer.imbalance_threshold == 2.0
        assert analyzer.absorption_threshold == 3.0
        assert analyzer.value_area_pct == 0.80
        assert analyzer.price_precision == 4

    def test_calculate_delta_tape_reading(self, sample_data):
        """Test delta calculation using tape reading"""
        analyzer = OrderFlowAnalyzer()
        result = analyzer.calculate_delta(sample_data, use_tape_reading=True)

        assert 'delta' in result.columns
        assert 'cvd' in result.columns
        assert 'delta_percent' in result.columns

        # CVD should be cumulative sum of delta
        assert result['cvd'].iloc[-1] == result['delta'].sum()

    def test_detect_absorption(self, sample_data):
        """Test absorption detection"""
        analyzer = OrderFlowAnalyzer()
        df = analyzer.calculate_delta(sample_data, use_tape_reading=True)
        result = analyzer.detect_absorption(df)

        assert 'absorption_detected' in result.columns
        assert result['absorption_detected'].dtype == bool

    def test_detect_exhaustion(self, sample_data):
        """Test exhaustion detection"""
        analyzer = OrderFlowAnalyzer()
        df = analyzer.calculate_delta(sample_data, use_tape_reading=True)
        result = analyzer.detect_exhaustion(df)

        assert 'exhaustion_detected' in result.columns
        assert 'bearish_exhaustion' in result.columns
        assert 'bullish_exhaustion' in result.columns

    def test_detect_imbalances(self, sample_data):
        """Test imbalance detection"""
        analyzer = OrderFlowAnalyzer()
        result = analyzer.detect_imbalances(sample_data)

        assert 'imbalance_ratio' in result.columns
        assert 'bullish_imbalance' in result.columns
        assert 'bearish_imbalance' in result.columns

    def test_volume_profile(self, sample_data):
        """Test volume profile calculation"""
        analyzer = OrderFlowAnalyzer()
        profile = analyzer.calculate_volume_profile(sample_data, num_bins=50)

        assert isinstance(profile, VolumeProfile)
        assert profile.poc > 0
        assert profile.vah >= profile.poc
        assert profile.val <= profile.poc
        assert len(profile.volume_nodes) > 0
        assert isinstance(profile.high_volume_nodes, list)
        assert isinstance(profile.low_volume_nodes, list)

    def test_analyze_comprehensive(self, sample_data):
        """Test comprehensive analysis"""
        analyzer = OrderFlowAnalyzer()
        df, profile = analyzer.analyze(sample_data)

        # Check DataFrame columns
        assert 'delta' in df.columns
        assert 'cvd' in df.columns
        assert 'absorption_detected' in df.columns
        assert 'exhaustion_detected' in df.columns
        assert 'imbalance_ratio' in df.columns

        # Check profile
        assert isinstance(profile, VolumeProfile)
        assert profile.poc > 0

    def test_get_latest_metrics(self, sample_data):
        """Test getting latest metrics"""
        analyzer = OrderFlowAnalyzer()
        df, _ = analyzer.analyze(sample_data)
        metrics = analyzer.get_latest_metrics(df)

        assert isinstance(metrics, OrderFlowMetrics)
        assert metrics.cvd == df.iloc[-1]['cvd']
        assert metrics.delta == df.iloc[-1]['delta']
        # numpy bool is also valid
        assert isinstance(metrics.absorption_detected, (bool, np.bool_))
        assert isinstance(metrics.exhaustion_detected, (bool, np.bool_))


class TestVolumeProfile:
    """Test VolumeProfile dataclass"""

    def test_volume_profile_creation(self):
        """Test VolumeProfile creation"""
        profile = VolumeProfile(
            poc=50000,
            vah=51000,
            val=49000,
            value_area_volume_pct=0.70,
            volume_nodes={50000: 1000, 50100: 800},
            high_volume_nodes=[50000, 50100],
            low_volume_nodes=[49500, 49600]
        )

        assert profile.poc == 50000
        assert profile.vah == 51000
        assert profile.val == 49000
        assert len(profile.volume_nodes) == 2


class TestOrderFlowMetrics:
    """Test OrderFlowMetrics dataclass"""

    def test_metrics_creation(self):
        """Test OrderFlowMetrics creation"""
        metrics = OrderFlowMetrics(
            timestamp=datetime.now(),
            cvd=1000.0,
            delta=50.0,
            delta_percent=5.0,
            buy_volume=500.0,
            sell_volume=450.0,
            total_volume=1000.0,
            absorption_detected=True,
            exhaustion_detected=False,
            imbalance_ratio=1.5
        )

        assert metrics.cvd == 1000.0
        assert metrics.delta == 50.0
        assert metrics.absorption_detected is True
        assert metrics.exhaustion_detected is False


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_dataframe(self):
        """Test with empty DataFrame"""
        analyzer = OrderFlowAnalyzer()
        df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])

        # Should handle gracefully and return empty results
        result_df, profile = analyzer.analyze(df)
        assert len(result_df) == 0

    def test_single_row_dataframe(self):
        """Test with single row"""
        analyzer = OrderFlowAnalyzer()
        df = pd.DataFrame({
            'timestamp': [datetime.now()],
            'open': [50000],
            'high': [50100],
            'low': [49900],
            'close': [50050],
            'volume': [1000]
        })

        # Should handle gracefully
        result_df, profile = analyzer.analyze(df)
        assert len(result_df) == 1

    def test_zero_volume(self):
        """Test with zero volume bars"""
        df = pd.DataFrame({
            'timestamp': pd.date_range(start='2024-01-01', periods=10, freq='1H'),
            'open': [50000] * 10,
            'high': [50100] * 10,
            'low': [49900] * 10,
            'close': [50000] * 10,
            'volume': [0] * 10
        })

        analyzer = OrderFlowAnalyzer()
        result_df, profile = analyzer.analyze(df)

        # Should not crash
        assert len(result_df) == 10
