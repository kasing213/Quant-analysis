"""
Fundamental Analysis Module

Provides fundamental analysis for crypto and traditional assets:
- On-chain metrics (for crypto)
- Economic calendar integration
- Sentiment analysis
- Market dominance metrics
- Macro indicators
- News impact assessment
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SentimentScore(Enum):
    """Market sentiment classification"""
    EXTREME_FEAR = 0
    FEAR = 25
    NEUTRAL = 50
    GREED = 75
    EXTREME_GREED = 100


class ImpactLevel(Enum):
    """Economic event impact level"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class OnChainMetrics:
    """Cryptocurrency on-chain metrics"""
    timestamp: datetime
    symbol: str

    # Network metrics
    active_addresses: Optional[int] = None
    transaction_count: Optional[int] = None
    hash_rate: Optional[float] = None

    # Supply metrics
    circulating_supply: Optional[float] = None
    total_supply: Optional[float] = None
    inflation_rate: Optional[float] = None

    # Holder metrics
    whale_concentration: Optional[float] = None  # % held by top addresses
    exchange_reserves: Optional[float] = None  # Coins on exchanges

    # Valuation metrics
    nvt_ratio: Optional[float] = None  # Network Value to Transactions
    mvrv_ratio: Optional[float] = None  # Market Value to Realized Value

    # Flow metrics
    exchange_inflow: Optional[float] = None
    exchange_outflow: Optional[float] = None
    net_flow: Optional[float] = None


@dataclass
class EconomicEvent:
    """Economic calendar event"""
    timestamp: datetime
    name: str
    country: str
    impact: ImpactLevel
    actual: Optional[float] = None
    forecast: Optional[float] = None
    previous: Optional[float] = None
    currency: str = "USD"


@dataclass
class SentimentMetrics:
    """Market sentiment indicators"""
    timestamp: datetime

    # Fear & Greed Index
    fear_greed_index: int  # 0-100
    sentiment_classification: SentimentScore

    # Social metrics
    twitter_sentiment: Optional[float] = None  # -1 to 1
    reddit_sentiment: Optional[float] = None
    news_sentiment: Optional[float] = None

    # Search trends
    google_trends: Optional[int] = None  # 0-100

    # Trading metrics
    funding_rate: Optional[float] = None  # Perpetual futures funding
    open_interest: Optional[float] = None
    long_short_ratio: Optional[float] = None


@dataclass
class MarketDominance:
    """Market dominance and correlation metrics"""
    timestamp: datetime

    # Dominance
    btc_dominance: float
    eth_dominance: float
    stablecoin_dominance: float

    # Total market
    total_market_cap: float
    total_volume_24h: float

    # Correlations
    btc_correlation: Optional[float] = None  # Asset correlation to BTC
    sp500_correlation: Optional[float] = None
    gold_correlation: Optional[float] = None


@dataclass
class FundamentalSignal:
    """Fundamental analysis trading signal"""
    timestamp: datetime
    signal: str  # "bullish", "bearish", "neutral"
    strength: float  # 0-1
    components: Dict[str, float]  # Individual factor scores
    reasoning: List[str]  # Human-readable reasons


class FundamentalAnalyzer:
    """
    Performs fundamental analysis combining multiple data sources.

    For crypto: on-chain metrics, sentiment, dominance
    For stocks: economic calendar, macro factors
    """

    def __init__(
        self,
        asset_type: str = "crypto",
        sentiment_weight: float = 0.3,
        onchain_weight: float = 0.4,
        macro_weight: float = 0.3
    ):
        """
        Args:
            asset_type: "crypto" or "stock"
            sentiment_weight: Weight for sentiment signals
            onchain_weight: Weight for on-chain signals (crypto only)
            macro_weight: Weight for macro/economic signals
        """
        self.asset_type = asset_type
        self.sentiment_weight = sentiment_weight
        self.onchain_weight = onchain_weight
        self.macro_weight = macro_weight

        # Normalize weights
        total_weight = sentiment_weight + onchain_weight + macro_weight
        self.sentiment_weight /= total_weight
        self.onchain_weight /= total_weight
        self.macro_weight /= total_weight

    def analyze_onchain_metrics(self, metrics: OnChainMetrics) -> Tuple[float, List[str]]:
        """
        Analyze on-chain metrics for crypto assets.

        Args:
            metrics: OnChainMetrics object

        Returns:
            Tuple of (score from -1 to 1, list of insights)
        """
        score = 0.0
        insights = []
        components_scored = 0

        # NVT Ratio analysis
        if metrics.nvt_ratio is not None:
            if metrics.nvt_ratio < 40:
                score += 1
                insights.append(f"Low NVT ratio ({metrics.nvt_ratio:.2f}) suggests undervalued")
            elif metrics.nvt_ratio > 80:
                score -= 1
                insights.append(f"High NVT ratio ({metrics.nvt_ratio:.2f}) suggests overvalued")
            components_scored += 1

        # MVRV Ratio analysis
        if metrics.mvrv_ratio is not None:
            if metrics.mvrv_ratio < 1:
                score += 1
                insights.append(f"MVRV < 1 ({metrics.mvrv_ratio:.2f}) indicates market bottom signal")
            elif metrics.mvrv_ratio > 3.5:
                score -= 1
                insights.append(f"MVRV > 3.5 ({metrics.mvrv_ratio:.2f}) indicates market top signal")
            components_scored += 1

        # Exchange flow analysis
        if metrics.net_flow is not None:
            if metrics.net_flow < 0:  # Net outflow from exchanges
                score += 0.5
                insights.append(f"Net outflow from exchanges (bullish accumulation)")
            elif metrics.net_flow > 0:
                score -= 0.5
                insights.append(f"Net inflow to exchanges (bearish distribution)")
            components_scored += 1

        # Whale concentration
        if metrics.whale_concentration is not None:
            if metrics.whale_concentration > 0.6:  # 60%+ held by whales
                score -= 0.3
                insights.append(f"High whale concentration ({metrics.whale_concentration:.1%}) - manipulation risk")
            components_scored += 1

        # Active addresses (network growth)
        if metrics.active_addresses is not None:
            # This would need historical comparison - simplified here
            insights.append(f"Active addresses: {metrics.active_addresses:,}")

        # Normalize score
        if components_scored > 0:
            score = score / components_scored
        else:
            score = 0

        return np.clip(score, -1, 1), insights

    def analyze_sentiment(self, sentiment: SentimentMetrics) -> Tuple[float, List[str]]:
        """
        Analyze market sentiment indicators.

        Args:
            sentiment: SentimentMetrics object

        Returns:
            Tuple of (score from -1 to 1, list of insights)
        """
        score = 0.0
        insights = []
        components_scored = 0

        # Fear & Greed Index (contrarian indicator)
        fg = sentiment.fear_greed_index
        if fg <= 20:
            score += 0.8  # Extreme fear = buying opportunity
            insights.append(f"Extreme fear ({fg}/100) - contrarian buy signal")
        elif fg <= 40:
            score += 0.4
            insights.append(f"Fear ({fg}/100) - accumulation zone")
        elif fg >= 80:
            score -= 0.8  # Extreme greed = take profits
            insights.append(f"Extreme greed ({fg}/100) - contrarian sell signal")
        elif fg >= 60:
            score -= 0.4
            insights.append(f"Greed ({fg}/100) - distribution zone")
        components_scored += 1

        # Funding rate (perpetual futures)
        if sentiment.funding_rate is not None:
            if sentiment.funding_rate > 0.01:  # 1% positive funding
                score -= 0.5
                insights.append(f"High positive funding ({sentiment.funding_rate:.3%}) - overleveraged longs")
            elif sentiment.funding_rate < -0.01:
                score += 0.5
                insights.append(f"Negative funding ({sentiment.funding_rate:.3%}) - overleveraged shorts")
            components_scored += 1

        # Long/Short ratio
        if sentiment.long_short_ratio is not None:
            if sentiment.long_short_ratio > 2.0:
                score -= 0.3
                insights.append(f"High long/short ratio ({sentiment.long_short_ratio:.2f}) - crowded long")
            elif sentiment.long_short_ratio < 0.5:
                score += 0.3
                insights.append(f"Low long/short ratio ({sentiment.long_short_ratio:.2f}) - crowded short")
            components_scored += 1

        # Social sentiment
        social_sentiment = np.mean([
            s for s in [sentiment.twitter_sentiment, sentiment.reddit_sentiment, sentiment.news_sentiment]
            if s is not None
        ])
        if not np.isnan(social_sentiment):
            score += social_sentiment * 0.3  # Less weight on social
            insights.append(f"Social sentiment: {social_sentiment:.2f}")
            components_scored += 1

        # Normalize
        if components_scored > 0:
            score = score / components_scored

        return np.clip(score, -1, 1), insights

    def analyze_macro_factors(
        self,
        dominance: Optional[MarketDominance] = None,
        economic_events: Optional[List[EconomicEvent]] = None
    ) -> Tuple[float, List[str]]:
        """
        Analyze macro factors and economic events.

        Args:
            dominance: Market dominance metrics
            economic_events: Upcoming/recent economic events

        Returns:
            Tuple of (score from -1 to 1, list of insights)
        """
        score = 0.0
        insights = []
        components_scored = 0

        # Market dominance analysis (crypto)
        if dominance is not None:
            # BTC dominance
            if dominance.btc_dominance > 60:
                insights.append(f"High BTC dominance ({dominance.btc_dominance:.1f}%) - altcoin weakness")
                score -= 0.2  # Bearish for alts
            elif dominance.btc_dominance < 40:
                insights.append(f"Low BTC dominance ({dominance.btc_dominance:.1f}%) - alt season")
                score += 0.2  # Bullish for alts

            # Stablecoin dominance (risk-off indicator)
            if dominance.stablecoin_dominance > 15:
                score -= 0.3
                insights.append(f"High stablecoin dominance ({dominance.stablecoin_dominance:.1f}%) - risk-off")

            components_scored += 1

        # Economic events impact
        if economic_events:
            high_impact_events = [e for e in economic_events if e.impact in [ImpactLevel.HIGH, ImpactLevel.CRITICAL]]

            if high_impact_events:
                insights.append(f"{len(high_impact_events)} high-impact events upcoming - volatility expected")
                # Analyze actual vs forecast
                for event in high_impact_events[:3]:  # Top 3 events
                    if event.actual is not None and event.forecast is not None:
                        surprise = (event.actual - event.forecast) / abs(event.forecast) if event.forecast != 0 else 0
                        if abs(surprise) > 0.1:  # 10% surprise
                            insights.append(f"{event.name}: {surprise:+.1%} surprise")
                components_scored += 1

        # Normalize
        if components_scored > 0:
            score = score / components_scored

        return np.clip(score, -1, 1), insights

    def generate_signal(
        self,
        onchain: Optional[OnChainMetrics] = None,
        sentiment: Optional[SentimentMetrics] = None,
        dominance: Optional[MarketDominance] = None,
        economic_events: Optional[List[EconomicEvent]] = None
    ) -> FundamentalSignal:
        """
        Generate comprehensive fundamental analysis signal.

        Args:
            onchain: On-chain metrics (crypto only)
            sentiment: Sentiment metrics
            dominance: Market dominance
            economic_events: Economic calendar events

        Returns:
            FundamentalSignal with combined analysis
        """
        components = {}
        all_insights = []

        # Analyze each component
        if self.asset_type == "crypto" and onchain is not None:
            onchain_score, onchain_insights = self.analyze_onchain_metrics(onchain)
            components['onchain'] = onchain_score
            all_insights.extend([f"[OnChain] {i}" for i in onchain_insights])
        else:
            onchain_score = 0

        if sentiment is not None:
            sentiment_score, sentiment_insights = self.analyze_sentiment(sentiment)
            components['sentiment'] = sentiment_score
            all_insights.extend([f"[Sentiment] {i}" for i in sentiment_insights])
        else:
            sentiment_score = 0

        macro_score, macro_insights = self.analyze_macro_factors(dominance, economic_events)
        components['macro'] = macro_score
        all_insights.extend([f"[Macro] {i}" for i in macro_insights])

        # Calculate weighted final score
        final_score = (
            onchain_score * self.onchain_weight +
            sentiment_score * self.sentiment_weight +
            macro_score * self.macro_weight
        )

        # Classify signal
        if final_score > 0.3:
            signal = "bullish"
        elif final_score < -0.3:
            signal = "bearish"
        else:
            signal = "neutral"

        # Calculate strength
        strength = abs(final_score)

        return FundamentalSignal(
            timestamp=datetime.now(),
            signal=signal,
            strength=strength,
            components=components,
            reasoning=all_insights
        )


# Example usage
if __name__ == "__main__":
    print("\n=== Fundamental Analysis Example ===\n")

    # Create sample data
    onchain = OnChainMetrics(
        timestamp=datetime.now(),
        symbol="BTC",
        active_addresses=900000,
        nvt_ratio=35.5,  # Undervalued
        mvrv_ratio=1.2,  # Moderate
        net_flow=-5000,  # Outflow from exchanges (bullish)
        whale_concentration=0.45  # 45% - acceptable
    )

    sentiment = SentimentMetrics(
        timestamp=datetime.now(),
        fear_greed_index=25,  # Fear
        sentiment_classification=SentimentScore.FEAR,
        funding_rate=0.005,  # 0.5% positive
        long_short_ratio=1.3,
        twitter_sentiment=0.2,
        reddit_sentiment=0.1,
        news_sentiment=0.15
    )

    dominance = MarketDominance(
        timestamp=datetime.now(),
        btc_dominance=52.5,
        eth_dominance=18.5,
        stablecoin_dominance=8.2,
        total_market_cap=2.5e12,
        total_volume_24h=120e9
    )

    # Run analysis
    analyzer = FundamentalAnalyzer(asset_type="crypto")
    signal = analyzer.generate_signal(
        onchain=onchain,
        sentiment=sentiment,
        dominance=dominance
    )

    print(f"Signal: {signal.signal.upper()}")
    print(f"Strength: {signal.strength:.2f}")
    print(f"\nComponent Scores:")
    for component, score in signal.components.items():
        print(f"  {component}: {score:+.2f}")

    print(f"\nReasoning:")
    for reason in signal.reasoning:
        print(f"  • {reason}")
