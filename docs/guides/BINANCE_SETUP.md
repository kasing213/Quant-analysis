# Binance Data Pipeline - Quick Start Guide

## 🎉 What We Built

A **complete real-time crypto data pipeline** that works **WITHOUT API authentication**!

```
Binance WebSocket → Redis Cache → RSI Calculator → Trading Signals
```

### Features:
- ✅ **Real-time data streaming** from Binance (public WebSocket, no auth needed)
- ✅ **Centralized data manager** for 10+ bots (single connection)
- ✅ **Redis caching** for ultra-fast data access
- ✅ **RSI calculator** with buy/sell signal generation
- ✅ **Scalable architecture** ready for multiple bots

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Install Requirements

```bash
# Install Binance-specific packages
pip install -r requirements/binance.txt

# Or install manually:
pip install websockets redis pandas numpy python-dotenv
```

### Step 2: Start Redis

**Option A: Using Docker (Recommended)**
```bash
docker-compose up -d redis
```

**Option B: Using Local Redis**
```bash
# Windows (if Redis installed)
redis-server

# Or download from: https://github.com/microsoftarchive/redis/releases
```

### Step 3: Test the Pipeline

```bash
python test_binance_data_pipeline.py
```

**Expected Output:**
```
✅ Redis is running!
1. Connecting to Binance WebSocket and Redis...
2. Subscribing to symbols: ['BTCUSDT', 'ETHUSDT']
3. Starting WebSocket stream...
4. Waiting 30 seconds for data to accumulate...
5. Running health check...
6. Testing RSI Calculation and Signals...

--- BTCUSDT ---
📊 RSI Analysis for BTCUSDT:
  Price: $43250.50
  RSI: 45.23
  Trend: UP
  Signal: HOLD

✅ DATA PIPELINE TEST COMPLETED SUCCESSFULLY
```

---

## 📊 How It Works

### Architecture

```
┌─────────────────────────────────┐
│  Binance Public WebSocket       │  ← No auth needed!
│  (Live BTC, ETH, etc. prices)   │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Data Manager                    │
│  - Receives 1-min candles        │
│  - Stores in Redis               │
│  - Keeps last 200 candles        │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Redis Cache                     │
│  Key: "candles:BTCUSDT:1m"       │
│  Value: [candle1, candle2, ...]  │
│  Ultra-fast: <1ms read time      │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  RSI Calculator                  │
│  - Reads from Redis              │
│  - Calculates RSI(14)            │
│  - Generates BUY/SELL signals    │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Trading Bots (10+)              │
│  - All read from shared cache    │
│  - No duplicate API calls        │
│  - Instant signal generation     │
└─────────────────────────────────┘
```

### Key Files Created

```
src/binance/
├── __init__.py                    # Module initialization
├── websocket_client.py            # WebSocket streaming (NO AUTH!)
└── data_manager.py                # Centralized data pipeline

src/indicators/
├── __init__.py
└── rsi.py                         # RSI calculator with signals

test_binance_data_pipeline.py     # Complete pipeline test
requirements/binance.txt           # Dependencies
```

---

## 💡 Usage Examples

### Example 1: Stream Live Data

```python
import asyncio
from src.binance.data_manager import BinanceDataManager

async def stream_live_data():
    # Create manager (testnet=True for safety)
    manager = BinanceDataManager(testnet=True)

    # Connect
    await manager.connect()

    # Subscribe to BTC and ETH
    await manager.subscribe_multiple_symbols(['BTCUSDT', 'ETHUSDT'])

    # Start streaming
    await manager.start_streaming()

asyncio.run(stream_live_data())
```

### Example 2: Calculate RSI and Get Signals

```python
import asyncio
from src.binance.data_manager import BinanceDataManager
from src.indicators.rsi import RSICalculator

async def get_trading_signal():
    manager = BinanceDataManager(testnet=True)
    await manager.connect()
    await manager.subscribe_symbol('BTCUSDT')

    # Wait for data
    await asyncio.sleep(30)

    # Get candles from Redis
    df = await manager.get_candles('BTCUSDT', count=50)

    # Calculate RSI
    rsi_calc = RSICalculator(period=14, oversold=30, overbought=70)
    df = rsi_calc.calculate(df)

    # Get signal
    signal = rsi_calc.get_signal_with_context(df)
    print(f"Signal: {signal}")

    await manager.close()

asyncio.run(get_trading_signal())
```

### Example 3: Monitor Multiple Pairs

```python
import asyncio
from src.binance.data_manager import BinanceDataManager

async def monitor_portfolio():
    manager = BinanceDataManager(testnet=True)
    await manager.connect()

    # Subscribe to portfolio
    pairs = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT']
    await manager.subscribe_multiple_symbols(pairs)

    # Stream in background
    stream_task = asyncio.create_task(manager.start_streaming())

    # Monitor every 10 seconds
    while True:
        await asyncio.sleep(10)

        for pair in pairs:
            price = await manager.get_latest_price(pair)
            print(f"{pair}: ${price}")

asyncio.run(monitor_portfolio())
```

---

## 🔥 Performance Benefits

### Why This Architecture Rocks:

1. **Single WebSocket Connection Per Pair**
   - 10 bots trading BTC = 1 WebSocket connection (not 10!)
   - Avoids Binance rate limits

2. **Redis Caching**
   - Read data in <1ms
   - All bots share same cache
   - No redundant API calls

3. **Smooth RSI Calculations**
   - Always have 200 candles ready
   - No data gaps
   - Real-time signal generation

4. **Scalable**
   - Add more bots without extra load
   - Each bot just reads from Redis

---

## 🐛 Troubleshooting

### Redis Not Running
```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG

# Start with Docker
docker-compose up -d redis

# Or download Redis for Windows:
# https://github.com/microsoftarchive/redis/releases
```

### WebSocket Connection Failed
- Check internet connection
- Testnet might be down, try production:
  ```python
  manager = BinanceDataManager(testnet=False)
  ```

### No Data in Redis
- Wait longer (30+ seconds for data to accumulate)
- Check if WebSocket is streaming:
  ```python
  health = await manager.health_check()
  print(health)
  ```

---

## 🎯 Next Steps

Now that you have real-time data and RSI signals:

1. ✅ **Data pipeline working** - Binance → Redis → RSI
2. 🔜 **Build trading bot** that reads signals
3. 🔜 **Add risk management** (position sizing, stop-loss)
4. 🔜 **Multi-bot orchestrator** to run 10+ bots
5. 🔜 **Add Binance API authentication** for live trading (when GitHub is fixed)

---

## 📝 Important Notes

- **No Authentication Required** - This uses public Binance WebSocket streams
- **For Trading** - You'll need API keys (waiting for GitHub fix)
- **Testnet** - Safe to test strategies without real money
- **Rate Limits** - Public streams have no auth limits!

---

**🎉 You now have a production-ready crypto data pipeline!**

The hard part (smooth data fetching) is DONE. Now we just need to:
1. Fix GitHub → Get Binance API keys
2. Add authenticated trading endpoints
3. Build the bot logic

While you're fixing GitHub, you can already start building bot strategies with this live data! 🚀
