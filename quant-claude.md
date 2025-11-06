# Quantitative Trading System - Technical Documentation

**Last Updated:** 2025-10-26
**Version:** 2.0

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Alpha Generation & Low-Noise Signals](#alpha-generation--low-noise-signals)
3. [Alternative Data Sources](#alternative-data-sources)
4. [News & Sentiment Analysis](#news--sentiment-analysis)
5. [Political Events & Macro Factors](#political-events--macro-factors)
6. [Signal Filtering & Noise Reduction](#signal-filtering--noise-reduction)
7. [Multi-Source Signal Alignment](#multi-source-signal-alignment)
8. [Trading Strategies](#trading-strategies)
9. [Technical Indicators](#technical-indicators)
10. [Signal Generation](#signal-generation)
11. [Backtesting Framework](#backtesting-framework)
12. [Performance Metrics](#performance-metrics)
13. [Risk Management](#risk-management)
14. [Prediction Models](#prediction-models)
15. [Bot Trading Framework](#bot-trading-framework)
16. [API Reference](#api-reference)

---

## System Overview

This is a **production-grade quantitative trading system** built for cryptocurrency and traditional asset trading with a focus on:

- **Multi-strategy backtesting** using backtrader
- **Real-time automated trading** via Binance API
- **Advanced risk management** with drawdown guards and position sizing
- **Multiple prediction models** beyond linear regression
- **WebSocket market data streaming** for real-time signals
- **Persistent bot orchestration** with database-backed state management

### Architecture Components

```
┌─────────────────────────────────────────────────────────┐
│                  Trading Dashboard UI                    │
│              (Vanilla JS + WebSocket)                    │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│              FastAPI Backend (src/api)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Market     │  │  Portfolio   │  │    Bots      │  │
│  │   Router     │  │   Router     │  │   Router     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│          Bot Orchestrator (src/binance)                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Multiple Trading Bots (TradingBot instances)    │  │
│  │  - MA Crossover  - RSI Mean Reversion           │  │
│  │  - MACD Momentum - Bollinger Bands              │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Shared Data Manager (BinanceDataManager)        │  │
│  │  - WebSocket streaming - Redis caching          │  │
│  └──────────────────────────────────────────────────┘  │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│              Infrastructure Layer                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │  Redis   │  │Postgres  │  │ Binance  │              │
│  │  (Cache) │  │  (DB)    │  │   API    │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
```

---

## Alpha Generation & Low-Noise Signals

**Alpha** = Returns that exceed the benchmark, uncorrelated with market movements

### What is True Alpha?

In quantitative trading, **alpha** represents the excess return of an investment relative to the return of a benchmark index. True alpha is:

- ✅ **Consistent** - Works across different market regimes
- ✅ **Uncorrelated** - Not just leveraged beta (market exposure)
- ✅ **Statistically Significant** - Not random noise
- ✅ **Actionable** - Can be traded before decay
- ✅ **Low Noise** - High signal-to-noise ratio (SNR)

### Signal-to-Noise Ratio (SNR)

```python
def calculate_snr(signal_returns, benchmark_returns):
    """
    Calculate Signal-to-Noise Ratio

    SNR = Signal Power / Noise Power
    Higher SNR = Better quality signal

    Target: SNR > 2.0 for tradeable alpha
    """
    import numpy as np

    # Alpha = signal returns - beta * benchmark returns
    beta = np.cov(signal_returns, benchmark_returns)[0, 1] / np.var(benchmark_returns)
    alpha_returns = signal_returns - beta * benchmark_returns

    # Signal power = variance of alpha
    signal_power = np.var(alpha_returns)

    # Noise power = variance of residuals
    residuals = signal_returns - (alpha_returns + beta * benchmark_returns)
    noise_power = np.var(residuals)

    snr = signal_power / noise_power if noise_power > 0 else 0

    return {
        'snr': snr,
        'snr_db': 10 * np.log10(snr) if snr > 0 else -np.inf,
        'signal_power': signal_power,
        'noise_power': noise_power,
        'quality': 'excellent' if snr > 3 else 'good' if snr > 2 else 'poor'
    }

# Example usage
snr_metrics = calculate_snr(
    signal_returns=strategy_returns,
    benchmark_returns=btc_returns
)

print(f"SNR: {snr_metrics['snr']:.2f}")
print(f"SNR (dB): {snr_metrics['snr_db']:.2f}")
print(f"Quality: {snr_metrics['quality']}")
```

### Information Coefficient (IC)

Measures predictive power of signals:

```python
def calculate_information_coefficient(predictions, actuals):
    """
    IC = Correlation between predicted returns and actual returns

    IC > 0.05: Good signal
    IC > 0.10: Excellent signal
    IC < 0.02: Noise
    """
    from scipy.stats import spearmanr

    # Use Spearman (rank) correlation - more robust to outliers
    ic, p_value = spearmanr(predictions, actuals)

    return {
        'ic': ic,
        'p_value': p_value,
        'significant': p_value < 0.05,
        'quality': 'excellent' if abs(ic) > 0.10 else 'good' if abs(ic) > 0.05 else 'poor'
    }
```

### Alpha Decay Analysis

Alpha signals lose predictive power over time:

```python
def analyze_alpha_decay(signals, returns, max_days=10):
    """
    Measure how quickly alpha signal decays

    Fast decay = Need quick execution
    Slow decay = Can hold positions longer
    """
    import pandas as pd
    import numpy as np

    decay_ics = []

    for lag in range(1, max_days + 1):
        # Shift returns by lag days
        lagged_returns = returns.shift(-lag)

        # Calculate IC for this lag
        valid_mask = ~(signals.isna() | lagged_returns.isna())
        ic = signals[valid_mask].corr(lagged_returns[valid_mask])

        decay_ics.append({
            'lag_days': lag,
            'ic': ic,
            'decay_pct': (1 - ic / decay_ics[0]['ic']) * 100 if len(decay_ics) > 0 else 0
        })

    # Calculate half-life (when IC drops to 50%)
    half_life = next((d['lag_days'] for d in decay_ics if d['decay_pct'] >= 50), max_days)

    return {
        'decay_curve': pd.DataFrame(decay_ics),
        'half_life_days': half_life,
        'recommendation': 'high_frequency' if half_life <= 2 else 'day_trade' if half_life <= 5 else 'swing_trade'
    }
```

---

## Alternative Data Sources

Beyond price and volume, incorporate **alternative data** for unique alpha generation:

### 1. On-Chain Data (Crypto-Specific)

**High-Alpha Signals:**

```python
class OnChainDataFetcher:
    """
    Fetch blockchain data for crypto alpha signals

    Data Sources:
    - Glassnode API
    - CryptoQuant API
    - Whale Alert
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.glassnode.com/v1/metrics"

    async def get_exchange_flows(self, asset: str = 'BTC'):
        """
        Exchange inflows/outflows

        🔴 High inflow → Selling pressure (bearish)
        🟢 High outflow → Accumulation (bullish)
        """
        endpoint = f"{self.base_url}/transactions/transfers_volume_exchanges_net"
        params = {'a': asset, 'api_key': self.api_key}

        # Fetch data
        data = await self._fetch(endpoint, params)

        return {
            'net_flow': data['value'],
            'signal': 'SELL' if data['value'] > 0 else 'BUY',
            'confidence': min(abs(data['value']) / 1000, 1.0)  # Normalize
        }

    async def get_whale_movements(self, asset: str = 'BTC', threshold_btc: float = 100):
        """
        Track large wallet movements (whales)

        Whale accumulation → Bullish
        Whale distribution → Bearish
        """
        endpoint = f"{self.base_url}/addresses/active_count"

        # Fetch whale wallet data
        # Filter for wallets > threshold

        return {
            'whale_accumulation_score': 0.75,  # -1 to 1
            'signal': 'BUY',
            'reason': 'Whales accumulating'
        }

    async def get_miner_position_index(self, asset: str = 'BTC'):
        """
        Miner Position Index (MPI)

        MPI > 2: Miners selling → Potential top
        MPI < 0: Miners holding → Accumulation phase
        """
        endpoint = f"{self.base_url}/indicators/mpi"

        data = await self._fetch(endpoint, {'a': asset, 'api_key': self.api_key})
        mpi = data['value']

        return {
            'mpi': mpi,
            'signal': 'SELL' if mpi > 2 else 'BUY' if mpi < 0 else 'HOLD',
            'confidence': min(abs(mpi) / 3, 1.0)
        }

    async def get_nvt_signal(self, asset: str = 'BTC'):
        """
        Network Value to Transactions (NVT) Signal

        NVT > 90: Overvalued → Bearish
        NVT < 45: Undervalued → Bullish
        """
        endpoint = f"{self.base_url}/indicators/nvt_signal"

        data = await self._fetch(endpoint, {'a': asset, 'api_key': self.api_key})
        nvt = data['value']

        return {
            'nvt_signal': nvt,
            'signal': 'SELL' if nvt > 90 else 'BUY' if nvt < 45 else 'HOLD',
            'confidence': 0.8 if nvt > 90 or nvt < 45 else 0.3
        }
```

**Integration Example:**

```python
async def generate_onchain_signal(symbol: str):
    """Combine multiple on-chain indicators"""

    fetcher = OnChainDataFetcher(api_key=GLASSNODE_API_KEY)

    # Fetch all metrics
    exchange_flow = await fetcher.get_exchange_flows('BTC')
    whale_movement = await fetcher.get_whale_movements('BTC')
    mpi = await fetcher.get_miner_position_index('BTC')
    nvt = await fetcher.get_nvt_signal('BTC')

    # Weighted combination
    signals = [
        {'signal': exchange_flow['signal'], 'weight': 0.3, 'confidence': exchange_flow['confidence']},
        {'signal': whale_movement['signal'], 'weight': 0.35, 'confidence': whale_movement['confidence']},
        {'signal': mpi['signal'], 'weight': 0.20, 'confidence': mpi['confidence']},
        {'signal': nvt['signal'], 'weight': 0.15, 'confidence': nvt['confidence']},
    ]

    # Calculate weighted signal
    buy_score = sum(s['weight'] * s['confidence'] for s in signals if s['signal'] == 'BUY')
    sell_score = sum(s['weight'] * s['confidence'] for s in signals if s['signal'] == 'SELL')

    if buy_score > sell_score and buy_score > 0.5:
        return {'signal': 'BUY', 'confidence': buy_score, 'source': 'on_chain'}
    elif sell_score > buy_score and sell_score > 0.5:
        return {'signal': 'SELL', 'confidence': sell_score, 'source': 'on_chain'}
    else:
        return {'signal': 'HOLD', 'confidence': 0.0, 'source': 'on_chain'}
```

### 2. Social Media Sentiment

```python
class SocialSentimentAnalyzer:
    """
    Analyze social media for sentiment shifts

    Sources:
    - Twitter/X (crypto influencers)
    - Reddit (r/cryptocurrency, r/bitcoin)
    - Telegram groups
    - Discord servers
    """

    async def get_twitter_sentiment(self, keywords: List[str], timeframe: str = '1h'):
        """
        Twitter sentiment using API v2

        Metrics:
        - Tweet volume
        - Sentiment score (-1 to 1)
        - Influencer mentions
        - Engagement rate
        """
        import tweepy
        from textblob import TextBlob

        # Fetch tweets
        tweets = await self._fetch_tweets(keywords, timeframe)

        # Sentiment analysis
        sentiments = []
        for tweet in tweets:
            blob = TextBlob(tweet['text'])
            sentiments.append({
                'score': blob.sentiment.polarity,  # -1 to 1
                'followers': tweet['author']['followers_count'],
                'engagement': tweet['likes'] + tweet['retweets']
            })

        # Weighted by follower count and engagement
        weighted_sentiment = sum(
            s['score'] * (s['followers'] + s['engagement'])
            for s in sentiments
        ) / sum(s['followers'] + s['engagement'] for s in sentiments)

        return {
            'sentiment_score': weighted_sentiment,
            'tweet_volume': len(tweets),
            'signal': 'BUY' if weighted_sentiment > 0.3 else 'SELL' if weighted_sentiment < -0.3 else 'HOLD',
            'confidence': min(abs(weighted_sentiment) * 2, 1.0)
        }

    async def get_reddit_sentiment(self, subreddits: List[str] = ['cryptocurrency', 'bitcoin']):
        """
        Reddit sentiment from specific subreddits

        Metrics:
        - Post volume
        - Upvote ratio
        - Comment sentiment
        - Award count (strong conviction signal)
        """
        import praw
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        analyzer = SentimentIntensityAnalyzer()

        # Fetch posts
        posts = await self._fetch_reddit_posts(subreddits, limit=100)

        sentiments = []
        for post in posts:
            # Analyze title + body
            text = f"{post['title']} {post['body']}"
            scores = analyzer.polarity_scores(text)

            sentiments.append({
                'compound': scores['compound'],
                'upvote_ratio': post['upvote_ratio'],
                'awards': post['total_awards_received'],
                'comments': post['num_comments']
            })

        # Weight by engagement
        avg_sentiment = sum(
            s['compound'] * (s['upvote_ratio'] + s['awards'] * 0.1)
            for s in sentiments
        ) / len(sentiments)

        return {
            'sentiment_score': avg_sentiment,
            'post_volume': len(posts),
            'signal': 'BUY' if avg_sentiment > 0.5 else 'SELL' if avg_sentiment < -0.5 else 'HOLD',
            'confidence': min(abs(avg_sentiment), 1.0)
        }
```

### 3. Google Trends & Search Volume

```python
async def get_google_trends_signal(keywords: List[str], asset: str = 'BTC'):
    """
    Google Trends search volume as leading indicator

    Rising search interest → Retail FOMO → Potential top
    Falling search interest → Apathy → Potential bottom

    Note: Contrarian indicator for crypto
    """
    from pytrends.request import TrendReq

    pytrends = TrendReq(hl='en-US', tz=360)
    pytrends.build_payload(keywords, timeframe='now 7-d')

    data = pytrends.interest_over_time()

    # Calculate trend
    recent_avg = data.iloc[-7:].mean().mean()  # Last week average
    prev_avg = data.iloc[-14:-7].mean().mean()  # Previous week

    change_pct = (recent_avg - prev_avg) / prev_avg if prev_avg > 0 else 0

    # CONTRARIAN: High search volume = potential top
    if change_pct > 0.5:  # 50% increase in search
        return {
            'search_volume_change': change_pct,
            'signal': 'SELL',  # Contrarian
            'confidence': 0.6,
            'reason': 'Retail FOMO detected'
        }
    elif change_pct < -0.3:  # 30% decrease
        return {
            'search_volume_change': change_pct,
            'signal': 'BUY',  # Contrarian
            'confidence': 0.7,
            'reason': 'Public apathy - potential accumulation zone'
        }
    else:
        return {'signal': 'HOLD', 'confidence': 0.0}
```

---

## News & Sentiment Analysis

### 1. News Aggregation & Filtering

```python
class NewsAggregator:
    """
    Aggregate news from multiple sources

    Sources:
    - CoinDesk, CoinTelegraph (crypto)
    - Bloomberg, Reuters (macro)
    - Official announcements (SEC, CFTC)
    """

    def __init__(self):
        self.sources = {
            'crypto': ['https://api.cryptopanic.com/v1/posts/'],
            'traditional': ['https://newsapi.org/v2/everything'],
            'official': ['https://www.sec.gov/cgi-bin/browse-edgar']
        }

    async def fetch_crypto_news(self, keywords: List[str], hours: int = 24):
        """
        Fetch crypto-specific news

        Filter by:
        - Relevance to trading assets
        - Source credibility
        - Recency
        """
        import aiohttp
        from datetime import datetime, timedelta

        cutoff_time = datetime.now() - timedelta(hours=hours)

        async with aiohttp.ClientSession() as session:
            url = self.sources['crypto'][0]
            params = {
                'auth_token': CRYPTOPANIC_API_KEY,
                'currencies': 'BTC,ETH',
                'filter': 'hot'
            }

            async with session.get(url, params=params) as response:
                data = await response.json()

                articles = []
                for article in data['results']:
                    published = datetime.fromisoformat(article['published_at'].replace('Z', '+00:00'))

                    if published > cutoff_time:
                        articles.append({
                            'title': article['title'],
                            'url': article['url'],
                            'source': article['source']['title'],
                            'published': published,
                            'votes': article.get('votes', {})
                        })

                return articles

    async def fetch_regulatory_news(self):
        """
        Monitor regulatory announcements

        High impact:
        - SEC enforcement actions
        - Federal Reserve statements
        - G20 crypto regulations
        """
        # Scrape SEC website or use RSS feeds
        regulatory_keywords = [
            'cryptocurrency', 'bitcoin', 'digital asset',
            'securities', 'enforcement', 'approval', 'ETF'
        ]

        # Implementation would scrape SEC.gov
        return []
```

### 2. Advanced NLP Sentiment Analysis

```python
class AdvancedSentimentAnalyzer:
    """
    Deep learning-based sentiment analysis

    Models:
    - FinBERT (financial sentiment)
    - CryptoBERT (crypto-specific)
    - Custom-trained transformers
    """

    def __init__(self):
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        import torch

        # Load FinBERT model
        self.tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
        self.model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

    def analyze_text(self, text: str) -> Dict:
        """
        Analyze sentiment with confidence scores

        Returns:
        - positive, negative, neutral probabilities
        - dominant sentiment
        - confidence level
        """
        import torch

        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)

        sentiment_map = {0: 'negative', 1: 'neutral', 2: 'positive'}
        sentiment_idx = torch.argmax(probs).item()

        return {
            'sentiment': sentiment_map[sentiment_idx],
            'confidence': probs[0][sentiment_idx].item(),
            'probabilities': {
                'positive': probs[0][2].item(),
                'neutral': probs[0][1].item(),
                'negative': probs[0][0].item()
            }
        }

    async def analyze_news_batch(self, articles: List[Dict]) -> Dict:
        """
        Batch analyze multiple news articles

        Aggregate sentiment across all articles
        Weight by source credibility
        """
        sentiments = []

        # Source credibility weights
        credibility = {
            'Bloomberg': 1.0,
            'Reuters': 1.0,
            'CoinDesk': 0.8,
            'CoinTelegraph': 0.7,
            'Unknown': 0.5
        }

        for article in articles:
            text = f"{article['title']} {article.get('description', '')}"
            sentiment = self.analyze_text(text)

            weight = credibility.get(article.get('source', 'Unknown'), 0.5)

            sentiments.append({
                **sentiment,
                'weight': weight,
                'article': article['title']
            })

        # Weighted average
        total_weight = sum(s['weight'] for s in sentiments)

        avg_sentiment_score = sum(
            (s['probabilities']['positive'] - s['probabilities']['negative']) * s['weight']
            for s in sentiments
        ) / total_weight

        return {
            'aggregate_sentiment': avg_sentiment_score,  # -1 to 1
            'signal': 'BUY' if avg_sentiment_score > 0.3 else 'SELL' if avg_sentiment_score < -0.3 else 'HOLD',
            'confidence': min(abs(avg_sentiment_score) * 2, 1.0),
            'article_count': len(sentiments),
            'breakdown': sentiments
        }
```

### 3. Event Detection & Classification

```python
class EventDetector:
    """
    Detect and classify market-moving events

    Event Types:
    - Regulatory (SEC approval, bans)
    - Technical (hacks, network upgrades)
    - Macro (Fed rates, inflation data)
    - Corporate (Tesla buys BTC, PayPal integrates)
    """

    def __init__(self):
        self.event_patterns = {
            'regulatory_positive': ['approval', 'approved', 'ETF approved', 'legalized'],
            'regulatory_negative': ['ban', 'banned', 'crackdown', 'investigation', 'lawsuit'],
            'technical_positive': ['upgrade', 'mainnet', 'partnership', 'integration'],
            'technical_negative': ['hack', 'exploit', 'vulnerability', 'bug'],
            'macro_positive': ['rate cut', 'stimulus', 'QE', 'dovish'],
            'macro_negative': ['rate hike', 'hawkish', 'tightening', 'recession']
        }

    def detect_events(self, text: str) -> List[Dict]:
        """
        Detect events in text using pattern matching and NER
        """
        detected_events = []

        text_lower = text.lower()

        for event_type, patterns in self.event_patterns.items():
            for pattern in patterns:
                if pattern in text_lower:
                    impact = 'positive' if 'positive' in event_type else 'negative'
                    category = event_type.split('_')[0]

                    detected_events.append({
                        'event_type': event_type,
                        'category': category,
                        'impact': impact,
                        'pattern': pattern,
                        'weight': self._get_event_weight(category)
                    })

        return detected_events

    def _get_event_weight(self, category: str) -> float:
        """Event importance weights"""
        weights = {
            'regulatory': 1.0,  # Highest impact
            'macro': 0.9,
            'corporate': 0.7,
            'technical': 0.6
        }
        return weights.get(category, 0.5)

    async def generate_event_signal(self, articles: List[Dict]) -> Dict:
        """
        Generate trading signal from detected events
        """
        all_events = []

        for article in articles:
            events = self.detect_events(article['title'])
            all_events.extend(events)

        if not all_events:
            return {'signal': 'HOLD', 'confidence': 0.0, 'events': []}

        # Calculate net impact
        positive_impact = sum(e['weight'] for e in all_events if e['impact'] == 'positive')
        negative_impact = sum(e['weight'] for e in all_events if e['impact'] == 'negative')

        net_impact = positive_impact - negative_impact

        if net_impact > 0.5:
            return {
                'signal': 'BUY',
                'confidence': min(net_impact / 2, 1.0),
                'events': all_events,
                'reason': f"{len([e for e in all_events if e['impact'] == 'positive'])} positive events detected"
            }
        elif net_impact < -0.5:
            return {
                'signal': 'SELL',
                'confidence': min(abs(net_impact) / 2, 1.0),
                'events': all_events,
                'reason': f"{len([e for e in all_events if e['impact'] == 'negative'])} negative events detected"
            }
        else:
            return {'signal': 'HOLD', 'confidence': 0.0, 'events': all_events}
```

---

## Political Events & Macro Factors

### 1. Economic Calendar Integration

```python
class EconomicCalendarMonitor:
    """
    Monitor high-impact economic events

    Sources:
    - ForexFactory
    - Investing.com Economic Calendar
    - Federal Reserve announcements
    """

    async def get_upcoming_events(self, days_ahead: int = 7):
        """
        Fetch upcoming high-impact economic events

        Key Events:
        - FOMC meetings (interest rates)
        - CPI/PPI releases (inflation)
        - NFP (employment)
        - GDP reports
        - Central bank speeches
        """
        import aiohttp
        from datetime import datetime, timedelta

        # Example: Investing.com API (requires subscription)
        events = [
            {
                'date': datetime.now() + timedelta(days=2),
                'event': 'FOMC Interest Rate Decision',
                'impact': 'high',
                'forecast': '5.25%',
                'previous': '5.00%',
                'currency': 'USD'
            },
            {
                'date': datetime.now() + timedelta(days=5),
                'event': 'US CPI y/y',
                'impact': 'high',
                'forecast': '3.2%',
                'previous': '3.7%',
                'currency': 'USD'
            }
        ]

        return events

    def calculate_event_impact(self, event: Dict) -> Dict:
        """
        Estimate market impact of upcoming event

        Higher surprise = Higher volatility
        """
        if event['impact'] != 'high':
            return {'signal': 'HOLD', 'confidence': 0.0}

        # Calculate surprise factor
        if 'forecast' in event and 'previous' in event:
            forecast = float(event['forecast'].rstrip('%'))
            previous = float(event['previous'].rstrip('%'))
            surprise_potential = abs(forecast - previous) / previous

            # High surprise potential = reduce positions before event
            if surprise_potential > 0.10:  # 10% deviation
                return {
                    'signal': 'REDUCE_RISK',
                    'confidence': 0.8,
                    'reason': f"High surprise potential: {surprise_potential:.1%}",
                    'action': 'reduce_position_size',
                    'recommended_size': 0.5  # 50% of normal
                }

        return {'signal': 'HOLD', 'confidence': 0.0}
```

### 2. Political Event Tracker

```python
class PoliticalEventTracker:
    """
    Track political events affecting crypto markets

    Events:
    - Elections (US, China, EU)
    - Regulatory hearings
    - Government shutdowns
    - Geopolitical tensions
    """

    def __init__(self):
        self.event_sources = {
            'us_congress': 'https://api.congress.gov/v3/',
            'sec_calendar': 'https://www.sec.gov/news/upcoming-events',
            'gdelt': 'https://api.gdeltproject.org/api/v2/'  # Global event database
        }

    async def track_crypto_hearings(self):
        """
        Monitor Congressional hearings on cryptocurrency

        Bullish: Pro-crypto testimony, clarity on regulations
        Bearish: Hostile questioning, proposed bans
        """
        hearings = [
            {
                'date': '2024-02-15',
                'title': 'Senate Banking Committee: Digital Assets Hearing',
                'participants': ['SEC Chair', 'CFTC Chair'],
                'sentiment': 'neutral',
                'impact': 'high'
            }
        ]

        # Analyze hearing transcripts for sentiment
        for hearing in hearings:
            # Fetch transcript
            transcript = await self._fetch_transcript(hearing['title'])

            # Sentiment analysis
            sentiment_analyzer = AdvancedSentimentAnalyzer()
            sentiment = sentiment_analyzer.analyze_text(transcript)

            hearing['calculated_sentiment'] = sentiment

        return hearings

    async def monitor_elections(self, countries: List[str] = ['US', 'China', 'EU']):
        """
        Track elections and crypto policy stances

        Pro-crypto candidates winning → Bullish
        Anti-crypto majority → Bearish
        """
        elections = {
            'US_2024': {
                'date': '2024-11-05',
                'candidates': [
                    {'name': 'Candidate A', 'crypto_stance': 'supportive', 'polling': 0.48},
                    {'name': 'Candidate B', 'crypto_stance': 'hostile', 'polling': 0.52}
                ]
            }
        }

        # Calculate weighted crypto sentiment
        for election in elections.values():
            weighted_sentiment = sum(
                (1 if c['crypto_stance'] == 'supportive' else -1) * c['polling']
                for c in election['candidates']
            )

            election['crypto_sentiment'] = weighted_sentiment

        return elections

    async def track_geopolitical_risk(self):
        """
        Monitor geopolitical tensions using GDELT

        High tensions → Flight to safe havens (BTC as digital gold?)
        Stable geopolitics → Risk-on sentiment
        """
        from gdeltdoc import GdeltDoc, Filters

        # Search for conflict/tension news
        f = Filters(
            keyword=['war', 'conflict', 'sanctions', 'tension'],
            start_date='2024-01-01',
            end_date='2024-01-31'
        )

        gd = GdeltDoc()
        articles = gd.article_search(f)

        # Calculate tension score
        tension_score = len(articles) / 1000  # Normalize

        if tension_score > 0.7:  # High tension
            return {
                'signal': 'BUY_BTC',  # Bitcoin as safe haven
                'confidence': 0.6,
                'reason': 'Elevated geopolitical risk',
                'tension_score': tension_score
            }

        return {'signal': 'HOLD', 'confidence': 0.0}
```

### 3. Central Bank Policy Tracker

```python
class CentralBankMonitor:
    """
    Track central bank policies affecting crypto

    Key Factors:
    - Interest rates (inverse correlation with BTC)
    - Money supply (M2)
    - Balance sheet size
    - CBDC development
    """

    async def get_fed_policy_signal(self):
        """
        Federal Reserve policy → Crypto market impact

        Rate hikes → Bearish (higher opportunity cost)
        Rate cuts → Bullish (cheaper money)
        QE → Bullish (inflation hedge)
        QT → Bearish (liquidity drain)
        """
        import aiohttp

        # FRED API for economic data
        fred_api_key = 'YOUR_FRED_API_KEY'

        # Fetch Federal Funds Rate
        async with aiohttp.ClientSession() as session:
            url = f'https://api.stlouisfed.org/fred/series/observations'
            params = {
                'series_id': 'FEDFUNDS',
                'api_key': fred_api_key,
                'file_type': 'json',
                'sort_order': 'desc',
                'limit': 2
            }

            async with session.get(url, params=params) as response:
                data = await response.json()

                current_rate = float(data['observations'][0]['value'])
                prev_rate = float(data['observations'][1]['value'])

                rate_change = current_rate - prev_rate

        # Fetch M2 Money Supply
        m2_params = params.copy()
        m2_params['series_id'] = 'M2SL'

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=m2_params) as response:
                m2_data = await response.json()

                current_m2 = float(m2_data['observations'][0]['value'])
                prev_m2 = float(m2_data['observations'][1]['value'])

                m2_growth = (current_m2 - prev_m2) / prev_m2

        # Generate signal
        signal_score = 0

        # Rate changes (inverse correlation)
        if rate_change > 0.25:  # Rate hike
            signal_score -= 0.4
        elif rate_change < -0.25:  # Rate cut
            signal_score += 0.4

        # M2 growth (positive correlation)
        if m2_growth > 0.02:  # 2% monthly growth
            signal_score += 0.3
        elif m2_growth < -0.02:
            signal_score -= 0.3

        if signal_score > 0.3:
            return {
                'signal': 'BUY',
                'confidence': min(signal_score, 1.0),
                'reason': f"Accommodative Fed policy (rate: {rate_change:+.2f}%, M2 growth: {m2_growth:.1%})"
            }
        elif signal_score < -0.3:
            return {
                'signal': 'SELL',
                'confidence': min(abs(signal_score), 1.0),
                'reason': f"Restrictive Fed policy (rate: {rate_change:+.2f}%, M2 growth: {m2_growth:.1%})"
            }

        return {'signal': 'HOLD', 'confidence': 0.0}
```

---

## Signal Filtering & Noise Reduction

### 1. Kalman Filter for Smooth Signals

```python
class KalmanSignalFilter:
    """
    Kalman Filter for reducing noise in trading signals

    Use cases:
    - Smooth price predictions
    - Filter sentiment scores
    - Reduce false signals
    """

    def __init__(self, process_variance=1e-5, measurement_variance=1e-1):
        self.process_variance = process_variance
        self.measurement_variance = measurement_variance
        self.estimate = 0
        self.error_estimate = 1

    def update(self, measurement):
        """
        Update filter with new measurement

        Returns: Filtered (smooth) value
        """
        # Prediction
        prediction = self.estimate
        error_prediction = self.error_estimate + self.process_variance

        # Update
        kalman_gain = error_prediction / (error_prediction + self.measurement_variance)
        self.estimate = prediction + kalman_gain * (measurement - prediction)
        self.error_estimate = (1 - kalman_gain) * error_prediction

        return self.estimate

    def filter_signal_series(self, signals: List[float]) -> List[float]:
        """Apply Kalman filter to entire signal series"""
        filtered = []
        for signal in signals:
            filtered.append(self.update(signal))
        return filtered

# Example usage
raw_signals = [0.5, 0.8, 0.3, 0.9, 0.6, 0.7, 0.4]  # Noisy signals
kalman = KalmanSignalFilter()
smooth_signals = kalman.filter_signal_series(raw_signals)

print(f"Raw: {raw_signals}")
print(f"Filtered: {[f'{s:.2f}' for s in smooth_signals]}")
```

### 2. Wavelet Denoising

```python
def wavelet_denoise_signal(signal: np.ndarray, wavelet='db4', level=1):
    """
    Wavelet transform for advanced denoising

    Better than moving averages - preserves sharp edges

    Parameters:
    - wavelet: 'db4' (Daubechies), 'sym8' (Symlet), 'coif5' (Coiflet)
    - level: Decomposition level (higher = more smoothing)
    """
    import pywt

    # Decompose signal
    coeffs = pywt.wavedec(signal, wavelet, level=level)

    # Calculate threshold
    sigma = np.median(np.abs(coeffs[-1])) / 0.6745
    threshold = sigma * np.sqrt(2 * np.log(len(signal)))

    # Apply soft thresholding to detail coefficients
    coeffs[1:] = [pywt.threshold(c, threshold, mode='soft') for c in coeffs[1:]]

    # Reconstruct signal
    denoised = pywt.waverec(coeffs, wavelet)

    return denoised[:len(signal)]

# Example
noisy_prices = np.array([100, 102, 98, 101, 99, 103, 97, 104])
clean_prices = wavelet_denoise_signal(noisy_prices)
```

### 3. Statistical Significance Testing

```python
def is_signal_significant(signal_returns: np.ndarray, alpha=0.05):
    """
    Test if trading signal returns are statistically significant

    Uses t-test to check if returns are significantly different from zero

    Returns:
    - is_significant: bool
    - p_value: float
    - confidence_level: float
    """
    from scipy import stats

    # One-sample t-test (testing if mean return != 0)
    t_statistic, p_value = stats.ttest_1samp(signal_returns, 0)

    is_significant = p_value < alpha
    confidence_level = 1 - p_value

    return {
        'is_significant': is_significant,
        'p_value': p_value,
        'confidence_level': min(confidence_level, 0.99),
        't_statistic': t_statistic,
        'mean_return': np.mean(signal_returns),
        'std_return': np.std(signal_returns),
        'verdict': 'TRADEABLE' if is_significant and np.mean(signal_returns) > 0 else 'NOISE'
    }

# Example
signal_returns = np.array([0.02, 0.015, -0.01, 0.03, 0.025, 0.018, -0.005])
result = is_signal_significant(signal_returns)
print(f"Signal verdict: {result['verdict']} (p={result['p_value']:.4f})")
```

### 4. Moving Average Crossover for Signal Confirmation

```python
def confirm_signal_with_ma(signal_values: pd.Series, fast_period=3, slow_period=10):
    """
    Confirm signals using moving average crossover

    Only act on signal when:
    - Signal MA crosses above threshold (for BUY)
    - Signal MA crosses below threshold (for SELL)

    Reduces whipsaw trades
    """
    fast_ma = signal_values.rolling(window=fast_period).mean()
    slow_ma = signal_values.rolling(window=slow_period).mean()

    # Detect crossovers
    crossover = fast_ma - slow_ma

    confirmed_signals = []
    for i in range(1, len(crossover)):
        if crossover.iloc[i] > 0 and crossover.iloc[i-1] <= 0:
            confirmed_signals.append({'index': i, 'signal': 'BUY', 'confidence': 0.8})
        elif crossover.iloc[i] < 0 and crossover.iloc[i-1] >= 0:
            confirmed_signals.append({'index': i, 'signal': 'SELL', 'confidence': 0.8})
        else:
            confirmed_signals.append({'index': i, 'signal': 'HOLD', 'confidence': 0.0})

    return confirmed_signals
```

### 5. Volatility-Adjusted Signal Strength

```python
def adjust_signal_for_volatility(signal_strength: float, current_volatility: float, avg_volatility: float):
    """
    Reduce position size during high volatility periods

    High volatility = Higher risk = Smaller positions
    """
    volatility_ratio = current_volatility / avg_volatility

    if volatility_ratio > 1.5:  # 50% above average volatility
        adjusted_strength = signal_strength * 0.5  # Half position
        adjustment_reason = "high_volatility"
    elif volatility_ratio > 1.2:  # 20% above average
        adjusted_strength = signal_strength * 0.75
        adjustment_reason = "elevated_volatility"
    elif volatility_ratio < 0.7:  # Low volatility
        adjusted_strength = signal_strength * 1.2  # Increase position (capped)
        adjustment_reason = "low_volatility"
    else:
        adjusted_strength = signal_strength
        adjustment_reason = "normal_volatility"

    return {
        'original_strength': signal_strength,
        'adjusted_strength': min(adjusted_strength, 1.0),  # Cap at 100%
        'volatility_ratio': volatility_ratio,
        'adjustment_reason': adjustment_reason
    }
```

---

## Multi-Source Signal Alignment

### Combining All Signal Sources

```python
class AlphaSignalAggregator:
    """
    Master signal aggregator combining all sources:

    1. Technical indicators (40% weight)
    2. On-chain data (25% weight)
    3. News sentiment (20% weight)
    4. Social sentiment (10% weight)
    5. Macro/political (5% weight)
    """

    def __init__(self):
        self.technical_analyzer = None  # Your existing TA
        self.onchain_fetcher = OnChainDataFetcher(api_key='...')
        self.news_analyzer = AdvancedSentimentAnalyzer()
        self.social_analyzer = SocialSentimentAnalyzer()
        self.macro_monitor = CentralBankMonitor()

        self.weights = {
            'technical': 0.40,
            'onchain': 0.25,
            'news': 0.20,
            'social': 0.10,
            'macro': 0.05
        }

    async def generate_master_signal(self, symbol: str) -> Dict:
        """
        Generate final trading signal from all sources

        Returns high-confidence, low-noise alpha signal
        """
        signals = {}

        # 1. Technical Analysis
        df = await self.data_manager.get_candles(symbol, count=100)
        technical_signal = await self.analyze_technical(df)
        signals['technical'] = technical_signal

        # 2. On-Chain Data (crypto only)
        if symbol.endswith('USDT'):
            asset = symbol.replace('USDT', '')
            onchain_signal = await self.onchain_fetcher.get_exchange_flows(asset)
            signals['onchain'] = onchain_signal
        else:
            signals['onchain'] = {'signal': 'HOLD', 'confidence': 0.0}

        # 3. News Sentiment
        news_articles = await NewsAggregator().fetch_crypto_news(keywords=[symbol[:3]], hours=24)
        news_signal = await self.news_analyzer.analyze_news_batch(news_articles)
        signals['news'] = news_signal

        # 4. Social Sentiment
        social_signal = await self.social_analyzer.get_twitter_sentiment(keywords=[symbol[:3]])
        signals['social'] = social_signal

        # 5. Macro Factors
        macro_signal = await self.macro_monitor.get_fed_policy_signal()
        signals['macro'] = macro_signal

        # Aggregate with weights
        final_signal = self._aggregate_signals(signals)

        # Apply noise reduction
        final_signal = self._reduce_noise(final_signal)

        # Quality check
        final_signal = self._quality_check(final_signal)

        return final_signal

    def _aggregate_signals(self, signals: Dict) -> Dict:
        """Weighted aggregation of all signals"""

        # Convert signals to numeric scores
        signal_map = {'BUY': 1, 'HOLD': 0, 'SELL': -1}

        weighted_score = 0
        total_confidence = 0

        for source, signal_data in signals.items():
            if source not in self.weights:
                continue

            signal_value = signal_map.get(signal_data.get('signal', 'HOLD'), 0)
            confidence = signal_data.get('confidence', 0.0)
            weight = self.weights[source]

            weighted_score += signal_value * confidence * weight
            total_confidence += confidence * weight

        # Normalize
        if total_confidence > 0:
            normalized_score = weighted_score / total_confidence
        else:
            normalized_score = 0

        # Convert back to signal
        if normalized_score > 0.3:
            final_signal = 'BUY'
        elif normalized_score < -0.3:
            final_signal = 'SELL'
        else:
            final_signal = 'HOLD'

        return {
            'signal': final_signal,
            'confidence': abs(normalized_score),
            'weighted_score': normalized_score,
            'component_signals': signals,
            'alignment_score': self._calculate_alignment(signals)
        }

    def _calculate_alignment(self, signals: Dict) -> float:
        """
        Calculate how well signals align

        High alignment = All sources agree → High confidence
        Low alignment = Conflicting signals → Low confidence
        """
        signal_map = {'BUY': 1, 'HOLD': 0, 'SELL': -1}

        signal_values = [
            signal_map.get(s.get('signal', 'HOLD'), 0)
            for s in signals.values()
        ]

        # Calculate standard deviation (lower = better alignment)
        std_dev = np.std(signal_values)

        # Convert to alignment score (0 to 1)
        alignment = max(0, 1 - std_dev)

        return alignment

    def _reduce_noise(self, signal: Dict) -> Dict:
        """Apply noise reduction techniques"""

        # If alignment is low, reduce confidence
        if signal['alignment_score'] < 0.6:
            signal['confidence'] *= signal['alignment_score']
            signal['noise_reduction'] = 'low_alignment_penalty'

        # Kalman filtering on confidence scores
        # (would maintain state across calls)

        return signal

    def _quality_check(self, signal: Dict) -> Dict:
        """
        Final quality check before returning signal

        Minimum requirements:
        - Confidence > 0.5
        - At least 3 sources agreeing
        - Alignment > 0.5
        """
        component_signals = signal['component_signals']

        # Count agreeing sources
        signal_type = signal['signal']
        agreeing_sources = sum(
            1 for s in component_signals.values()
            if s.get('signal') == signal_type and s.get('confidence', 0) > 0.3
        )

        # Apply quality filters
        if signal['confidence'] < 0.5:
            signal['signal'] = 'HOLD'
            signal['quality_flag'] = 'low_confidence'
        elif agreeing_sources < 3:
            signal['signal'] = 'HOLD'
            signal['quality_flag'] = 'insufficient_agreement'
        elif signal['alignment_score'] < 0.5:
            signal['signal'] = 'HOLD'
            signal['quality_flag'] = 'low_alignment'
        else:
            signal['quality_flag'] = 'passed'

        return signal

# Usage Example
async def main():
    aggregator = AlphaSignalAggregator()

    # Generate master signal
    signal = await aggregator.generate_master_signal('BTCUSDT')

    print(f"Signal: {signal['signal']}")
    print(f"Confidence: {signal['confidence']:.2%}")
    print(f"Alignment: {signal['alignment_score']:.2%}")
    print(f"Quality: {signal['quality_flag']}")
    print(f"\nComponent Signals:")
    for source, data in signal['component_signals'].items():
        print(f"  {source}: {data['signal']} ({data.get('confidence', 0):.2%})")
```

### Signal Persistence Check

```python
def check_signal_persistence(recent_signals: List[Dict], required_persistence=3):
    """
    Only act on signals that persist for multiple periods

    Reduces false signals from temporary noise

    Parameters:
    - recent_signals: List of last N signal dictionaries
    - required_persistence: How many consecutive signals needed

    Returns: Confirmed signal or HOLD
    """
    if len(recent_signals) < required_persistence:
        return {'signal': 'HOLD', 'confidence': 0.0, 'reason': 'insufficient_history'}

    last_n = recent_signals[-required_persistence:]

    # Check if all last N signals agree
    signal_types = [s['signal'] for s in last_n]

    if len(set(signal_types)) == 1 and signal_types[0] != 'HOLD':
        # All signals agree and are not HOLD
        avg_confidence = np.mean([s['confidence'] for s in last_n])

        return {
            'signal': signal_types[0],
            'confidence': avg_confidence * 1.2,  # Boost for persistence
            'reason': f'signal_persisted_{required_persistence}_periods'
        }
    else:
        return {
            'signal': 'HOLD',
            'confidence': 0.0,
            'reason': 'inconsistent_signals'
        }
```

---

## Trading Strategies

### 1. Moving Average (MA) Crossover

**Strategy Type:** Trend Following
**Files:** `src/core/backtester.py`, `src/core/enhanced_backtester.py`

#### Signal Logic

**Entry (BUY):**
- Fast MA crosses **above** Slow MA (Golden Cross)
- Indicates bullish momentum
- Enter long position

**Exit (SELL):**
- Fast MA crosses **below** Slow MA (Death Cross)
- Indicates bearish momentum
- Close long position

#### Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `fast_period` | 10 | 5-50 | Fast MA lookback period |
| `slow_period` | 30 | 20-200 | Slow MA lookback period |
| `stop_loss` | 5% | 2-10% | Maximum loss threshold |
| `take_profit` | 15% | 5-30% | Profit target threshold |

#### Implementation

```python
class MovingAverageStrategy(bt.Strategy):
    params = (
        ('fast_period', 10),
        ('slow_period', 30),
        ('stop_loss', 0.05),
        ('take_profit', 0.15),
    )

    def __init__(self):
        self.fast_ma = bt.indicators.SMA(self.data.close, period=self.params.fast_period)
        self.slow_ma = bt.indicators.SMA(self.data.close, period=self.params.slow_period)
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)

    def next(self):
        if not self.position:
            if self.crossover > 0:  # Golden cross
                self.buy()
        elif self.crossover < 0:  # Death cross
            self.sell()
```

#### Typical Use Cases
- **Best for:** Trending markets (crypto, stocks in bull/bear runs)
- **Time frames:** 1h, 4h, 1d for crypto; 1d for stocks
- **Win rate:** 35-45% (but winners > losers)
- **Sharpe ratio:** 0.8 - 1.5 (depends on market regime)

---

### 2. RSI Mean Reversion

**Strategy Type:** Mean Reversion
**Files:** `src/core/backtester.py`

#### Signal Logic

**Entry (BUY):**
- RSI < 30 (Oversold)
- Price below lower Bollinger Band (optional confirmation)
- Market likely to bounce

**Exit (SELL):**
- RSI > 70 (Overbought)
- Price above upper Bollinger Band
- Stop-loss or take-profit hit

#### Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `rsi_period` | 14 | 7-21 | RSI calculation period |
| `rsi_oversold` | 30 | 20-35 | Oversold threshold |
| `rsi_overbought` | 70 | 65-80 | Overbought threshold |
| `stop_loss` | 3% | 2-5% | Maximum loss |
| `take_profit` | 8% | 5-15% | Profit target |

#### Advanced Features
- **Bollinger Band confirmation** for stronger signals
- **Dynamic stop-loss** adjustment
- **High win-rate** (60-70%) with smaller profit targets

---

### 3. MACD Momentum Strategy

**Strategy Type:** Momentum
**Files:** `src/core/enhanced_backtester.py`

#### Signal Logic

**Entry (BUY):**
- MACD line crosses **above** Signal line
- Volume > 1.5x average (confirmation)
- Strong momentum detected

**Exit (SELL):**
- MACD crosses **below** Signal line
- OR Stop-loss/take-profit triggered

#### Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `macd_fast` | 12 | 8-15 | Fast EMA period |
| `macd_slow` | 26 | 20-35 | Slow EMA period |
| `macd_signal` | 9 | 5-14 | Signal line period |
| `volume_threshold` | 1.5x | 1.2-2.0x | Volume confirmation multiplier |
| `stop_loss` | 6% | 3-10% | Maximum loss |
| `take_profit` | 18% | 10-30% | Profit target |

#### Volume Confirmation
- Filters false signals during low liquidity
- Higher volume = higher confidence
- Reduces whipsaw trades

---

### 4. Bollinger Bands Mean Reversion

**Strategy Type:** Volatility-based Mean Reversion
**Files:** `src/core/backtester.py`

#### Signal Logic

**Entry (BUY):**
- Price touches or breaches **lower band**
- Indicates oversold/overextended downside
- Expect reversion to mean

**Exit (SELL):**
- Price touches or breaches **upper band**
- Indicates overbought/overextended upside
- OR Stop-loss/take-profit

#### Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `period` | 20 | 15-30 | Moving average period |
| `devfactor` | 2.0 | 1.5-3.0 | Standard deviation multiplier |
| `stop_loss` | 4% | 2-6% | Maximum loss |
| `take_profit` | 10% | 5-20% | Profit target |

#### Band Width Interpretation
- **Narrow bands** = Low volatility → breakout imminent
- **Wide bands** = High volatility → trend continuation or reversal
- **Squeeze** detection → potential explosive move

---

## Technical Indicators

### Core Indicators Available

| Indicator | Type | Use Case | Implementation |
|-----------|------|----------|----------------|
| **SMA** | Trend | Moving averages, support/resistance | `bt.indicators.SMA()` |
| **EMA** | Trend | Faster response to price changes | `bt.indicators.EMA()` |
| **RSI** | Momentum | Overbought/oversold conditions | `bt.indicators.RSI()` |
| **MACD** | Momentum | Trend strength and direction | `bt.indicators.MACD()` |
| **Bollinger Bands** | Volatility | Price extremes and squeezes | `bt.indicators.BollingerBands()` |
| **ATR** | Volatility | Stop-loss placement | `bt.indicators.ATR()` |
| **Stochastic** | Momentum | Overbought/oversold (similar to RSI) | `bt.indicators.Stochastic()` |
| **Volume** | Volume | Confirm price movements | `self.data.volume` |

### Custom Indicator Creation

```python
class CustomIndicator(bt.Indicator):
    lines = ('custom_line',)
    params = (('period', 14),)

    def __init__(self):
        self.lines.custom_line = bt.indicators.SMA(self.data.close, period=self.params.period)
```

---

## Signal Generation

### Signal Types

```python
class SignalType(Enum):
    BUY = "BUY"      # Enter long position
    SELL = "SELL"    # Exit long position (or enter short)
    HOLD = "HOLD"    # No action
```

### Signal Structure

Every strategy returns a signal dictionary:

```python
{
    'signal': SignalType.BUY,        # BUY, SELL, or HOLD
    'confidence': 0.85,               # 0.0 to 1.0
    'reason': 'Golden cross + volume spike',
    'entry_price': 45000.0,           # Recommended entry
    'stop_loss': 42750.0,             # Suggested stop-loss
    'take_profit': 49500.0,           # Suggested take-profit
    'position_size': 0.05,            # Fraction of capital
    'indicators': {                    # Supporting data
        'rsi': 65,
        'macd': 120,
        'volume_ratio': 1.8
    }
}
```

### Multi-Indicator Confluence

**Best practice:** Combine multiple signals for higher confidence

```python
# Example: MA Crossover + RSI confirmation
if golden_cross and rsi < 60:  # Not overbought
    confidence = 0.9
elif golden_cross and rsi > 60:
    confidence = 0.6  # Lower confidence
else:
    confidence = 0.0
```

---

## Backtesting Framework

### Quick Start

```python
from src.core.backtester import PortfolioBacktester, MovingAverageStrategy

# Initialize backtester
backtester = PortfolioBacktester(
    initial_cash=100000,
    commission=0.001  # 0.1% per trade
)

# Run backtest
result = backtester.run_backtest(
    symbol='BTCUSDT',
    strategy_class=MovingAverageStrategy,
    strategy_params={'fast_period': 10, 'slow_period': 30},
    start_date='2023-01-01',
    end_date='2024-01-01'
)

# Get metrics
metrics = result.get_performance_metrics()
print(metrics)
```

### Strategy Comparison

```python
# Compare multiple strategies
strategies = [
    (MovingAverageStrategy, {'fast_period': 10, 'slow_period': 30}),
    (MovingAverageStrategy, {'fast_period': 5, 'slow_period': 20}),
    (RSIMeanReversionStrategy, {}),
    (BollingerBandsStrategy, {}),
]

comparison_df = backtester.run_strategy_comparison(
    symbol='BTCUSDT',
    strategies=strategies,
    start_date='2023-01-01',
    end_date='2024-01-01'
)

# Results as DataFrame
print(comparison_df[['Strategy', 'Total Return', 'Sharpe Ratio', 'Max Drawdown %', 'Win Rate %']])
```

### Analyzers Available

| Analyzer | Provides | Key Metrics |
|----------|----------|-------------|
| **SharpeRatio** | Risk-adjusted returns | Sharpe ratio (returns/volatility) |
| **DrawDown** | Maximum decline | Max DD%, DD duration |
| **Returns** | Return statistics | Total, average, annualized |
| **TradeAnalyzer** | Trade statistics | Win rate, avg win/loss, total trades |
| **SQN** | System Quality Number | Strategy robustness score |
| **TimeReturn** | Time-series returns | Daily/monthly returns |

---

## Performance Metrics

### Alpha and Beta

**Alpha (α):** Excess return over benchmark
**Beta (β):** Sensitivity to market movements

```python
def calculate_alpha_beta(strategy_returns, benchmark_returns):
    """
    Calculate alpha and beta using linear regression

    Returns = α + β * Market_Returns + ε
    """
    import numpy as np
    from scipy import stats

    # Linear regression: strategy_returns = alpha + beta * benchmark_returns
    slope, intercept, r_value, p_value, std_err = stats.linregress(
        benchmark_returns,
        strategy_returns
    )

    beta = slope
    alpha = intercept

    return {
        'alpha': alpha,
        'beta': beta,
        'r_squared': r_value ** 2,
        'correlation': r_value
    }

# Example usage
alpha_beta = calculate_alpha_beta(
    strategy_returns=bot.get_returns(),
    benchmark_returns=sp500_returns
)
# Output: {'alpha': 0.015, 'beta': 1.2, 'r_squared': 0.68, 'correlation': 0.82}
```

### Key Metrics Explained

| Metric | Formula | Good Value | Interpretation |
|--------|---------|------------|----------------|
| **Total Return** | `(Final - Initial) / Initial * 100` | >10% annually | Overall profit/loss |
| **Sharpe Ratio** | `(Return - RiskFree) / StdDev` | >1.0 | Risk-adjusted returns |
| **Sortino Ratio** | `(Return - RiskFree) / DownsideStdDev` | >1.5 | Downside risk-adjusted returns |
| **Max Drawdown** | `Max((Peak - Trough) / Peak)` | <20% | Worst decline from peak |
| **Win Rate** | `Winning Trades / Total Trades` | >50% | Percentage of profitable trades |
| **Profit Factor** | `Gross Profit / Gross Loss` | >1.5 | Profitability ratio |
| **Alpha** | `Strategy Return - (β * Market Return)` | >0 | Excess return vs market |
| **Beta** | `Cov(Strategy, Market) / Var(Market)` | 0.8-1.2 | Market sensitivity |

### Information Ratio

```python
def calculate_information_ratio(strategy_returns, benchmark_returns):
    """
    Measures consistency of excess returns over benchmark
    IR = (Portfolio Return - Benchmark Return) / Tracking Error
    """
    excess_returns = strategy_returns - benchmark_returns
    tracking_error = np.std(excess_returns)

    if tracking_error == 0:
        return 0

    information_ratio = np.mean(excess_returns) / tracking_error
    return information_ratio
```

---

## Risk Management

### Position Sizing

**Files:** `src/binance/trading_bot.py`

```python
class TradingBot:
    def __init__(
        self,
        capital: float = 1000.0,
        risk_per_trade: float = 0.02,      # 2% risk per trade
        max_position_size: float = 0.10,   # 10% max capital per position
        ...
    )
```

#### Kelly Criterion (Advanced)

```python
def kelly_position_size(win_rate, avg_win, avg_loss):
    """
    Optimal position sizing based on edge

    Kelly% = (Win_Rate * Avg_Win - (1 - Win_Rate) * Avg_Loss) / Avg_Win
    """
    if avg_win <= 0:
        return 0

    kelly_pct = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win

    # Use fractional Kelly (1/2 or 1/4) for safety
    return max(0, min(kelly_pct * 0.5, 0.25))  # Cap at 25%
```

### Stop-Loss Strategies

#### 1. Fixed Percentage Stop-Loss

```python
stop_loss_price = entry_price * (1 - stop_loss_pct)  # e.g., 5% below entry
```

#### 2. ATR-Based Stop-Loss

```python
def atr_stop_loss(entry_price, atr_value, multiplier=2.0):
    """
    Dynamic stop-loss based on Average True Range
    More volatile assets get wider stops
    """
    return entry_price - (atr_value * multiplier)
```

#### 3. Trailing Stop-Loss

```python
class Position:
    def update_trailing_stop(self, current_price: float) -> Optional[float]:
        """
        Move stop-loss up as price increases (for long positions)
        Locks in profits while allowing upside
        """
        if self.side == 'BUY':
            self.highest_price = max(self.highest_price, current_price)
            trailing_price = self.highest_price * (1 - self.trailing_stop_pct)

            if trailing_price > self.stop_loss:
                self.stop_loss = trailing_price
                return trailing_price

        return self.stop_loss
```

### Drawdown Guard

```python
def _update_drawdown(self, unrealized_pnl: float = 0.0):
    """
    Halt trading if drawdown exceeds threshold
    Protects capital during unfavorable market conditions
    """
    equity = self.capital + self.total_pnl + unrealized_pnl
    self.peak_equity = max(self.peak_equity, equity)

    drawdown_pct = (self.peak_equity - equity) / self.peak_equity

    if drawdown_pct >= self.drawdown_guard_pct:  # e.g., 15%
        self.trading_halted = True
        self.halt_reason = f"Drawdown limit exceeded: {drawdown_pct:.2%}"
```

### Risk-Reward Ratio

```python
def validate_trade_setup(entry, stop_loss, take_profit):
    """
    Ensure risk-reward ratio meets minimum threshold

    Recommended: R:R >= 2:1 (risk $1 to make $2)
    """
    risk = abs(entry - stop_loss)
    reward = abs(take_profit - entry)

    risk_reward_ratio = reward / risk if risk > 0 else 0

    if risk_reward_ratio < 2.0:
        return False, f"R:R too low: {risk_reward_ratio:.2f}"

    return True, f"R:R acceptable: {risk_reward_ratio:.2f}"
```

---

## Prediction Models

### 1. Linear Regression (Baseline)

```python
from sklearn.linear_model import LinearRegression
import numpy as np

def linear_regression_prediction(prices, lookback=30, forecast_days=5):
    """
    Simple linear trend prediction
    Good for: Trending markets
    """
    X = np.arange(lookback).reshape(-1, 1)
    y = prices[-lookback:]

    model = LinearRegression()
    model.fit(X, y)

    # Forecast future prices
    future_X = np.arange(lookback, lookback + forecast_days).reshape(-1, 1)
    predictions = model.predict(future_X)

    return {
        'predictions': predictions,
        'slope': model.coef_[0],
        'intercept': model.intercept_,
        'trend': 'bullish' if model.coef_[0] > 0 else 'bearish'
    }
```

**Limitations:**
- Assumes linear relationship
- Poor for ranging/volatile markets
- No consideration of non-linear patterns

---

### 2. Polynomial Regression

```python
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline

def polynomial_regression_prediction(prices, lookback=30, degree=3, forecast_days=5):
    """
    Captures non-linear trends
    Good for: Curved price patterns, parabolic moves
    """
    X = np.arange(lookback).reshape(-1, 1)
    y = prices[-lookback:]

    # Create polynomial features
    model = make_pipeline(
        PolynomialFeatures(degree=degree),
        LinearRegression()
    )
    model.fit(X, y)

    # Forecast
    future_X = np.arange(lookback, lookback + forecast_days).reshape(-1, 1)
    predictions = model.predict(future_X)

    return {
        'predictions': predictions,
        'degree': degree,
        'last_price': prices[-1],
        'predicted_change': (predictions[-1] - prices[-1]) / prices[-1]
    }
```

**Advantages:**
- Captures curves and acceleration
- Better for momentum markets
- Flexible with degree parameter

**Watch out for:**
- Overfitting with high degrees
- Poor extrapolation beyond training data

---

### 3. ARIMA (AutoRegressive Integrated Moving Average)

```python
from statsmodels.tsa.arima.model import ARIMA

def arima_prediction(prices, order=(5, 1, 0), forecast_days=5):
    """
    Time series forecasting model
    Good for: Capturing autocorrelation and trends

    Parameters:
    - p: AutoRegressive order (past values)
    - d: Differencing order (stationarity)
    - q: Moving Average order (past errors)
    """
    model = ARIMA(prices, order=order)
    fitted_model = model.fit()

    # Forecast
    forecast = fitted_model.forecast(steps=forecast_days)

    return {
        'predictions': forecast,
        'aic': fitted_model.aic,  # Model quality metric
        'bic': fitted_model.bic,
        'confidence_interval': fitted_model.get_forecast(steps=forecast_days).conf_int()
    }
```

**Use cases:**
- Strong trend identification
- Seasonality detection
- Confidence intervals for predictions

---

### 4. Random Forest Regression

```python
from sklearn.ensemble import RandomForestRegressor
import numpy as np

def random_forest_prediction(df, lookback=30, forecast_days=5):
    """
    Machine learning ensemble method
    Good for: Complex patterns, multiple features

    Features used:
    - Past N prices
    - RSI, MACD, Volume
    - Price changes
    """
    from sklearn.preprocessing import StandardScaler

    # Feature engineering
    features = []
    targets = []

    for i in range(lookback, len(df) - forecast_days):
        # Features: past prices, RSI, MACD, volume
        feature_vector = [
            *df['close'].iloc[i-lookback:i].values,
            df['rsi'].iloc[i],
            df['macd'].iloc[i],
            df['volume'].iloc[i] / df['volume'].iloc[i-10:i].mean()
        ]
        features.append(feature_vector)

        # Target: price N days ahead
        targets.append(df['close'].iloc[i + forecast_days])

    X = np.array(features)
    y = np.array(targets)

    # Train model
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        random_state=42
    )
    model.fit(X_scaled, y)

    # Predict
    last_features = [
        *df['close'].iloc[-lookback:].values,
        df['rsi'].iloc[-1],
        df['macd'].iloc[-1],
        df['volume'].iloc[-1] / df['volume'].iloc[-10:].mean()
    ]

    prediction = model.predict(scaler.transform([last_features]))[0]

    return {
        'prediction': prediction,
        'feature_importance': dict(zip(
            ['price_history', 'rsi', 'macd', 'volume_ratio'],
            model.feature_importances_
        )),
        'model_score': model.score(X_scaled, y)
    }
```

**Advantages:**
- Handles non-linear relationships
- Multiple feature integration
- Feature importance analysis
- Robust to overfitting

---

### 5. LSTM (Long Short-Term Memory Neural Network)

```python
import torch
import torch.nn as nn
import numpy as np

class LSTMPricePredictor(nn.Module):
    def __init__(self, input_size=1, hidden_size=50, num_layers=2, output_size=1):
        super(LSTMPricePredictor, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size)

        out, _ = self.lstm(x, (h0, c0))
        out = self.fc(out[:, -1, :])
        return out

def lstm_prediction(prices, lookback=60, forecast_days=5, epochs=100):
    """
    Deep learning time series prediction
    Good for: Complex patterns, long-term dependencies

    Captures:
    - Long-term trends
    - Non-linear patterns
    - Temporal dependencies
    """
    from sklearn.preprocessing import MinMaxScaler

    # Normalize data
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_prices = scaler.fit_transform(prices.reshape(-1, 1))

    # Create sequences
    X, y = [], []
    for i in range(lookback, len(scaled_prices) - forecast_days):
        X.append(scaled_prices[i-lookback:i, 0])
        y.append(scaled_prices[i + forecast_days - 1, 0])

    X = np.array(X).reshape(-1, lookback, 1)
    y = np.array(y).reshape(-1, 1)

    # Convert to tensors
    X_tensor = torch.FloatTensor(X)
    y_tensor = torch.FloatTensor(y)

    # Train model
    model = LSTMPricePredictor()
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    for epoch in range(epochs):
        output = model(X_tensor)
        loss = criterion(output, y_tensor)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    # Predict
    last_sequence = scaled_prices[-lookback:].reshape(1, lookback, 1)
    prediction_scaled = model(torch.FloatTensor(last_sequence)).detach().numpy()
    prediction = scaler.inverse_transform(prediction_scaled)[0][0]

    return {
        'prediction': prediction,
        'confidence': 1 - loss.item(),  # Inverse of loss as confidence proxy
        'model': model,
        'scaler': scaler
    }
```

**Best for:**
- Cryptocurrency high-frequency data
- Capturing complex temporal patterns
- Multi-step ahead forecasting

---

### 6. Ensemble Prediction (Recommended)

```python
def ensemble_prediction(prices, df, lookback=30, forecast_days=5):
    """
    Combine multiple models for robust predictions
    Reduces individual model bias
    """
    # Get predictions from all models
    linear_pred = linear_regression_prediction(prices, lookback, forecast_days)
    poly_pred = polynomial_regression_prediction(prices, lookback, degree=3, forecast_days=forecast_days)
    arima_pred = arima_prediction(prices, order=(5, 1, 0), forecast_days=forecast_days)
    rf_pred = random_forest_prediction(df, lookback, forecast_days)
    lstm_pred = lstm_prediction(prices, lookback, forecast_days)

    # Weighted average (adjust weights based on model performance)
    weights = {
        'linear': 0.10,
        'polynomial': 0.15,
        'arima': 0.25,
        'random_forest': 0.30,
        'lstm': 0.20
    }

    ensemble_prediction = (
        weights['linear'] * linear_pred['predictions'][-1] +
        weights['polynomial'] * poly_pred['predictions'][-1] +
        weights['arima'] * arima_pred['predictions'][-1] +
        weights['random_forest'] * rf_pred['prediction'] +
        weights['lstm'] * lstm_pred['prediction']
    )

    # Calculate prediction agreement (confidence)
    predictions = [
        linear_pred['predictions'][-1],
        poly_pred['predictions'][-1],
        arima_pred['predictions'][-1],
        rf_pred['prediction'],
        lstm_pred['prediction']
    ]

    std_dev = np.std(predictions)
    confidence = 1 / (1 + std_dev / np.mean(predictions))  # Lower variance = higher confidence

    return {
        'ensemble_prediction': ensemble_prediction,
        'confidence': confidence,
        'individual_predictions': {
            'linear': linear_pred['predictions'][-1],
            'polynomial': poly_pred['predictions'][-1],
            'arima': arima_pred['predictions'][-1],
            'random_forest': rf_pred['prediction'],
            'lstm': lstm_pred['prediction']
        },
        'prediction_variance': std_dev
    }
```

---

## Bot Trading Framework

### Bot Lifecycle

```python
from src.binance import BotOrchestrator, TradingBot, TradingStrategy

# 1. Initialize orchestrator
orchestrator = BotOrchestrator(
    api_key="your_api_key",
    api_secret="your_api_secret",
    redis_host="localhost",
    redis_port=6379,
    testnet=True,  # Use testnet for paper trading
    test_mode=True,  # Simulate trades without executing
    enable_persistence=True  # Save bot state to database
)

await orchestrator.initialize()

# 2. Create custom strategy
class MyCustomStrategy(TradingStrategy):
    def __init__(self):
        super().__init__(name="My Custom MA Strategy")
        self.fast_period = 10
        self.slow_period = 30

    async def analyze(self, df: pd.DataFrame, symbol: str) -> Dict:
        # Calculate indicators
        df['fast_ma'] = df['close'].rolling(window=self.fast_period).mean()
        df['slow_ma'] = df['close'].rolling(window=self.slow_period).mean()

        # Generate signal
        if df['fast_ma'].iloc[-1] > df['slow_ma'].iloc[-1]:
            if df['fast_ma'].iloc[-2] <= df['slow_ma'].iloc[-2]:
                return {
                    'signal': SignalType.BUY,
                    'confidence': 0.85,
                    'reason': 'Golden cross detected'
                }
        elif df['fast_ma'].iloc[-1] < df['slow_ma'].iloc[-1]:
            return {
                'signal': SignalType.SELL,
                'confidence': 0.80,
                'reason': 'Death cross detected'
            }

        return {'signal': SignalType.HOLD, 'confidence': 0.5, 'reason': 'No clear signal'}

    def get_parameters(self) -> Dict:
        return {'fast_period': self.fast_period, 'slow_period': self.slow_period}

# 3. Create and start bot
bot = await orchestrator.create_bot(
    bot_id="btc_ma_bot_001",
    symbol="BTCUSDT",
    strategy=MyCustomStrategy(),
    capital=10000.0,
    risk_per_trade=0.02,  # 2% risk per trade
    max_position_size=0.10,  # 10% max capital per position
    trailing_stop_pct=0.02,  # 2% trailing stop
    drawdown_guard_pct=0.15,  # Halt at 15% drawdown
    auto_start=True
)

# 4. Monitor performance
performance = bot.get_performance()
print(f"Total P&L: ${performance['total_pnl']}")
print(f"Win Rate: {performance['win_rate']:.2%}")
print(f"Current Drawdown: {performance['current_drawdown_pct']:.2%}")

# 5. Stop bot
await orchestrator.stop_bot("btc_ma_bot_001")
```

### Position Management

```python
class Position:
    """
    Represents an open trading position

    Features:
    - Entry/exit tracking
    - P&L calculation
    - Trailing stop management
    - Risk metrics
    """

    def __init__(
        self,
        symbol: str,
        side: str,  # 'BUY' or 'SELL'
        quantity: float,
        entry_price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trailing_stop_pct: Optional[float] = None
    )
```

**Methods:**
- `calculate_pnl(current_price)` - Calculate unrealized P&L
- `update_trailing_stop(current_price)` - Adjust trailing stop
- `close(exit_price)` - Close position and realize P&L
- `to_dict()` - Serialize to dictionary

---

## API Reference

### REST Endpoints

#### Market Data

```http
GET /api/v1/market/symbols
Response: {
    "symbols": ["BTCUSDT", "ETHUSDT", ...],
    "default_interval": "1m"
}

GET /api/v1/market/price/{symbol}
Response: {
    "symbol": "BTCUSDT",
    "price": 45000.50,
    "timestamp": "2024-01-15T10:30:00Z"
}

GET /api/v1/market/candles/{symbol}?interval=1h&limit=100
Response: {
    "symbol": "BTCUSDT",
    "interval": "1h",
    "candles": [
        {
            "timestamp": "2024-01-15T10:00:00Z",
            "open": 45000,
            "high": 45500,
            "low": 44800,
            "close": 45200,
            "volume": 1234.56
        },
        ...
    ]
}
```

#### Portfolio

```http
GET /api/v1/portfolio/summary
Response: {
    "total_value": 105000.00,
    "cash": 50000.00,
    "positions_value": 55000.00,
    "total_pnl": 5000.00,
    "return_pct": 5.0
}

GET /api/v1/portfolio/positions
Response: {
    "positions": [
        {
            "symbol": "BTCUSDT",
            "quantity": 1.2,
            "entry_price": 45000,
            "current_price": 46000,
            "pnl": 1200.00,
            "pnl_pct": 2.67
        },
        ...
    ]
}
```

#### Bots

```http
GET /api/v1/bots
Response: {
    "bots": [
        {
            "bot_id": "btc_ma_bot_001",
            "symbol": "BTCUSDT",
            "strategy": "MovingAverageCrossover",
            "status": "running",
            "capital": 10000,
            "pnl": 250.50,
            "trades": 15
        },
        ...
    ]
}

POST /api/v1/bots
Body: {
    "bot_id": "eth_rsi_bot",
    "symbol": "ETHUSDT",
    "strategy": "RSIMeanReversion",
    "capital": 5000,
    "risk_per_trade": 0.02
}

GET /api/v1/bots/{bot_id}/performance
Response: {
    "bot_id": "btc_ma_bot_001",
    "total_pnl": 250.50,
    "win_rate": 0.67,
    "sharpe_ratio": 1.25,
    "max_drawdown": -0.08,
    "trades": [...]
}
```

#### Backtesting

```http
POST /api/v1/backtesting/run
Body: {
    "symbol": "BTCUSDT",
    "strategy": "MovingAverageCrossover",
    "start_date": "2023-01-01",
    "end_date": "2024-01-01",
    "initial_capital": 100000,
    "strategy_params": {
        "fast_period": 10,
        "slow_period": 30
    }
}

Response: {
    "backtest_id": "bt_123456",
    "status": "completed",
    "metrics": {
        "total_return": 15.5,
        "sharpe_ratio": 1.2,
        "max_drawdown": -12.3,
        "win_rate": 0.55,
        "total_trades": 45
    },
    "equity_curve": [...],
    "trades": [...]
}
```

### WebSocket Streams

```javascript
// Connect to market data stream
const ws = new WebSocket('ws://localhost:8000/ws/market');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Market update:', data);
    // data = {
    //     symbol: 'BTCUSDT',
    //     price: 45100.50,
    //     volume: 1234.56,
    //     timestamp: '2024-01-15T10:30:15Z'
    // }
};

// Subscribe to specific symbols
ws.send(JSON.stringify({
    action: 'subscribe',
    symbols: ['BTCUSDT', 'ETHUSDT']
}));
```

---

## Holding Period Strategies

### 1. Scalping (Seconds to Minutes)

**Characteristics:**
- Holding period: 1 second - 5 minutes
- Profit target: 0.1% - 0.5% per trade
- Frequency: 50-200 trades/day
- Best for: High liquidity pairs (BTC, ETH)

```python
class ScalpingStrategy(TradingStrategy):
    def __init__(self):
        super().__init__(name="Scalping")
        self.profit_target = 0.003  # 0.3%
        self.stop_loss = 0.001  # 0.1%

    async def analyze(self, df: pd.DataFrame, symbol: str) -> Dict:
        # Use 1m or 5m candles
        # Look for quick momentum shifts
        # Exit quickly on profit target or stop-loss
```

### 2. Day Trading (Minutes to Hours)

**Characteristics:**
- Holding period: 5 minutes - 8 hours
- Profit target: 0.5% - 3% per trade
- Frequency: 5-20 trades/day
- All positions closed by end of day

```python
class DayTradingStrategy(TradingStrategy):
    def __init__(self):
        super().__init__(name="DayTrading")
        self.max_holding_hours = 8
        self.end_of_day = "23:55"  # Close all positions before midnight
```

### 3. Swing Trading (Hours to Days)

**Characteristics:**
- Holding period: 1 day - 2 weeks
- Profit target: 3% - 15% per trade
- Frequency: 2-10 trades/week
- Captures multi-day trends

```python
class SwingTradingStrategy(TradingStrategy):
    def __init__(self):
        super().__init__(name="SwingTrading")
        self.min_holding_days = 1
        self.max_holding_days = 14
        self.profit_target = 0.10  # 10%
```

### 4. Position Trading (Weeks to Months)

**Characteristics:**
- Holding period: 2 weeks - 6 months
- Profit target: 15% - 100%+ per trade
- Frequency: 1-5 trades/month
- Long-term trend following

```python
class PositionTradingStrategy(TradingStrategy):
    def __init__(self):
        super().__init__(name="PositionTrading")
        self.min_holding_weeks = 2
        self.use_weekly_charts = True
        self.profit_target = 0.50  # 50%
```

---

## Best Practices

### 1. Strategy Development Workflow

1. **Research & Hypothesis**
   - Identify market inefficiency
   - Formulate testable hypothesis

2. **Backtest**
   - Test on historical data (2+ years)
   - Optimize parameters
   - Walk-forward analysis

3. **Paper Trade**
   - Test in live market (no real money)
   - Validate backtest results
   - Monitor slippage and execution

4. **Live Trade (Small)**
   - Start with minimal capital
   - Monitor performance daily
   - Compare to backtest metrics

5. **Scale Up**
   - Gradually increase capital
   - Monitor capacity constraints
   - Diversify across strategies

### 2. Common Pitfalls to Avoid

❌ **Overfitting** - Too many parameters, perfect backtest, poor live results
✅ **Solution:** Use simple strategies, out-of-sample testing

❌ **Look-ahead bias** - Using future data in backtests
✅ **Solution:** Ensure indicators only use past data

❌ **Ignoring transaction costs** - Commission, slippage, spread
✅ **Solution:** Include realistic costs in backtests (0.1% - 0.5%)

❌ **No risk management** - Letting losses run
✅ **Solution:** Always use stop-losses and position sizing

❌ **Emotional trading** - Overriding bot decisions
✅ **Solution:** Trust the system, review periodically

---

## Example: Complete Strategy Workflow

```python
# 1. Define strategy
class MyStrategy(TradingStrategy):
    async def analyze(self, df, symbol):
        # ... strategy logic ...
        pass

# 2. Backtest
from src.core.backtester import PortfolioBacktester

backtester = PortfolioBacktester()
result = backtester.run_backtest(
    symbol='BTCUSDT',
    strategy_class=MyStrategy,
    start_date='2022-01-01',
    end_date='2024-01-01'
)

metrics = result.get_performance_metrics()
print(f"Backtest Sharpe: {metrics['Sharpe Ratio']}")

# 3. If Sharpe > 1.0, proceed to paper trading
if metrics['Sharpe Ratio'] > 1.0:
    orchestrator = BotOrchestrator(testnet=True, test_mode=True)
    await orchestrator.initialize()

    bot = await orchestrator.create_bot(
        bot_id="my_strategy_paper",
        symbol="BTCUSDT",
        strategy=MyStrategy(),
        capital=10000,
        auto_start=True
    )

    # 4. Monitor for 1 month, then go live
```

---

## Resources & Further Reading

- **Backtrader Documentation:** https://www.backtrader.com/
- **Binance API Docs:** https://binance-docs.github.io/apidocs/
- **QuantLib:** https://www.quantlib.org/
- **Papers:**
  - "The Sharpe Ratio" by William F. Sharpe
  - "A Statistical Comparison of Technical Trading Systems" by Brock, Lakonishok, LeBaron

---

**Last Updated:** 2025-10-26
**Maintained By:** Trading System Team
**Questions?** Check `docs/guides/` or create an issue

