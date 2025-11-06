# Quant Claude - Medium-Scale Quantitative Trading System

## Project Overview

A comprehensive quantitative trading system designed for individual traders and small funds, featuring CFD trading, investment tracking, and advanced stock analysis capabilities.

## System Architecture

### Core Components

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Data Layer    │───▶│ Engine Core  │───▶│   Frontend      │
│                 │    │              │    │                 │
│ • Market Data   │    │ • Strategies │    │ • Dashboard     │
│ • News/Alt Data │    │ • Risk Mgmt  │    │ • Monitoring    │
│ • Fundamentals  │    │ • Portfolio  │    │ • Controls      │
└─────────────────┘    │ • Execution  │    └─────────────────┘
                       └──────────────┘              │
┌─────────────────┐           │                     │
│   Brokers       │◀──────────┼─────────────────────┘
│                 │           ▼
│ • CFD Platforms │    ┌──────────────┐
│ • Stock Brokers │    │  Storage     │
│ • Crypto        │    │              │
└─────────────────┘    │ • PostgreSQL │
                       │ • InfluxDB   │
                       │ • Redis      │
                       └──────────────┘
```

## Tech Stack

### Backend
- **Language**: Python 3.11+
- **Web Framework**: FastAPI (async support)
- **ORM**: SQLAlchemy with Alembic migrations
- **Task Queue**: Celery with Redis broker
- **WebSocket**: FastAPI WebSocket for real-time updates

### Databases
- **PostgreSQL**: Trades, positions, accounts, strategies
- **InfluxDB**: Time-series market data, metrics
- **Redis**: Caching, sessions, real-time data

### Frontend
- **Framework**: React 18 with TypeScript
- **Charts**: Plotly.js / TradingView widgets
- **UI**: Material-UI or Tailwind CSS
- **State**: Redux Toolkit + RTK Query

### Infrastructure
- **Containerization**: Docker + Docker Compose
- **Monitoring**: Prometheus + Grafana
- **Logging**: Structured logging with ELK stack
- **API Documentation**: FastAPI auto-generated docs

## Core Modules

### 1. Data Infrastructure (`/data`)

#### Market Data Pipeline
```python
# data/providers/
├── yahoo_finance.py     # Primary: Unlimited but rate limited
├── interactive_brokers.py # Primary: Professional-grade real-time data
├── alpha_vantage.py     # Backup: Free tier: 25 calls/day
├── polygon.py           # Backup: Paid tier for real-time
├── iex_cloud.py         # Backup: Good free tier
└── base_provider.py     # Abstract base class

# Dual API Integration Module
├── dual_api_manager.py  # Manages Yahoo Finance + Interactive Brokers
└── data_aggregator.py   # Combines data from multiple sources
```

**Features:**
- Real-time and historical price data
- Fundamental data (P/E, EPS, revenue)
- Economic indicators (GDP, inflation, rates)
- Alternative data (sentiment, news)
- Data validation and cleaning

#### Dual API Architecture: Yahoo Finance + Interactive Brokers

**Primary Data Sources:**
```python
# Yahoo Finance API Integration
import yfinance as yf
from yahoo_fin import stock_info as si

class YahooFinanceProvider:
    def __init__(self):
        self.session = None

    def get_historical_data(self, symbol, period="1y"):
        """Fetch historical price data"""
        ticker = yf.Ticker(symbol)
        return ticker.history(period=period)

    def get_real_time_quote(self, symbol):
        """Get current market quote"""
        return si.get_live_price(symbol)

    def get_financials(self, symbol):
        """Fetch fundamental data"""
        ticker = yf.Ticker(symbol)
        return {
            'income_stmt': ticker.financials,
            'balance_sheet': ticker.balance_sheet,
            'cash_flow': ticker.cashflow
        }

# Interactive Brokers API Integration
from ib_insync import IB, Stock, util
from datetime import datetime

class InteractiveBrokersProvider:
    def __init__(self):
        self.ib = IB()
        self.connected = False

    def connect(self, host='127.0.0.1', port=7497, clientId=1):
        """Connect to IB TWS or Gateway"""
        try:
            self.ib.connect(host, port, clientId)
            self.connected = True
            return True
        except Exception as e:
            print(f"IB Connection failed: {e}")
            return False

    def get_real_time_data(self, symbol, exchange='SMART'):
        """Get real-time market data"""
        contract = Stock(symbol, exchange, 'USD')
        self.ib.qualifyContracts(contract)
        ticker = self.ib.reqMktData(contract)
        return ticker

    def get_historical_bars(self, symbol, duration="1 Y", barSize="1 day"):
        """Fetch historical data with high precision"""
        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)
        bars = self.ib.reqHistoricalData(
            contract, '', duration, barSize, 'MIDPOINT', True, False, []
        )
        return util.df(bars)
```

**Dual API Manager Implementation:**
```python
class DualAPIManager:
    def __init__(self):
        self.yahoo = YahooFinanceProvider()
        self.ib = InteractiveBrokersProvider()
        self.fallback_enabled = True

    def get_market_data(self, symbol, data_type="historical"):
        """
        Primary: Interactive Brokers for real-time precision
        Fallback: Yahoo Finance for reliability
        """
        try:
            if data_type == "real_time" and self.ib.connected:
                return self.ib.get_real_time_data(symbol)
            elif data_type == "historical":
                # Try IB first for precision
                if self.ib.connected:
                    ib_data = self.ib.get_historical_bars(symbol)
                    if not ib_data.empty:
                        return ib_data

                # Fallback to Yahoo Finance
                if self.fallback_enabled:
                    return self.yahoo.get_historical_data(symbol)

        except Exception as e:
            # Always fallback to Yahoo Finance on errors
            print(f"Primary data source failed: {e}, using Yahoo Finance")
            return self.yahoo.get_historical_data(symbol)

    def get_fundamentals(self, symbol):
        """Yahoo Finance excels at fundamental data"""
        return self.yahoo.get_financials(symbol)

    def health_check(self):
        """Monitor both API connections"""
        status = {
            'yahoo_finance': True,  # Always available
            'interactive_brokers': self.ib.connected,
            'timestamp': util.formatIBDatetime(datetime.now())
        }
        return status
```

**API Selection Strategy:**
- **Interactive Brokers**: Real-time data, order execution, professional-grade precision
- **Yahoo Finance**: Historical data, fundamental analysis, reliable fallback
- **Automatic Failover**: Seamless switching when primary source fails
- **Data Validation**: Cross-reference between sources for accuracy

#### Database Schema
```sql
-- Core tables
accounts (id, name, broker, balance, currency)
instruments (id, symbol, type, exchange, sector)
positions (id, account_id, instrument_id, quantity, avg_price)
trades (id, position_id, side, quantity, price, timestamp)
strategies (id, name, parameters, active, performance)
```

### 2. CFD Trading Module (`/trading`)

#### Broker Integrations
```python
# trading/brokers/
├── interactive_brokers/ # Primary: IB API for stocks & options
├── yahoo_finance/       # Data provider only, no trading
├── metatrader5/         # MT5 API integration for CFDs
├── ctrader/             # cTrader Open API
├── oanda/               # OANDA REST API
├── ig_markets/          # IG Markets API
└── base_broker.py       # Standard interface

# Dual API Trading Integration
├── ib_trader.py         # Interactive Brokers order execution
├── data_sync.py         # Yahoo Finance + IB data synchronization
└── unified_interface.py # Single interface for data + trading
```

**CFD Features:**
- Multi-asset support (forex, indices, commodities)
- Automated position sizing based on risk
- Dynamic stop-loss and take-profit
- Leverage monitoring and margin calls
- Slippage and spread tracking

#### Position Management
```python
class CFDPosition:
    def __init__(self, symbol, side, size, entry_price):
        self.symbol = symbol
        self.side = side  # 'long' or 'short'
        self.size = size
        self.entry_price = entry_price
        self.current_price = None
        self.stop_loss = None
        self.take_profit = None
        self.margin_required = None

    def calculate_pnl(self):
        """Calculate unrealized P&L"""
        pass

    def update_stops(self, trailing_stop=None):
        """Dynamic stop management"""
        pass
```

### 3. Investment Tracking (`/portfolio`)

#### Portfolio Analytics
- **Real-time P&L**: Mark-to-market across all positions
- **Performance Attribution**: Alpha/beta decomposition
- **Risk Metrics**: VaR, Sharpe ratio, max drawdown
- **Benchmark Comparison**: SPY, sector ETFs
- **Tax Optimization**: Wash sale detection, loss harvesting

#### Account Reconciliation
```python
class Portfolio:
    def __init__(self, accounts):
        self.accounts = accounts
        self.positions = {}
        self.cash_balance = 0

    def calculate_nav(self):
        """Net Asset Value calculation"""
        pass

    def get_exposure_by_sector(self):
        """Sector allocation breakdown"""
        pass

    def calculate_risk_metrics(self, period_days=252):
        """VaR, CVaR, Sharpe, etc."""
        pass
```

### 4. Stock Analysis Engine (`/analysis`)

#### Multi-Factor Scoring
```python
# analysis/factors/
├── value.py            # P/E, P/B, EV/EBITDA
├── growth.py           # Revenue/earnings growth
├── momentum.py         # Price/earnings momentum
├── quality.py          # ROE, debt-to-equity
├── technical.py        # RSI, MACD, moving averages
└── composite.py        # Combined factor scores
```

#### Screening & Ranking
- **Universe Definition**: S&P 500, Russell 2000, custom lists
- **Factor Combinations**: Multi-factor models
- **Backtesting Validation**: Historical factor performance
- **Sector Neutral**: Industry-relative scores

### 5. Risk Management (`/risk`)

#### Position Sizing
```python
class KellyPositionSizer:
    def calculate_position_size(self, win_rate, avg_win, avg_loss, account_balance):
        """Kelly Criterion position sizing"""
        kelly_fraction = win_rate - ((1 - win_rate) / (avg_win / avg_loss))
        return account_balance * min(kelly_fraction, 0.25)  # Cap at 25%
```

#### Risk Controls
- **Portfolio-level**: Maximum drawdown limits
- **Position-level**: Stop-loss automation
- **Correlation**: Avoid over-concentration
- **Leverage**: Dynamic adjustment based on volatility

### 6. Strategy Framework (`/strategies`)

#### Strategy Types
```python
# strategies/
├── mean_reversion.py    # Mean reversion with CFDs
├── momentum.py          # Trend following
├── pairs_trading.py     # Statistical arbitrage
├── factor_rotation.py   # Sector/factor rotation
└── base_strategy.py     # Abstract strategy class
```

#### Backtesting Engine
```python
class Backtest:
    def __init__(self, strategy, start_date, end_date, initial_capital):
        self.strategy = strategy
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital

    def run(self):
        """Execute historical simulation"""
        pass

    def generate_report(self):
        """Performance metrics and charts"""
        pass
```

### 7. Web Dashboard (`/frontend`)

#### Key Screens
- **Overview**: Portfolio summary, P&L, top positions
- **Positions**: Active trades, unrealized P&L
- **Analytics**: Factor exposures, performance attribution
- **Screening**: Stock rankings, watchlists
- **Strategy**: Backtest results, live strategy performance
- **Risk**: VaR reports, drawdown analysis

#### Real-time Features
- WebSocket connections for live prices
- Push notifications for trade alerts
- Mobile-responsive design
- Dark/light theme toggle

## Development Roadmap

### Phase 1: Foundation (Weeks 1-3)
- [ ] Project setup and database schema
- [ ] Basic market data pipeline
- [ ] Simple portfolio tracking
- [ ] Web framework setup

### Phase 2: Core Features (Weeks 4-8)
- [ ] CFD broker integration (choose 1-2 brokers)
- [ ] Position management system
- [ ] Basic risk controls
- [ ] Simple web dashboard

### Phase 3: Analytics (Weeks 9-12)
- [ ] Factor analysis engine
- [ ] Stock screening system
- [ ] Performance attribution
- [ ] Backtesting framework

### Phase 4: Advanced Features (Weeks 13-16)
- [ ] Strategy automation
- [ ] Advanced risk management
- [ ] Mobile app (optional)
- [ ] Machine learning models

## Getting Started

### Prerequisites
```bash
# System requirements
Python 3.11+
PostgreSQL 14+
Redis 6+
Node.js 18+ (for frontend)

# Optional
Docker & Docker Compose
InfluxDB 2.0+
```

### Quick Setup
```bash
# Clone and setup
git clone <repo-url> quant-claude
cd quant-claude
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Install dual API dependencies
pip install yfinance yahoo-fin ib-insync
pip install pandas numpy requests asyncio

npm install  # in frontend directory

# Database setup
createdb quantdb
alembic upgrade head

# Start development
docker-compose up -d  # databases
python main.py        # backend
npm start            # frontend (separate terminal)
```

### Configuration
```yaml
# config.yaml
database:
  url: "postgresql://user:pass@localhost/quantdb"

# Dual API Configuration
data_providers:
  yahoo_finance:
    enabled: true
    rate_limit: 2000  # requests per hour
    timeout: 10
    retry_attempts: 3

  interactive_brokers:
    enabled: true
    host: "127.0.0.1"
    port: 7497  # TWS: 7497, Gateway: 4001
    client_id: 1
    timeout: 30
    auto_reconnect: true

  # Backup providers
  alpha_vantage:
    api_key: "your_key"
    calls_per_day: 25
    enabled: false

# API Failover Strategy
api_strategy:
  primary_data: "interactive_brokers"  # or "yahoo_finance"
  fallback_enabled: true
  health_check_interval: 300  # seconds
  cross_validation: true  # validate data across sources

brokers:
  interactive_brokers:
    account_id: "your_account"
    environment: "paper"  # or "live"
    max_daily_trades: 100

  oanda:
    api_key: "your_key"
    account_id: "your_account"
    environment: "practice"  # or "live"

risk:
  max_portfolio_risk: 0.02  # 2% daily VaR
  max_position_size: 0.10   # 10% of portfolio
```

## Security & Compliance

### API Security
- JWT authentication with refresh tokens
- Rate limiting on all endpoints
- Input validation and sanitization
- CORS configuration

### Data Protection
- Encrypted API keys storage
- Database encryption at rest
- Secure WebSocket connections (WSS)
- Regular security audits

### Trading Compliance
- Trade logging and audit trails
- Position limits enforcement
- Regulatory reporting hooks
- Risk oversight dashboards

## Monitoring & Maintenance

### System Health
```python
# health checks
/health/database    # DB connectivity
/health/brokers     # Broker API status
/health/data        # Market data feeds
/health/strategies  # Strategy execution
```

### Performance Monitoring
- API response times
- Database query performance
- Memory and CPU usage
- Strategy P&L tracking

### Backup & Recovery
- Daily database backups
- Strategy configuration versioning
- Trade data replication
- Disaster recovery procedures

## Cost Estimation

### Monthly Operating Costs
- **VPS/Cloud Server**: $50-200 (depending on scale)
- **Database Hosting**: $25-100
- **Market Data**: $50-500 (depends on real-time needs)
- **Broker APIs**: Usually free
- **Monitoring Tools**: $20-50

**Total**: ~$150-850/month for medium-scale operation

## Next Steps

1. **Choose Your Broker**: Research CFD brokers with good APIs
2. **Data Strategy**: Decide on free vs paid market data
3. **Trading Strategies**: Define your edge and backtesting approach
4. **Risk Tolerance**: Set position sizing and drawdown limits
5. **Timeline**: Allocate 3-4 months for full system development

Ready to start building? Let me know which component you'd like to tackle first!