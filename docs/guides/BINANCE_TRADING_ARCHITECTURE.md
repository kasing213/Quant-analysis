# Binance Trading Bot Architecture

## Overview

A complete automated trading system with:
- Real-time WebSocket market data streaming
- REST API for order execution
- Multiple concurrent trading bots
- Redis-based data caching
- FastAPI web interface
- PostgreSQL database integration

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                  FastAPI Backend (Port 8000)            │
│  ┌──────────────────────────────────────────────────┐   │
│  │           Bot Orchestrator                       │   │
│  │  ┌──────────────┐  ┌──────────────┐             │   │
│  │  │ BTC RSI Bot  │  │ ETH RSI Bot  │   ...       │   │
│  │  └──────────────┘  └──────────────┘             │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │        Binance Data Manager                      │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐ │   │
│  │  │ WebSocket  │  │ REST API   │  │   Redis    │ │   │
│  │  │  Streams   │  │  Client    │  │   Cache    │ │   │
│  │  └────────────┘  └────────────┘  └────────────┘ │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
      ┌──────────────┐        ┌─────────────┐
      │  PostgreSQL  │        │    Redis    │
      │ (Portfolio)  │        │(Market Data)│
      └──────────────┘        └─────────────┘
                                      │
                                      ▼
                              ┌───────────────┐
                              │   Binance     │
                              │   WebSocket   │
                              └───────────────┘
```

## Components

### 1. WebSocket Client (`src/binance/websocket_client.py`)
- Connects to Binance WebSocket API
- Subscribes to real-time kline (candlestick) data
- Supports ticker, trade, and book ticker streams
- Buffers candle data for technical analysis
- **No API keys required** (public streams)

### 2. Data Manager (`src/binance/data_manager.py`)
- Centralized data pipeline using Redis
- Single WebSocket connection per symbol
- Distributes data to multiple bots efficiently
- Stores last 200 candles per symbol
- Provides pandas DataFrame interface

### 3. REST API Client (`src/binance/rest_client.py`)
- Order execution (market, limit, stop-loss)
- Account balance queries
- Position management
- Order history
- Test mode for paper trading (simulated orders)

### 4. Trading Bot Framework (`src/binance/trading_bot.py`)
- Base `TradingStrategy` class for custom strategies
- `TradingBot` class with:
  - Strategy execution
  - Position management
  - Risk management (stop-loss, take-profit)
  - Performance tracking
- Position sizing based on risk percentage
- Automatic PnL calculation

### 5. RSI Strategy (`src/binance/strategies/rsi_strategy.py`)
- Buy when RSI < 30 (oversold)
- Sell when RSI > 70 (overbought)
- Trend confirmation with SMA
- Configurable parameters (period, thresholds)

### 6. Bot Orchestrator (`src/binance/bot_orchestrator.py`)
- Manages multiple bots simultaneously
- Shared data manager for efficiency
- Start/stop individual or all bots
- Portfolio-level statistics
- Health monitoring

### 7. API Endpoints (`src/api/routers/bots.py`)
- RESTful bot management
- Create, start, stop, remove bots
- Real-time statistics
- Portfolio summary

## Data Flow

1. **Market Data Ingestion**
   ```
   Binance WebSocket → Data Manager → Redis → Bots
   ```

2. **Strategy Execution**
   ```
   Bot → Get Candles → Calculate Indicators → Generate Signal → Execute Order
   ```

3. **Order Execution**
   ```
   Bot → REST Client → Binance API → Order Confirmation → Position Update
   ```

## File Structure

```
src/
├── binance/
│   ├── __init__.py
│   ├── websocket_client.py     # WebSocket streaming
│   ├── data_manager.py          # Redis data pipeline
│   ├── rest_client.py           # Order execution
│   ├── trading_bot.py           # Bot framework
│   ├── bot_orchestrator.py      # Multi-bot manager
│   └── strategies/
│       ├── __init__.py
│       └── rsi_strategy.py      # RSI strategy
├── api/
│   └── routers/
│       └── bots.py              # Bot API endpoints
└── indicators/
    └── rsi.py                   # RSI calculator
```

## Key Features

### 1. Efficient Data Streaming
- **Single WebSocket per symbol** (not per bot)
- **Redis caching** for instant data access
- **200-candle buffer** for technical analysis
- **Supports 10+ concurrent bots** efficiently

### 2. Safe Trading
- **Test mode** (paper trading, no real orders)
- **Testnet support** (Binance testnet)
- **Position sizing** based on risk percentage
- **Automatic stop-loss** and take-profit

### 3. Flexible Strategy System
- **Abstract base class** for custom strategies
- **Easy to extend** with new indicators
- **Strategy parameters** configurable via API
- **Multiple strategies** can run simultaneously

### 4. Real-time Management
- **FastAPI endpoints** for bot control
- **WebSocket support** for live updates
- **Health monitoring** for all components
- **Performance metrics** (PnL, win rate, trades)

## Quick Start

### 1. Start Redis
```bash
docker run -d -p 6379:6379 redis:latest
```

### 2. Start Backend Server
```bash
# Option A: Using existing script
./start_trading_server.sh

# Option B: Manual start
source venv_api/bin/activate
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Access API
- **API Docs**: http://localhost:8000/docs
- **Dashboard**: http://localhost:8000
- **Health**: http://localhost:8000/health

### 4. Create a Bot (via API)
```bash
curl -X POST http://localhost:8000/api/v1/bots/create \
  -H "Content-Type: application/json" \
  -d '{
    "bot_id": "btc_rsi",
    "symbol": "BTCUSDT",
    "strategy_name": "RSI_14",
    "strategy_params": {"period": 14, "oversold": 30, "overbought": 70},
    "capital": 1000,
    "risk_per_trade": 0.02,
    "auto_start": true
  }'
```

### 5. Monitor Bots
```bash
# Get all bots
curl http://localhost:8000/api/v1/bots/

# Get specific bot stats
curl http://localhost:8000/api/v1/bots/btc_rsi/stats

# Get portfolio summary
curl http://localhost:8000/api/v1/bots/portfolio/summary
```

## Environment Variables

Create `.env` file:
```env
# Binance Configuration
BINANCE_ENABLE_BOTS=true
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
BINANCE_TESTNET=true          # Use testnet
BINANCE_TEST_MODE=true        # Simulate orders (safe)

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/trading
```

## Safety Features

1. **Test Mode** (default)
   - No real orders executed
   - All operations are simulated
   - Safe for development and testing

2. **Testnet Mode**
   - Uses Binance testnet
   - Free test USDT
   - Real API behavior without real money

3. **Risk Management**
   - Maximum risk per trade (default 2%)
   - Position size limits (default 10% of capital)
   - Automatic stop-loss orders
   - Take-profit levels

## API Endpoints

### Bot Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/bots/create` | Create new bot |
| POST | `/api/v1/bots/{bot_id}/start` | Start bot |
| POST | `/api/v1/bots/{bot_id}/stop` | Stop bot |
| DELETE | `/api/v1/bots/{bot_id}` | Remove bot |
| GET | `/api/v1/bots/{bot_id}/stats` | Get bot statistics |
| GET | `/api/v1/bots/` | List all bots |
| POST | `/api/v1/bots/start-all` | Start all bots |
| POST | `/api/v1/bots/stop-all` | Stop all bots |
| GET | `/api/v1/bots/portfolio/summary` | Portfolio summary |
| GET | `/api/v1/bots/health` | Health check |

## Performance Metrics

Each bot tracks:
- **Total PnL** (Profit & Loss)
- **Total Trades** (executed)
- **Winning Trades** (profitable)
- **Win Rate** (percentage)
- **Current Position** (if any)
- **Running Status** (active/stopped)

Portfolio summary includes:
- **Total Capital** across all bots
- **Combined PnL**
- **Overall Win Rate**
- **Total Trades** across all bots

## Extending the System

### Creating Custom Strategies

1. **Inherit from `TradingStrategy`**:
```python
from src.binance.trading_bot import TradingStrategy, SignalType
import pandas as pd

class MyStrategy(TradingStrategy):
    def __init__(self, param1, param2):
        super().__init__(name="MyStrategy")
        self.param1 = param1
        self.param2 = param2

    async def analyze(self, df: pd.DataFrame, symbol: str):
        # Your analysis logic
        signal = SignalType.BUY.value if condition else SignalType.HOLD.value

        return {
            'signal': signal,
            'confidence': 0.8,
            'reason': 'Your reason here'
        }

    def get_parameters(self):
        return {'param1': self.param1, 'param2': self.param2}
```

2. **Register in API Router** (`src/api/routers/bots.py`):
```python
from src.binance.strategies.my_strategy import MyStrategy

# In create_bot endpoint
if request.strategy_name == 'MyStrategy':
    strategy = MyStrategy(
        param1=params.get('param1'),
        param2=params.get('param2')
    )
```

## Troubleshooting

### Redis Connection Issues
```bash
# Check if Redis is running
docker ps | grep redis

# Start Redis
docker run -d -p 6379:6379 redis:latest
```

### Port Already in Use
```bash
# Find process using port 8000
lsof -ti:8000

# Kill process
kill -9 $(lsof -ti:8000)
```

### Bot Not Starting
- Check Redis connection
- Verify Binance API credentials (if using live mode)
- Check bot orchestrator initialization in logs
- Ensure sufficient data in Redis (wait 30-60 seconds after starting)

## Testing

### Test Data Pipeline
```bash
python test_binance_data_pipeline.py
```

This tests:
1. WebSocket connection to Binance
2. Data storage in Redis
3. RSI calculation
4. Signal generation

## Next Steps

1. **Add More Strategies**:
   - Moving Average Crossover
   - MACD
   - Bollinger Bands
   - Custom ML models

2. **Enhance Risk Management**:
   - Trailing stop-loss
   - Dynamic position sizing
   - Portfolio-level risk limits

3. **Add More Exchanges**:
   - Same architecture works for any exchange
   - Just implement WebSocket and REST clients

4. **Advanced Features**:
   - Backtesting integration
   - Performance analytics dashboard
   - Trade journaling
   - Alert system (Telegram, Email)

## License & Disclaimer

This is educational software. **Always test thoroughly before using real money.**

- Start with **test mode**
- Use **Binance testnet**
- Never risk more than you can afford to lose
- Understand the strategy before deploying
