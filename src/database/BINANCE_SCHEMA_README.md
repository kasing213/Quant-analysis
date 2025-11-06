# Binance Bot Persistence Schema

This directory contains the PostgreSQL schema for persisting Binance trading bot data.

## Overview

The schema creates a dedicated `binance` schema with tables for:
- **Bot Configurations** - Bot settings and parameters
- **Bot States** - Snapshots for restart resilience
- **Bot Trades** - Complete trade history
- **Bot Performance** - Daily and real-time metrics
- **Bot Signals** - Trading signal history for analysis

## Quick Start

### Method 1: Using the Shell Script (Recommended)

**On Windows:**
```cmd
scripts\apply_schema.bat
```

**On Linux/WSL:**
```bash
./scripts/apply_schema.sh
```

### Method 2: Using Python Directly

```bash
# Activate virtual environment first
source venv_binance/bin/activate  # Linux/Mac
# OR
venv_binance\Scripts\activate  # Windows

# Run migration
python scripts/apply_bot_schema_direct.py
```

### Method 3: Using psql (Manual)

```bash
psql -h localhost -U trader -d trading_db -f src/database/binance_bots_schema.sql
```

## Schema Structure

### Tables

#### `binance.bot_configs`
Stores bot configuration and settings.
- `bot_id` - Unique bot identifier (PRIMARY KEY)
- `bot_name` - Human-readable bot name
- `symbol` - Trading pair (e.g., BTCUSDT)
- `strategy_name` - Strategy type (RSI, MACD, etc.)
- `strategy_params` - JSON strategy parameters
- `interval` - Candle interval (1m, 5m, etc.)
- `capital` - Total capital allocated to the bot
- `position_size` - Baseline position size in USD
- `risk_per_trade` - Max percentage of capital risked per trade
- `max_position_size` - Max percentage of capital for any position
- `stop_loss_pct` / `take_profit_pct` - Static risk parameters
- `trailing_stop_pct` - Optional trailing stop distance
- `drawdown_guard_pct` - Halt bots when drawdown exceeds this level
- `is_active` / `is_running` - Status flags
- Timestamps for tracking start/stop times

#### `binance.bot_states`
Snapshots of bot state for crash recovery.
- `state_id` - Unique state snapshot ID
- `bot_id` - Reference to bot config
- `state_data` - Full bot state as JSON
- `total_pnl`, `win_rate`, `total_trades` - Performance metrics
- Current position information
- `current_trailing_stop` - Active trailing stop trigger price
- `peak_equity` - Highest recorded equity for drawdown tracking
- `current_drawdown_pct` - Current drawdown as a fraction of peak equity
- `trading_halted` / `halt_reason` - Guardrail state and justification
- `snapshot_time` - When snapshot was taken

#### `binance.bot_trades`
Complete history of all bot trades.
- `trade_id` - Unique trade ID
- `bot_id` - Bot that made the trade
- `symbol` - Trading pair
- `order_id` / `external_order_id` - Order identifiers
- `side` - BUY or SELL
- `order_type` - MARKET, LIMIT, etc.
- `quantity`, `price` - Trade details
- `commission` - Trading fees
- `pnl` - Profit/Loss for the trade
- `strategy_signal` / `signal_reason` - Why the trade was made
- `is_entry` - Entry vs exit trade
- `is_test_mode` - Paper vs live trading

#### `binance.bot_performance_snapshots`
Daily performance summaries.
- `bot_id` - Bot reference
- `snapshot_date` - Date of snapshot
- `total_pnl`, `daily_pnl` - PnL metrics
- Win/loss statistics
- `sharpe_ratio`, `max_drawdown` - Risk metrics
- Unique constraint on (bot_id, snapshot_date)

#### `binance.bot_metrics_realtime`
Real-time monitoring data.
- Current price and position info
- Unrealized/realized PnL
- Strategy indicators (RSI, MACD, etc.) as JSON
- Market conditions as JSON

#### `binance.bot_signals`
History of trading signals.
- `signal_type` - BUY, SELL, or HOLD
- `signal_strength` - Confidence (0-100)
- `indicators` - Indicator values at signal time
- `action_taken` - EXECUTED, IGNORED, or REJECTED
- `rejection_reason` - Why signal was rejected
- Link to executed trade (if any)

### Views

#### `binance.bot_status_view`
Real-time view of all bot statuses with latest state information, including capital allocation, trailing-stop settings, drawdown guard configuration, and the most recent guardrail state.

#### `binance.bot_performance_summary`
Aggregated performance metrics for all bots, enriched with capital/risk configuration and last recorded drawdown/guardrail state.

#### `binance.recent_bot_signals`
Recent trading signals (last 24 hours) with execution status.

### Functions

#### `binance.upsert_bot_config(...)`
Create or update bot configuration.

#### `binance.save_bot_state(...)`
Save a bot state snapshot.

#### `binance.get_latest_bot_state(bot_id)`
Retrieve the most recent state for restart.

#### `binance.record_bot_trade(...)`
Log a trade execution.

#### `binance.cleanup_old_metrics()`
Remove metrics older than 90 days.

## Usage Examples

### Creating a Bot Configuration

```python
from src.binance.bot_persistence import BotPersistence

persistence = BotPersistence()
await persistence.initialize()

await persistence.save_bot_config(
    bot_id="rsi_btc_001",
    bot_name="BTC RSI Strategy",
    symbol="BTCUSDT",
    strategy_name="RSI",
    strategy_params={"period": 14, "oversold": 30, "overbought": 70},
    interval="1m",
    position_size=100.0,
    stop_loss_pct=2.0,
    take_profit_pct=5.0
)
```

### Recording a Trade

```python
await persistence.record_trade(
    bot_id="rsi_btc_001",
    symbol="BTCUSDT",
    order_id="order_123",
    external_order_id="binance_456",
    side="BUY",
    order_type="MARKET",
    quantity=0.001,
    price=45000.0,
    commission=0.05,
    strategy_signal="RSI_OVERSOLD",
    signal_reason="RSI crossed below 30 and bounced back",
    is_entry=True,
    is_test_mode=True
)
```

### Saving Bot State

```python
await persistence.save_bot_state(
    bot_id="rsi_btc_001",
    state_data={
        "last_rsi": 35.2,
        "candles_processed": 150,
        "last_signal_time": "2025-10-11T12:30:00Z"
    },
    total_pnl=250.50,
    win_rate=65.5,
    total_trades=20,
    winning_trades=13,
    losing_trades=7,
    position_side="LONG",
    position_size=0.001,
    position_entry_price=45000.0
)
```

### Retrieving Bot Status

```python
# Get configuration
config = await persistence.get_bot_config("rsi_btc_001")

# Get latest state (for restart)
state = await persistence.get_latest_bot_state("rsi_btc_001")

# Get comprehensive status
status = await persistence.get_bot_status("rsi_btc_001")

# Get performance summary
performance = await persistence.get_bot_performance_summary("rsi_btc_001")

# Get trade history
trades = await persistence.get_bot_trades("rsi_btc_001", limit=50)
```

## Integration with Bot Orchestrator

The persistence layer is designed to integrate with the `BotOrchestrator`:

1. **On Bot Creation** - Save config to database
2. **On Bot Start** - Load last state if available
3. **During Trading** - Record trades and signals
4. **Periodic Snapshots** - Save state every N minutes
5. **On Bot Stop** - Save final state
6. **Daily** - Create performance snapshot

## Maintenance

### Cleanup Old Data

```python
# Remove metrics older than 90 days
await persistence.cleanup_old_metrics()
```

### Backup

```bash
# Backup bot data
pg_dump -h localhost -U trader -d trading_db -n binance > binance_backup.sql

# Restore
psql -h localhost -U trader -d trading_db < binance_backup.sql
```

## Indexes

The schema includes optimized indexes for:
- Bot status queries
- Trade history lookups
- Performance analysis
- Signal analysis
- Time-series queries

All indexes are created automatically with the schema.

## Troubleshooting

### Schema Already Exists
The schema uses `IF NOT EXISTS` clauses, so it's safe to run multiple times.

### Connection Issues
Check your `.env` file for correct database credentials:
```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=trading_db
POSTGRES_USER=trader
POSTGRES_PASSWORD=your_password
```

### Permission Issues
Ensure the database user has CREATE privileges:
```sql
GRANT CREATE ON DATABASE trading_db TO trader;
GRANT ALL ON SCHEMA binance TO trader;
```

## Next Steps

After applying the schema:
1. Test with a sample bot configuration
2. Integrate persistence calls into bot lifecycle
3. Set up periodic state snapshots
4. Create monitoring dashboards using the views
5. Configure automated backups
