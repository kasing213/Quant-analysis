# Pipeline-Specific Backend Logic - Usage Guide

## ✅ Implementation Complete!

> **Important:** The legacy Interactive Brokers pipeline has been retired from this project. All remaining examples focus on Binance paper/live modes. Refer to the separate IB/CFD project for legacy functionality.

Automatic credential switching per pipeline mode has been successfully implemented. This guide shows you how to use it.

## What Was Implemented

1. **Automatic Credential Switching** - Different credentials for each pipeline mode
2. **Service Wiring Configuration** - Services automatically configure per pipeline
3. **Configuration Validation** - Built-in validation before startup
4. **Redis Database Isolation** - Each pipeline uses its own Redis database
5. **Pipeline-Aware Symbol Selection** - Crypto pairs for Binance, stocks for IB

## Quick Start

### 1. Run the Test

```bash
python test_pipeline_quick.py
```

You should see:
```
============================================================
  PIPELINE CONFIGURATION CHECK
============================================================

[OK] Current Pipeline: BINANCE_PAPER

[Binance] Settings:
   - Testnet: True
   - Test Mode: True
   - Credentials: Missing

[Redis] Settings:
   - Database: 0

[Dashboard] Symbols: BTCUSDT, ETHUSDT, BNBUSDT

[Validation] PASSED
```

### 2. Configure Your Environment

Copy `.env.example` to `.env` and configure credentials:

```bash
cp .env.example .env
```

Edit `.env` and set your pipeline and credentials:

```env
# Choose your pipeline
CURRENT_PIPELINE=binance_paper

# Binance Paper Trading (Testnet)
BINANCE_TESTNET_API_KEY=your_testnet_key_here
BINANCE_TESTNET_API_SECRET=your_testnet_secret_here

# Binance Live Trading (Real Money!)
BINANCE_LIVE_API_KEY=your_live_key_here
BINANCE_LIVE_API_SECRET=your_live_secret_here

# Interactive Brokers
IB_HOST=127.0.0.1
IB_PORT=7497
IB_ACCOUNT=your_ib_account
```

### 3. Start the Server

```bash
# Using the start script
./start.sh

# Or directly with Python
python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Watch the logs for pipeline configuration details!

## Pipeline Modes

### 🧪 BINANCE_PAPER (Default)
**Paper Trading with Binance Testnet**

- **Use Case**: Safe testing, learning, strategy development
- **Credentials**: `BINANCE_TESTNET_API_KEY` / `BINANCE_TESTNET_API_SECRET`
- **Testnet**: Yes (testnet.binance.vision)
- **Test Mode**: Yes (simulated orders)
- **Redis DB**: 0
- **Symbols**: Crypto pairs (BTCUSDT, ETHUSDT, etc.)
- **Risk**: None - no real money

**When to use:**
- Testing new strategies
- Learning the system
- Development work
- Demo purposes

### 💰 BINANCE_LIVE
**Live Trading with Real Binance Account**

- **Use Case**: Real money trading
- **Credentials**: `BINANCE_LIVE_API_KEY` / `BINANCE_LIVE_API_SECRET`
- **Testnet**: No (api.binance.com)
- **Test Mode**: Optional (can be forced on for safety)
- **Redis DB**: 1
- **Symbols**: Crypto pairs (BTCUSDT, ETHUSDT, etc.)
- **Risk**: HIGH - real money at stake!

**When to use:**
- Live trading with real funds
- After thorough testing in paper mode
- With proper risk management configured

**⚠️ WARNING**: This mode uses real money. Test extensively in paper mode first!


## API Endpoints

The following new endpoints are available:

### GET `/api/v1/pipelines/`
Get current pipeline and available options.

**Response:**
```json
{
  "current": {
    "id": "binance_paper",
    "label": "Binance Paper"
  },
  "options": [
    {"id": "binance_paper", "label": "Binance Paper"},
    {"id": "binance_live", "label": "Binance Live"},
    {"id": "legacy_ib", "label": "Legacy IB/CFD"}
  ]
}
```

### POST `/api/v1/pipelines/select`
Switch to a different pipeline.

**Request:**
```json
{
  "pipeline_id": "binance_live"
}
```

**Response:**
```json
{
  "id": "binance_live",
  "label": "Binance Live"
}
```

**⚠️ Note**: Server restart required for full effect!

### GET `/api/v1/pipelines/validate`
Validate current pipeline configuration.

**Response:**
```json
{
  "pipeline": "binance_paper",
  "valid": true,
  "errors": [],
  "summary": {
    "pipeline": "binance_paper",
    "services": {
      "binance": {
        "enabled": true,
        "testnet": true,
        "test_mode": true,
        "has_credentials": false
      },
      "redis": {
        "enabled": true,
        "db": 0
      }
    }
  }
}
```

### GET `/api/v1/pipelines/config`
Get detailed configuration info.

**Response:**
```json
{
  "pipeline": "binance_paper",
  "services": {...},
  "credentials_configured": false,
  "redis_database": 0,
  "testnet_mode": true,
  "test_mode": true
}
```

## How It Works

### Automatic Credential Selection

The system automatically selects credentials based on the pipeline:

```python
# When CURRENT_PIPELINE=binance_paper
api_key = os.getenv("BINANCE_TESTNET_API_KEY") or os.getenv("BINANCE_API_KEY")

# When CURRENT_PIPELINE=binance_live
api_key = os.getenv("BINANCE_LIVE_API_KEY") or os.getenv("BINANCE_API_KEY")

# Fallback to legacy credentials if pipeline-specific ones aren't set
```

### Redis Database Isolation

Each pipeline uses its own Redis database to prevent data mixing:

- `binance_paper` → Redis DB 0
- `binance_live` → Redis DB 1
- `legacy_ib` → Redis DB 2

This ensures paper trading data never mixes with live trading data!

### Service Configuration

Services are automatically configured per pipeline:

```python
from src.api.pipeline_config import get_pipeline_config

# Get configuration for current pipeline
config = get_pipeline_config()

# Get Binance config (None for legacy_ib pipeline)
binance_config = config.get_binance_config()

# Get Redis config (automatically selects correct DB)
redis_config = config.get_redis_config()

# Get appropriate symbols (crypto for Binance, stocks for IB)
symbols = config.get_dashboard_symbols()
```

## Switching Pipelines

### Method 1: Environment Variable (Recommended)

Edit your `.env` file:
```env
CURRENT_PIPELINE=binance_live
```

Restart the server:
```bash
./start.sh
```

### Method 2: API Call

```bash
curl -X POST http://localhost:8000/api/v1/pipelines/select \
  -H "Content-Type: application/json" \
  -d '{"pipeline_id": "binance_live"}'
```

**Then restart the server for changes to take full effect.**

### Method 3: Programmatic

```python
from src.api.pipeline import set_current_pipeline, Pipeline

# Switch to live trading
set_current_pipeline(Pipeline.BINANCE_LIVE)

# Restart your application for changes to take effect
```

## Configuration Validation

Always validate your configuration before switching pipelines:

```bash
curl http://localhost:8000/api/v1/pipelines/validate
```

Or use the test script:
```bash
python test_pipeline_quick.py
```

## Example Workflows

### Workflow 1: Paper Trading → Live Trading

1. **Start with paper trading** (default)
   ```env
   CURRENT_PIPELINE=binance_paper
   BINANCE_TESTNET_API_KEY=your_testnet_key
   BINANCE_TESTNET_API_SECRET=your_testnet_secret
   ```

2. **Test your strategies extensively**
   - Run for days/weeks
   - Monitor performance
   - Validate your strategy

3. **Get live credentials**
   - Create Binance account
   - Generate API keys
   - Add to `.env`:
     ```env
     BINANCE_LIVE_API_KEY=your_live_key
     BINANCE_LIVE_API_SECRET=your_live_secret
     ```

4. **Validate live configuration**
   ```bash
   CURRENT_PIPELINE=binance_live python test_pipeline_quick.py
   ```

5. **Switch to live (carefully!)**
   ```env
   CURRENT_PIPELINE=binance_live
   BINANCE_ENABLE_BOTS=true  # Enable if ready
   ```

6. **Restart server**
   ```bash
   ./start.sh
   ```

7. **Monitor closely!**
   - Watch the logs
   - Check Redis DB 1 (live data)
   - Monitor your Binance account

### Workflow 2: Using Multiple Pipelines

You can easily switch between pipelines for different purposes:

**Morning: Check paper trading results**
```bash
CURRENT_PIPELINE=binance_paper ./start.sh
# Review overnight paper trading
```

**Afternoon: Monitor live trading**
```bash
CURRENT_PIPELINE=binance_live ./start.sh
# Monitor real positions
```

**Evening: Test new strategy in legacy system**
```bash
CURRENT_PIPELINE=legacy_ib ./start.sh
# Test with IB data
```

## Safety Features

### 1. Test Mode Override
Force test mode even with live credentials:
```env
BINANCE_TEST_MODE=true
```

### 2. Configuration Validation
Server validates config on startup and warns about issues.

### 3. Credential Isolation
Different credentials for each pipeline prevent accidental live trading.

### 4. Redis Database Isolation
Paper and live data never mix in Redis.

### 5. Clear Logging
Startup logs show exactly which pipeline and credentials are active.

## Troubleshooting

### Issue: "Binance configuration invalid: API key and secret required"

**Solution**: Add credentials for your pipeline:
```env
# For paper trading
BINANCE_TESTNET_API_KEY=your_key

# For live trading
BINANCE_LIVE_API_KEY=your_key
```

### Issue: "Market data unavailable"

**Check**:
1. Redis is running: `redis-cli ping`
2. Market data enabled: `BINANCE_ENABLE_MARKET_DATA=true`
3. Symbols configured: `BINANCE_DASHBOARD_SYMBOLS=BTCUSDT,ETHUSDT`

### Issue: Services don't reflect pipeline switch

**Solution**: Restart the server! Pipeline switching updates the configuration file, but services need restart to reinitialize.

### Issue: Wrong Redis database being used

**Check**: Verify pipeline is set correctly:
```bash
python test_pipeline_quick.py
```

Look for `[Redis] Settings: - Database: X`

## Advanced Configuration

### Custom Redis Database Mapping

Edit `src/api/pipeline_config.py`:
```python
db_map = {
    Pipeline.BINANCE_PAPER: 0,
    Pipeline.BINANCE_LIVE: 1,
}
```

### Custom Symbol Lists

Per pipeline in `.env`:
```env
# Binance pipelines
BINANCE_DASHBOARD_SYMBOLS=BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT

# Legacy IB
IB_DASHBOARD_SYMBOLS=AAPL,GOOGL,MSFT,TSLA,NVDA
```

### Force Specific Credentials

Override automatic selection:
```python
config = get_pipeline_config()
binance_config = config.get_binance_config()

# Override API key (not recommended)
binance_config.api_key = "custom_key"
```

## File Reference

### Created Files
- `src/api/pipeline_config.py` - Pipeline configuration module
- `src/api/main_pipeline_aware.py` - Reference for lifespan changes
- `test_pipeline_quick.py` - Quick configuration test
- `scripts/test_pipeline_switching.py` - Comprehensive test suite
- `PIPELINE_IMPLEMENTATION_SUMMARY.md` - Implementation details
- `PIPELINE_USAGE_GUIDE.md` - This file

### Modified Files
- `src/api/main.py` - Updated lifespan function
- `src/api/routers/pipeline.py` - Added validation endpoints
- `src/api/schemas.py` - Added validation response models
- `.env.example` - Added pipeline-specific credentials

## Next Steps

1. ✅ Test the implementation
   ```bash
   python test_pipeline_quick.py
   ```

2. ✅ Configure your environment
   - Copy `.env.example` to `.env`
   - Add your credentials
   - Choose your pipeline

3. ✅ Start the server
   ```bash
   ./start.sh
   ```

4. ✅ Validate via API
   ```bash
   curl http://localhost:8000/api/v1/pipelines/validate
   ```

5. ✅ Check the docs
   ```
   http://localhost:8000/docs
   ```
   Look for the "Pipelines" section!

## Summary

You now have **automatic credential switching** working! The system will:

- ✅ Use correct credentials per pipeline
- ✅ Configure services appropriately
- ✅ Isolate data in Redis
- ✅ Validate configuration
- ✅ Log everything clearly

Happy trading! 🚀
