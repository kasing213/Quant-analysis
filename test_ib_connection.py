"""
Test Interactive Brokers connection
Run this after setting up TWS/Gateway to verify everything works
"""

import asyncio
import sys
import traceback
from core.ib_client import create_ib_client

async def test_connection():
    """Test basic IB connection and functionality"""
    print("🔄 Testing Interactive Brokers connection...")
    print("⚠️  Make sure TWS or IB Gateway is running with API enabled!")
    print("📍 Paper trading port: 7497, Live trading port: 7496")
    print("-" * 60)

    try:
        # Try to connect (paper trading by default)
        client = await create_ib_client(paper_trading=True)

        if not client.connected:
            print("❌ Connection failed!")
            print("\nTroubleshooting:")
            print("1. Is TWS/Gateway running?")
            print("2. Is API enabled in TWS/Gateway settings?")
            print("3. Is port 7497 available?")
            print("4. Try restarting TWS/Gateway")
            return False

        print("✅ Successfully connected to Interactive Brokers!")
        print(f"🌐 Connected to: {client.host}:{client.port}")

        # Test account info
        print("\n📊 Testing account information...")
        account_info = client.get_account_info()

        if account_info:
            print("✅ Account data retrieved successfully!")

            # Show key account metrics
            key_metrics = ['NetLiquidation', 'TotalCashValue', 'AvailableFunds', 'BuyingPower']
            for metric in key_metrics:
                if metric in account_info:
                    value = account_info[metric]['value']
                    currency = account_info[metric]['currency']
                    print(f"  💰 {metric}: {value} {currency}")
        else:
            print("⚠️  No account data available")

        # Test portfolio
        print("\n📈 Testing portfolio data...")
        portfolio = client.get_portfolio()
        positions = client.get_positions()

        print(f"✅ Portfolio items: {len(portfolio)}")
        print(f"✅ Positions: {len(positions)}")

        if portfolio:
            print("  📋 Current positions:")
            for pos in portfolio:
                print(f"    {pos['symbol']}: {pos['position']} @ ${pos['marketPrice']:.2f}")
        else:
            print("  📝 No positions found (normal for new accounts)")

        # Test market data
        print("\n📡 Testing market data...")
        test_symbols = ['AAPL', 'SPY', 'NVDA']

        for symbol in test_symbols:
            try:
                market_data = await client.get_market_data(symbol)
                if market_data and market_data['last'] > 0:
                    print(f"  ✅ {symbol}: ${market_data['last']:.2f} (Live data working!)")
                else:
                    print(f"  ⚠️  {symbol}: No data (may need real-time data subscription)")
            except Exception as e:
                print(f"  ❌ {symbol}: Error - {e}")

        # Test historical data
        print("\n📈 Testing historical data...")
        try:
            hist_data = await client.get_historical_data('AAPL', '5 D', '1 day')
            if not hist_data.empty:
                print(f"  ✅ Historical data: {len(hist_data)} bars retrieved")
                print(f"  📅 Date range: {hist_data.index[0].date()} to {hist_data.index[-1].date()}")
                print(f"  💲 Latest close: ${hist_data['close'].iloc[-1]:.2f}")
            else:
                print("  ⚠️  No historical data retrieved")
        except Exception as e:
            print(f"  ❌ Historical data error: {e}")

        # Test open orders
        print("\n📋 Testing order information...")
        open_orders = client.get_open_orders()
        print(f"✅ Open orders: {len(open_orders)}")

        if open_orders:
            for order in open_orders:
                print(f"  Order {order['orderId']}: {order['action']} {order['quantity']} {order['symbol']}")

        # Disconnect
        client.disconnect()
        print("\n✅ Test completed successfully!")
        print("\n🎉 Your IB integration is ready to use!")

        return True

    except Exception as e:
        print(f"\n❌ Connection test failed: {e}")
        print("\nFull error details:")
        traceback.print_exc()

        print("\n🔧 Troubleshooting steps:")
        print("1. Download and install TWS or IB Gateway")
        print("2. Login with your IB credentials")
        print("3. Go to Configure → API → Settings")
        print("4. Enable 'ActiveX and Socket Clients'")
        print("5. Set port to 7497 for paper trading")
        print("6. Uncheck 'Read-only API'")
        print("7. Click OK and restart this test")

        return False

def main():
    """Main test function"""
    print("Interactive Brokers API Test")
    print("=" * 60)

    # Check if event loop is already running (in Jupyter/IPython)
    try:
        # Try to get the current event loop
        loop = asyncio.get_running_loop()
        print("⚠️  Running in existing event loop (Jupyter/IPython detected)")
        # Create a new task in the existing loop
        import nest_asyncio
        nest_asyncio.apply()
        result = asyncio.run(test_connection())
    except RuntimeError:
        # No event loop running, safe to use asyncio.run()
        result = asyncio.run(test_connection())

    if result:
        print("\n🚀 Next steps:")
        print("1. Run your enhanced NVDA analyzer: streamlit run app.py")
        print("2. Try the multi-stock portfolio tracker")
        print("3. Test paper trading with small positions")
    else:
        print("\n🔴 Please fix the connection issues above before proceeding")

if __name__ == "__main__":
    main()