"""
Interactive Brokers Client Integration
Handles connection, data feeds, and trading operations with IB
"""

import asyncio
import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Handle event loop issue in Streamlit
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from ib_insync import IB, Stock, Contract, MarketOrder, LimitOrder, util
from ib_insync.objects import PortfolioItem, Position

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IBClient:
    def __init__(self, host='127.0.0.1', port=7497, client_id=1):
        """
        Initialize IB client
        port=7497 for TWS, port=4002 for IB Gateway paper trading
        port=7496 for TWS live, port=4001 for IB Gateway live
        """
        self.ib = IB()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connected = False

    async def connect(self):
        """Connect to IB TWS or Gateway"""
        try:
            await self.ib.connectAsync(self.host, self.port, clientId=self.client_id)
            self.connected = True
            logger.info(f"Connected to IB on {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to IB: {e}")
            return False

    def disconnect(self):
        """Disconnect from IB"""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
            logger.info("Disconnected from IB")

    def get_account_info(self) -> Dict:
        """Get account summary"""
        if not self.connected:
            return {}

        account_values = self.ib.accountSummary()
        info = {}
        for item in account_values:
            info[item.tag] = {
                'value': item.value,
                'currency': item.currency
            }
        return info

    def get_portfolio(self) -> List[Dict]:
        """Get current portfolio positions"""
        if not self.connected:
            return []

        portfolio_items = self.ib.portfolio()
        positions = []

        for item in portfolio_items:
            positions.append({
                'symbol': item.contract.symbol,
                'secType': item.contract.secType,
                'exchange': item.contract.exchange,
                'position': item.position,
                'marketPrice': item.marketPrice,
                'marketValue': item.marketValue,
                'averageCost': item.averageCost,
                'unrealizedPNL': item.unrealizedPNL,
                'realizedPNL': item.realizedPNL,
                'currency': item.contract.currency
            })

        return positions

    def get_positions(self) -> List[Dict]:
        """Get positions (alternative method)"""
        if not self.connected:
            return []

        positions = self.ib.positions()
        pos_list = []

        for pos in positions:
            pos_list.append({
                'account': pos.account,
                'symbol': pos.contract.symbol,
                'position': pos.position,
                'avgCost': pos.avgCost
            })

        return pos_list

    async def get_market_data(self, symbol: str, exchange: str = 'SMART',
                            currency: str = 'USD') -> Optional[Dict]:
        """Get real-time market data for a symbol"""
        if not self.connected:
            return None

        contract = Stock(symbol, exchange, currency)

        # Qualify the contract
        qualified_contracts = await self.ib.qualifyContractsAsync(contract)
        if not qualified_contracts:
            logger.error(f"Could not qualify contract for {symbol}")
            return None

        contract = qualified_contracts[0]

        # Request market data
        ticker = self.ib.reqMktData(contract)
        await asyncio.sleep(1)  # Wait for data

        if ticker.last != ticker.last:  # Check for NaN
            logger.warning(f"No market data available for {symbol}")
            return None

        return {
            'symbol': symbol,
            'last': ticker.last,
            'bid': ticker.bid,
            'ask': ticker.ask,
            'volume': ticker.volume,
            'high': ticker.high,
            'low': ticker.low,
            'close': ticker.close,
            'timestamp': datetime.now()
        }

    async def get_historical_data(self, symbol: str, duration: str = '1 Y',
                                bar_size: str = '1 day', exchange: str = 'SMART',
                                currency: str = 'USD') -> pd.DataFrame:
        """
        Get historical data
        duration: '1 Y', '6 M', '1 M', etc.
        bar_size: '1 day', '1 hour', '5 mins', etc.
        """
        if not self.connected:
            return pd.DataFrame()

        contract = Stock(symbol, exchange, currency)
        qualified_contracts = await self.ib.qualifyContractsAsync(contract)

        if not qualified_contracts:
            logger.error(f"Could not qualify contract for {symbol}")
            return pd.DataFrame()

        contract = qualified_contracts[0]

        try:
            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True
            )

            if not bars:
                return pd.DataFrame()

            # Convert to DataFrame
            df = util.df(bars)
            df['symbol'] = symbol
            return df

        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {e}")
            return pd.DataFrame()

    async def place_market_order(self, symbol: str, quantity: int,
                               action: str = 'BUY', exchange: str = 'SMART',
                               currency: str = 'USD') -> Optional[Dict]:
        """
        Place a market order
        action: 'BUY' or 'SELL'
        """
        if not self.connected:
            return None

        contract = Stock(symbol, exchange, currency)
        order = MarketOrder(action, abs(quantity))

        try:
            trade = self.ib.placeOrder(contract, order)
            logger.info(f"Placed {action} market order for {quantity} shares of {symbol}")

            return {
                'orderId': trade.order.orderId,
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'orderType': 'MKT',
                'status': trade.orderStatus.status,
                'timestamp': datetime.now()
            }

        except Exception as e:
            logger.error(f"Error placing market order: {e}")
            return None

    async def place_limit_order(self, symbol: str, quantity: int, limit_price: float,
                              action: str = 'BUY', exchange: str = 'SMART',
                              currency: str = 'USD') -> Optional[Dict]:
        """Place a limit order"""
        if not self.connected:
            return None

        contract = Stock(symbol, exchange, currency)
        order = LimitOrder(action, abs(quantity), limit_price)

        try:
            trade = self.ib.placeOrder(contract, order)
            logger.info(f"Placed {action} limit order for {quantity} shares of {symbol} at ${limit_price}")

            return {
                'orderId': trade.order.orderId,
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'limitPrice': limit_price,
                'orderType': 'LMT',
                'status': trade.orderStatus.status,
                'timestamp': datetime.now()
            }

        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            return None

    def get_open_orders(self) -> List[Dict]:
        """Get all open orders"""
        if not self.connected:
            return []

        orders = self.ib.openOrders()
        order_list = []

        for trade in orders:
            order_list.append({
                'orderId': trade.order.orderId,
                'symbol': trade.contract.symbol,
                'action': trade.order.action,
                'quantity': trade.order.totalQuantity,
                'orderType': trade.order.orderType,
                'status': trade.orderStatus.status,
                'lmtPrice': getattr(trade.order, 'lmtPrice', None),
                'auxPrice': getattr(trade.order, 'auxPrice', None)
            })

        return order_list

    def cancel_order(self, order_id: int) -> bool:
        """Cancel an open order"""
        if not self.connected:
            return False

        try:
            self.ib.cancelOrder(order_id)
            logger.info(f"Cancelled order {order_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

# Utility functions for easy integration
async def create_ib_client(paper_trading=True) -> IBClient:
    """
    Create and connect IB client
    paper_trading=True uses paper trading ports (7497 for TWS, 4002 for Gateway)
    paper_trading=False uses live trading ports (7496 for TWS, 4001 for Gateway)
    """
    port = 7497 if paper_trading else 7496  # TWS ports
    # port = 4002 if paper_trading else 4001  # Gateway ports (uncomment if using Gateway)

    client = IBClient(port=port)
    await client.connect()
    return client

def sync_create_ib_client(paper_trading=True) -> IBClient:
    """Synchronous wrapper for creating IB client"""
    return asyncio.run(create_ib_client(paper_trading))

# Example usage functions
async def example_get_portfolio():
    """Example: Get portfolio information"""
    client = await create_ib_client(paper_trading=True)

    if client.connected:
        account_info = client.get_account_info()
        portfolio = client.get_portfolio()
        positions = client.get_positions()

        print("Account Info:")
        for key, value in account_info.items():
            print(f"  {key}: {value}")

        print("\nPortfolio:")
        for pos in portfolio:
            print(f"  {pos['symbol']}: {pos['position']} @ ${pos['marketPrice']}")

        client.disconnect()

async def example_get_data():
    """Example: Get market data"""
    client = await create_ib_client(paper_trading=True)

    if client.connected:
        # Real-time data
        market_data = await client.get_market_data('AAPL')
        print("Real-time AAPL:", market_data)

        # Historical data
        hist_data = await client.get_historical_data('AAPL', '1 M', '1 day')
        print("Historical data shape:", hist_data.shape)
        print(hist_data.head())

        client.disconnect()

if __name__ == "__main__":
    # Run examples
    print("Testing IB connection...")
    asyncio.run(example_get_portfolio())
    # asyncio.run(example_get_data())