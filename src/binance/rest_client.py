"""
Binance REST API Client
Handles order execution, account info, and trading operations
"""

import hashlib
import hmac
import time
from typing import Dict, Optional, List
from urllib.parse import urlencode
import aiohttp
import logging

logger = logging.getLogger(__name__)


class BinanceRESTClient:
    """
    Binance REST API client for trading operations.

    Features:
    - Order placement (market, limit, stop-loss)
    - Position management
    - Account balance queries
    - Order history
    - Test mode for paper trading
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
        test_mode: bool = True
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.test_mode = test_mode  # Paper trading mode

        # API endpoints
        if testnet:
            self.base_url = "https://testnet.binance.vision/api"
        else:
            self.base_url = "https://api.binance.com/api"

        self.session = None

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    def _generate_signature(self, params: Dict) -> str:
        """Generate HMAC SHA256 signature"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def _request(
        self,
        method: str,
        endpoint: str,
        signed: bool = False,
        **params
    ) -> Dict:
        """Make HTTP request to Binance API"""

        url = f"{self.base_url}{endpoint}"
        headers = {"X-MBX-APIKEY": self.api_key}

        # Add timestamp for signed requests
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)

        try:
            async with self.session.request(
                method,
                url,
                headers=headers,
                params=params if method == 'GET' else None,
                json=params if method == 'POST' else None
            ) as response:
                data = await response.json()

                if response.status != 200:
                    logger.error(f"API Error: {data}")
                    raise Exception(f"Binance API Error: {data.get('msg', 'Unknown error')}")

                return data

        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise

    async def get_account_info(self) -> Dict:
        """Get account information including balances"""
        return await self._request('GET', '/v3/account', signed=True)

    async def get_balance(self, asset: str = 'USDT') -> float:
        """Get balance for specific asset"""
        account = await self.get_account_info()

        for balance in account['balances']:
            if balance['asset'] == asset:
                return float(balance['free'])

        return 0.0

    async def create_market_order(
        self,
        symbol: str,
        side: str,  # 'BUY' or 'SELL'
        quantity: float
    ) -> Dict:
        """
        Create market order

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            side: 'BUY' or 'SELL'
            quantity: Order quantity

        Returns:
            Order response dict
        """

        if self.test_mode:
            logger.info(f"[TEST MODE] Market {side} order: {quantity} {symbol}")
            return {
                'orderId': int(time.time() * 1000),
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': quantity,
                'status': 'FILLED',
                'test_mode': True
            }

        params = {
            'symbol': symbol,
            'side': side,
            'type': 'MARKET',
            'quantity': quantity
        }

        return await self._request('POST', '/v3/order', signed=True, **params)

    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        time_in_force: str = 'GTC'  # Good Till Cancel
    ) -> Dict:
        """Create limit order"""

        if self.test_mode:
            logger.info(f"[TEST MODE] Limit {side} order: {quantity} {symbol} @ {price}")
            return {
                'orderId': int(time.time() * 1000),
                'symbol': symbol,
                'side': side,
                'type': 'LIMIT',
                'quantity': quantity,
                'price': price,
                'status': 'NEW',
                'test_mode': True
            }

        params = {
            'symbol': symbol,
            'side': side,
            'type': 'LIMIT',
            'quantity': quantity,
            'price': price,
            'timeInForce': time_in_force
        }

        return await self._request('POST', '/v3/order', signed=True, **params)

    async def create_stop_loss_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_price: float,
        limit_price: Optional[float] = None
    ) -> Dict:
        """Create stop-loss order"""

        if self.test_mode:
            logger.info(f"[TEST MODE] Stop-loss {side} order: {quantity} {symbol} @ {stop_price}")
            return {
                'orderId': int(time.time() * 1000),
                'symbol': symbol,
                'side': side,
                'type': 'STOP_LOSS_LIMIT',
                'quantity': quantity,
                'stopPrice': stop_price,
                'status': 'NEW',
                'test_mode': True
            }

        order_type = 'STOP_LOSS_LIMIT' if limit_price else 'STOP_LOSS'

        params = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'quantity': quantity,
            'stopPrice': stop_price
        }

        if limit_price:
            params['price'] = limit_price
            params['timeInForce'] = 'GTC'

        return await self._request('POST', '/v3/order', signed=True, **params)

    async def cancel_order(self, symbol: str, order_id: int) -> Dict:
        """Cancel an order"""

        if self.test_mode:
            logger.info(f"[TEST MODE] Cancel order: {order_id} for {symbol}")
            return {
                'orderId': order_id,
                'symbol': symbol,
                'status': 'CANCELED',
                'test_mode': True
            }

        params = {
            'symbol': symbol,
            'orderId': order_id
        }

        return await self._request('DELETE', '/v3/order', signed=True, **params)

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open orders"""
        params = {}
        if symbol:
            params['symbol'] = symbol

        return await self._request('GET', '/v3/openOrders', signed=True, **params)

    async def get_order_history(
        self,
        symbol: str,
        limit: int = 500
    ) -> List[Dict]:
        """Get order history"""
        params = {
            'symbol': symbol,
            'limit': limit
        }

        return await self._request('GET', '/v3/allOrders', signed=True, **params)

    async def get_current_price(self, symbol: str) -> float:
        """Get current price for symbol"""
        data = await self._request('GET', '/v3/ticker/price', symbol=symbol)
        return float(data['price'])

    async def get_exchange_info(self, symbol: Optional[str] = None) -> Dict:
        """Get exchange trading rules and symbol info"""
        params = {}
        if symbol:
            params['symbol'] = symbol

        return await self._request('GET', '/v3/exchangeInfo', **params)

    async def get_symbol_info(self, symbol: str) -> Dict:
        """Get specific symbol trading rules"""
        exchange_info = await self.get_exchange_info(symbol=symbol)

        for symbol_info in exchange_info['symbols']:
            if symbol_info['symbol'] == symbol:
                return symbol_info

        raise ValueError(f"Symbol {symbol} not found")


# Example usage
async def example():
    """Example of using the REST client"""

    # Initialize client (testnet + test mode for safety)
    async with BinanceRESTClient(
        api_key="your_api_key",
        api_secret="your_api_secret",
        testnet=True,
        test_mode=True  # Paper trading
    ) as client:

        # Get account balance
        balance = await client.get_balance('USDT')
        print(f"USDT Balance: {balance}")

        # Get current BTC price
        price = await client.get_current_price('BTCUSDT')
        print(f"BTC Price: ${price}")

        # Create market buy order (test mode)
        order = await client.create_market_order(
            symbol='BTCUSDT',
            side='BUY',
            quantity=0.001
        )
        print(f"Order: {order}")

        # Get open orders
        open_orders = await client.get_open_orders('BTCUSDT')
        print(f"Open orders: {len(open_orders)}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example())
