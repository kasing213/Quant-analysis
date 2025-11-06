# Advanced Analysis Modules

This document describes the institutional-grade analysis modules for order flow, market structure, and fundamental analysis.

## Table of Contents
- [Order Flow Analysis](#order-flow-analysis)
- [Market Structure (SMC)](#market-structure-smc)
- [Fundamental Analysis](#fundamental-analysis)
- [Integration Guide](#integration-guide)
- [Examples](#examples)

---

## Order Flow Analysis

**Module**: `src/indicators/order_flow.py`

### Overview
Order flow analysis provides deep insights into institutional buying and selling pressure by analyzing volume dynamics and price action.

### Features

#### 1. Cumulative Volume Delta (CVD)
- Tracks net buying/selling pressure over time
- Identifies accumulation and distribution phases
- Detects divergences between price and volume

#### 2. Volume Profile
- **POC (Point of Control)**: Price level with highest volume
- **VAH (Value Area High)**: Top of 70% volume concentration
- **VAL (Value Area Low)**: Bottom of 70% volume concentration
- High/Low volume nodes for support/resistance

#### 3. Pattern Detection
- **Absorption**: Large volume with minimal price movement (strong S/R)
- **Exhaustion**: Price/volume divergence (reversal signal)
- **Imbalances**: Strong directional conviction (buy/sell ratio)

### Usage

```python
from src.indicators.order_flow import OrderFlowAnalyzer
import pandas as pd

# Initialize analyzer
analyzer = OrderFlowAnalyzer(
    imbalance_threshold=1.5,      # Buy/sell ratio threshold
    absorption_threshold=2.0,      # Volume threshold for absorption
    value_area_pct=0.70,          # Value area percentage (70%)
    price_precision=2             # Decimal places for price levels
)

# Analyze market data
df, volume_profile = analyzer.analyze(ohlcv_df)

# Get current metrics
metrics = analyzer.get_latest_metrics(df)

print(f"CVD: {metrics.cvd}")
print(f"Delta: {metrics.delta}")
print(f"Absorption: {metrics.absorption_detected}")
print(f"POC: {volume_profile.poc}")
print(f"VAH: {volume_profile.vah}")
print(f"VAL: {volume_profile.val}")
```

### Key Metrics

| Metric | Description | Interpretation |
|--------|-------------|----------------|
| **CVD** | Cumulative Volume Delta | Rising = buying pressure, Falling = selling pressure |
| **Delta** | Buy volume - Sell volume | Positive = bullish, Negative = bearish |
| **Delta %** | Delta as % of total volume | Magnitude of buying/selling pressure |
| **Absorption** | High volume, low price movement | Strong support/resistance |
| **Exhaustion** | Price/CVD divergence | Potential reversal |
| **Imbalance** | Buy/sell ratio | Directional conviction |

---

## Market Structure (SMC)

**Module**: `src/indicators/market_structure.py`

### Overview
Smart Money Concepts (SMC) analysis for identifying institutional trading behavior through market structure.

### Features

#### 1. Swing Points
- Identifies swing highs and swing lows
- Customizable lookback period
- Strength rating for each swing

#### 2. Structure Events
- **BOS (Break of Structure)**: Trend continuation signal
- **CHoCH (Change of Character)**: Potential reversal signal
- **MSS (Market Structure Shift)**: Confirmed trend reversal

#### 3. Fair Value Gaps (FVG)
- Price imbalances (gaps) in the market
- Bullish and bearish FVGs
- Target zones for price reversion

#### 4. Order Blocks
- Institutional order zones
- Last candle before strong moves
- High-probability reaction zones

### Usage

```python
from src.indicators.market_structure import MarketStructureAnalyzer, Trend

# Initialize analyzer
analyzer = MarketStructureAnalyzer(
    swing_lookback=5,              # Bars for swing detection
    structure_confirmation=2,       # Confirmation bars
    fvg_min_size=0.001,           # Min FVG size (0.1%)
    orderblock_lookback=10         # Lookback for order blocks
)

# Analyze structure
results = analyzer.analyze(ohlcv_df)

# Access results
print(f"Trend: {results['current_trend'].value}")
print(f"Swing Points: {len(results['swing_points'])}")
print(f"FVGs: {len(results['fair_value_gaps'])}")
print(f"Order Blocks: {len(results['order_blocks'])}")

# Latest structure event
if results['latest_structure_event']:
    event = results['latest_structure_event']
    print(f"Event: {event.event_type.value}")
    print(f"Price: {event.price}")
    print(f"Trend: {event.new_trend.value}")
```

### Structure Events

| Event Type | Description | Signal |
|------------|-------------|--------|
| **BOS** | Break of Structure | Continuation - trend is strong |
| **CHoCH** | Change of Character | Caution - potential reversal brewing |
| **MSS** | Market Structure Shift | Reversal - trend has changed |

### Trading Zones

| Zone Type | Description | Usage |
|-----------|-------------|-------|
| **Fair Value Gap** | Price imbalance | Target for reversion |
| **Order Block** | Institutional zone | High-probability reversal area |
| **POC** | Highest volume price | Strong support/resistance |
| **VAH/VAL** | Value area bounds | Overbought/oversold zones |

---

## Fundamental Analysis

**Module**: `src/indicators/fundamental_analysis.py`

### Overview
Combines on-chain metrics, sentiment, and macro factors for comprehensive fundamental analysis.

### Features

#### 1. On-Chain Metrics (Crypto)
- **Network Activity**: Active addresses, transaction count, hash rate
- **Supply Metrics**: Circulating supply, inflation rate
- **Holder Metrics**: Whale concentration, exchange reserves
- **Valuation**: NVT ratio, MVRV ratio
- **Flow Metrics**: Exchange inflows/outflows

#### 2. Sentiment Analysis
- **Fear & Greed Index**: Contrarian indicator (0-100)
- **Funding Rates**: Perpetual futures sentiment
- **Long/Short Ratio**: Crowded positions
- **Social Sentiment**: Twitter, Reddit, news
- **Search Trends**: Google Trends analysis

#### 3. Macro Factors
- **Market Dominance**: BTC, ETH, stablecoin dominance
- **Economic Events**: High-impact calendar events
- **Correlations**: Cross-asset correlations

### Usage

```python
from src.indicators.fundamental_analysis import (
    FundamentalAnalyzer,
    OnChainMetrics,
    SentimentMetrics,
    MarketDominance
)

# Initialize analyzer
analyzer = FundamentalAnalyzer(
    asset_type="crypto",          # "crypto" or "stock"
    sentiment_weight=0.3,         # Weight for sentiment
    onchain_weight=0.4,           # Weight for on-chain
    macro_weight=0.3              # Weight for macro
)

# Create metrics
onchain = OnChainMetrics(
    timestamp=datetime.now(),
    symbol="BTC",
    nvt_ratio=35.5,               # Undervalued < 40
    mvrv_ratio=1.2,               # Market/Realized value
    net_flow=-5000,               # Outflow from exchanges
    whale_concentration=0.45      # 45% held by whales
)

sentiment = SentimentMetrics(
    timestamp=datetime.now(),
    fear_greed_index=25,          # Fear zone
    sentiment_classification=SentimentScore.FEAR,
    funding_rate=0.005,           # 0.5% positive
    long_short_ratio=1.3
)

dominance = MarketDominance(
    timestamp=datetime.now(),
    btc_dominance=52.5,
    eth_dominance=18.5,
    stablecoin_dominance=8.2,
    total_market_cap=2.5e12,
    total_volume_24h=120e9
)

# Generate signal
signal = analyzer.generate_signal(
    onchain=onchain,
    sentiment=sentiment,
    dominance=dominance
)

print(f"Signal: {signal.signal}")          # "bullish", "bearish", "neutral"
print(f"Strength: {signal.strength:.2f}")  # 0-1 confidence
print("\nComponent Scores:")
for component, score in signal.components.items():
    print(f"  {component}: {score:+.2f}")
```

### On-Chain Indicators

| Indicator | Bullish | Bearish | Description |
|-----------|---------|---------|-------------|
| **NVT Ratio** | < 40 | > 80 | Network value to transactions |
| **MVRV Ratio** | < 1.0 | > 3.5 | Market/Realized value ratio |
| **Exchange Flow** | Outflow | Inflow | Coins moving off/onto exchanges |
| **Whale Concentration** | < 40% | > 70% | Distribution among holders |

### Sentiment Indicators

| Indicator | Bullish | Bearish | Interpretation |
|-----------|---------|---------|----------------|
| **Fear & Greed** | 0-25 | 75-100 | Contrarian indicator |
| **Funding Rate** | < -0.01 | > 0.01 | Perpetual futures sentiment |
| **Long/Short Ratio** | < 0.5 | > 2.0 | Crowded positions (contrarian) |

---

## Integration Guide

### 1. Standalone Usage
Use each module independently for specific analysis:

```python
# Order Flow only
from src.indicators.order_flow import OrderFlowAnalyzer
analyzer = OrderFlowAnalyzer()
df, profile = analyzer.analyze(ohlcv_data)

# Market Structure only
from src.indicators.market_structure import MarketStructureAnalyzer
analyzer = MarketStructureAnalyzer()
results = analyzer.analyze(ohlcv_data)

# Fundamental only
from src.indicators.fundamental_analysis import FundamentalAnalyzer
analyzer = FundamentalAnalyzer()
signal = analyzer.generate_signal(onchain=metrics)
```

### 2. Combined Analysis
Combine multiple modules for comprehensive analysis:

```python
class ComprehensiveAnalyzer:
    def __init__(self):
        self.order_flow = OrderFlowAnalyzer()
        self.structure = MarketStructureAnalyzer()
        self.fundamental = FundamentalAnalyzer()

    def analyze_all(self, ohlcv_df, fundamental_data=None):
        # Technical analysis
        of_df, volume_profile = self.order_flow.analyze(ohlcv_df)
        structure_results = self.structure.analyze(ohlcv_df)

        # Fundamental analysis
        fundamental_signal = None
        if fundamental_data:
            fundamental_signal = self.fundamental.generate_signal(**fundamental_data)

        return {
            'order_flow': self.order_flow.get_latest_metrics(of_df),
            'volume_profile': volume_profile,
            'structure': structure_results,
            'fundamental': fundamental_signal
        }
```

### 3. Trading Strategy Integration
Integrate with existing trading strategies:

```python
from src.binance.strategies.base_strategy import BaseStrategy

class AdvancedStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.order_flow = OrderFlowAnalyzer()
        self.structure = MarketStructureAnalyzer()

    def should_enter_long(self, df):
        # Order flow confirmation
        of_df, profile = self.order_flow.analyze(df)
        metrics = self.order_flow.get_latest_metrics(of_df)

        # Market structure confirmation
        structure = self.structure.analyze(df)

        # Entry conditions
        conditions = [
            metrics.delta > 0,                           # Positive delta
            not metrics.exhaustion_detected,              # No exhaustion
            structure['current_trend'] == Trend.BULLISH,  # Bullish trend
            df.iloc[-1]['close'] > profile.val            # Above value area
        ]

        return all(conditions)
```

---

## Examples

### Example 1: Scalping with Order Flow

```python
# High-frequency trading using order flow
analyzer = OrderFlowAnalyzer(
    imbalance_threshold=2.0,  # Stricter threshold
    absorption_threshold=3.0
)

df, profile = analyzer.analyze(df_1min)
metrics = analyzer.get_latest_metrics(df)

# Entry: Strong imbalance at value area
if (metrics.imbalance_ratio > 2.0 and
    df.iloc[-1]['close'] near profile.val):
    enter_trade()
```

### Example 2: Swing Trading with Structure

```python
# Multi-day swing trading
analyzer = MarketStructureAnalyzer(swing_lookback=10)
results = analyzer.analyze(df_daily)

# Wait for BOS in uptrend + FVG fill
if results['latest_structure_event'].event_type == StructureType.BOS:
    # Look for FVG to fill for entry
    for fvg in results['fair_value_gaps']:
        if fvg.is_bullish and not fvg.filled:
            # Set limit order in FVG
            entry_price = (fvg.top + fvg.bottom) / 2
```

### Example 3: Position Trading with Fundamentals

```python
# Long-term position based on fundamentals
analyzer = FundamentalAnalyzer()

signal = analyzer.generate_signal(
    onchain=onchain_metrics,
    sentiment=sentiment_metrics,
    dominance=market_dominance
)

# Strong bullish fundamental signal
if signal.signal == "bullish" and signal.strength > 0.7:
    # Accumulate position over time
    DCA_buy()
```

---

## Performance Metrics

### Testing Results
- **Order Flow Tests**: 14/14 passing
- **Market Structure Tests**: 16/16 passing
- **Total Coverage**: 30 comprehensive tests
- **Edge Cases**: Handled for empty data, single rows, zero volume

### Computational Efficiency
- Order Flow: O(n) for most operations
- Market Structure: O(n²) for swing detection
- Volume Profile: O(n * bins)

### Memory Usage
- Minimal memory footprint
- Efficient pandas operations
- Lazy evaluation where possible

---

## Best Practices

### 1. Timeframe Selection
- **Scalping (1-5min)**: Use order flow heavily
- **Intraday (15min-1H)**: Combine order flow + structure
- **Swing (4H-Daily)**: Structure + fundamentals
- **Position (Weekly+)**: Fundamentals primarily

### 2. Confirmation
Never rely on a single indicator:
- ✅ Order flow confirms structure
- ✅ Structure confirms fundamentals
- ✅ Multiple timeframe alignment

### 3. Risk Management
- Use order blocks for stop placement
- VAL/VAH for position sizing
- FVGs as profit targets

### 4. Backtesting
```python
# Always backtest before live trading
from src.core.backtester import Backtester

backtester = Backtester()
results = backtester.run(
    strategy=your_advanced_strategy,
    data=historical_data
)
```

---

## API Reference

See individual module documentation:
- [`order_flow.py`](../src/indicators/order_flow.py)
- [`market_structure.py`](../src/indicators/market_structure.py)
- [`fundamental_analysis.py`](../src/indicators/fundamental_analysis.py)

---

## Support & Contributing

For issues or feature requests, see [CONTRIBUTING.md](../CONTRIBUTING.md)

**Author**: Trading System Team
**Last Updated**: 2025-10-22
**Version**: 1.0.0
