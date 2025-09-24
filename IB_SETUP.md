# Interactive Brokers Setup Guide

## Prerequisites

✅ **You have**: IB account created and accepted
⏳ **Pending**: Funding (that's fine, you can use paper trading first)

## Step-by-Step Setup

### 1. Download TWS or IB Gateway

**Option A: Trader Workstation (TWS)**
- Download from: https://www.interactivebrokers.com/en/trading/tws-updateable-latest.php
- Full trading platform with GUI
- Ports: 7497 (paper), 7496 (live)

**Option B: IB Gateway (Recommended for API)**
- Download from: https://www.interactivebrokers.com/en/trading/ibgateway-latest.php
- Lightweight, API-focused
- Ports: 4002 (paper), 4001 (live)

### 2. Enable API Trading

1. **Login to TWS/Gateway**
2. **Go to**: Configure → API → Settings
3. **Enable API**: Check "Enable ActiveX and Socket Clients"
4. **Port**: 7497 (paper) or 7496 (live)
5. **Master API client ID**: 0 (allows other client IDs)
6. **Read-only API**: Uncheck (if you want to place orders)

### 3. Paper Trading Setup (Start Here)

1. **Login with paper trading account**
   - Username: Your IB username + "paper"
   - Password: Same as live account
2. **Virtual funding**: $1M automatically available
3. **Test everything** before going live

### 4. Test Your Connection

```bash
cd /mnt/d/Tiktok-analyzing
source .venv/bin/activate
python -c "
import asyncio
from core.ib_client import example_get_portfolio
asyncio.run(example_get_portfolio())
"
```

**Expected Output:**
```
Connected to IB on 127.0.0.1:7497
Account Info:
  NetLiquidation: {'value': '1000000.00', 'currency': 'USD'}
  TotalCashValue: {'value': '1000000.00', 'currency': 'USD'}
...
```

## What You Can Do Right Now (Paper Trading)

### Immediate Capabilities
- ✅ **Get real-time prices** for any US stock
- ✅ **Access historical data** (years of data)
- ✅ **Place paper trades** (buy/sell with virtual money)
- ✅ **Track portfolio** performance
- ✅ **Test strategies** risk-free

### Cost: **$0/month**
- IB API is completely free
- Paper trading unlimited
- No data fees for basic US stocks

## Integration with Your Current App

Let me show you how to extend your NVDA analyzer:

### Enhanced Multi-Stock Analyzer
```python
# In your app.py, add this:
import asyncio
from core.ib_client import create_ib_client

# Get live IB data instead of yfinance
async def get_ib_data(symbol):
    client = await create_ib_client(paper_trading=True)
    if client.connected:
        market_data = await client.get_market_data(symbol)
        hist_data = await client.get_historical_data(symbol, '1 Y', '1 day')
        client.disconnect()
        return market_data, hist_data
    return None, None
```

## Next Steps After Funding Arrives

### 1. Live Trading Setup
- Switch to live ports (7496/4001)
- Start with small position sizes
- Enable live data feeds if needed

### 2. Data Subscriptions (Optional)
**Real-time US Stock Data**:
- **Free**: 15-minute delayed quotes
- **$1.50/month**: Real-time Level I data
- **$4.95/month**: Real-time Level II data

### 3. Advanced Features
- **Options trading**: Full options chain access
- **International markets**: Stocks, forex, futures
- **Advanced orders**: Bracket orders, trailing stops

## Troubleshooting

### Connection Issues
```
Error: [Errno 111] Connection refused
```
**Solution**: Make sure TWS/Gateway is running and API is enabled

### Authentication Issues
```
Error: Not connected
```
**Solution**: Check username/password, ensure API settings are correct

### Port Issues
```
Error: [Errno 98] Address already in use
```
**Solution**: Check if another API client is using the same port

## Quick Start Example

Create this test file to verify everything works:

```python
# test_ib.py
import asyncio
from core.ib_client import create_ib_client

async def main():
    print("Testing IB connection...")

    client = await create_ib_client(paper_trading=True)

    if client.connected:
        print("✅ Connected successfully!")

        # Test account info
        account = client.get_account_info()
        net_liq = account.get('NetLiquidation', {}).get('value', 'N/A')
        print(f"💰 Account Value: ${net_liq}")

        # Test market data
        data = await client.get_market_data('AAPL')
        if data:
            print(f"📈 AAPL Price: ${data['last']}")

        client.disconnect()
        print("✅ Test completed successfully!")
    else:
        print("❌ Connection failed. Check TWS/Gateway is running.")

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:
```bash
python test_ib.py
```

## Ready to Go Live?

Once your funding arrives and you've tested thoroughly:

1. **Switch to live mode** in the IB client
2. **Start small** - test with $100-500 positions
3. **Use stop losses** on every trade
4. **Monitor closely** for the first week

Your IB setup gives you **institutional-grade** trading capabilities at essentially no cost!