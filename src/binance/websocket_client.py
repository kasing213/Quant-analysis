"""
Binance WebSocket Client
Streams real-time market data without authentication (public streams)
"""

import asyncio
import json
import logging
from typing import Dict, List, Callable, Optional
from datetime import datetime
import websockets
from collections import deque

# Import metrics for monitoring WebSocket reconnections
try:
    from src.api.metrics import record_websocket_reconnection, update_websocket_connection_status
except ImportError:
    # Graceful fallback if metrics module not available
    def record_websocket_reconnection(source: str, success: bool):
        pass
    def update_websocket_connection_status(source: str, connected: bool):
        pass

logger = logging.getLogger(__name__)


class BinanceWebSocketClient:
    """
    Real-time Binance WebSocket client for public market data streams.
    No API keys required for public streams!

    Supports:
    - Kline/Candlestick streams (for OHLCV data)
    - Ticker streams (24hr price stats)
    - Trade streams (individual trades)
    - Book ticker (best bid/ask)
    """

    def __init__(self, testnet: bool = True):
        self.testnet = testnet
        self.base_url = "wss://stream.testnet.binance.vision/ws" if testnet else "wss://stream.binance.com:9443/ws"
        self.ws = None
        self.running = False
        self.callbacks = {}
        self.data_buffer = {}  # Store recent candles for each symbol
        self.buffer_size = 200  # Keep 200 candles for RSI calculation

        # Reconnection settings
        self.auto_reconnect = True
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_attempts = 0  # 0 = infinite
        self.reconnect_attempts = 0
        self.subscribed_streams = []  # Track subscriptions for reconnection

    async def connect(self):
        """Connect to Binance WebSocket"""
        try:
            self.ws = await websockets.connect(self.base_url)
            self.running = True
            logger.info(f"Connected to Binance WebSocket ({'testnet' if self.testnet else 'production'})")
            # Update metrics to show connection is active
            update_websocket_connection_status(source='binance', connected=True)
        except Exception as e:
            logger.error(f"Failed to connect to Binance WebSocket: {e}")
            raise

    async def subscribe_kline(self, symbol: str, interval: str = "1m", callback: Optional[Callable] = None):
        """
        Subscribe to kline/candlestick stream for a symbol.

        Args:
            symbol: Trading pair (e.g., 'btcusdt')
            interval: Kline interval (1m, 3m, 5m, 15m, 30m, 1h, 4h, 1d)
            callback: Optional callback function to handle kline data
        """
        stream = f"{symbol.lower()}@kline_{interval}"

        if not self.ws:
            await self.connect()

        # Subscribe to stream
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": [stream],
            "id": 1
        }

        await self.ws.send(json.dumps(subscribe_msg))

        # Initialize data buffer for this symbol
        if symbol not in self.data_buffer:
            self.data_buffer[symbol] = deque(maxlen=self.buffer_size)

        if callback:
            self.callbacks[stream] = callback

        # Track subscription for reconnection
        if stream not in self.subscribed_streams:
            self.subscribed_streams.append(stream)

        logger.info(f"Subscribed to {stream}")

    async def subscribe_ticker(self, symbol: str, callback: Optional[Callable] = None):
        """Subscribe to 24hr ticker stream"""
        stream = f"{symbol.lower()}@ticker"

        if not self.ws:
            await self.connect()

        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": [stream],
            "id": 1
        }

        await self.ws.send(json.dumps(subscribe_msg))

        if callback:
            self.callbacks[stream] = callback

        logger.info(f"Subscribed to {stream}")

    async def subscribe_trade(self, symbol: str, callback: Optional[Callable] = None):
        """Subscribe to trade stream (individual trades)"""
        stream = f"{symbol.lower()}@trade"

        if not self.ws:
            await self.connect()

        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": [stream],
            "id": 1
        }

        await self.ws.send(json.dumps(subscribe_msg))

        if callback:
            self.callbacks[stream] = callback

        logger.info(f"Subscribed to {stream}")

    async def subscribe_book_ticker(self, symbol: str, callback: Optional[Callable] = None):
        """Subscribe to book ticker (best bid/ask)"""
        stream = f"{symbol.lower()}@bookTicker"

        if not self.ws:
            await self.connect()

        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": [stream],
            "id": 1
        }

        await self.ws.send(json.dumps(subscribe_msg))

        if callback:
            self.callbacks[stream] = callback

        logger.info(f"Subscribed to {stream}")

    async def listen(self):
        """Listen for WebSocket messages and dispatch to callbacks with auto-reconnection"""
        while self.auto_reconnect and self.running:
            try:
                async for message in self.ws:
                    data = json.loads(message)

                    # Reset reconnect counter on successful message
                    self.reconnect_attempts = 0

                    # Handle kline data
                    if 'e' in data and data['e'] == 'kline':
                        await self._handle_kline(data)

                    # Handle ticker data
                    elif 'e' in data and data['e'] == '24hrTicker':
                        await self._handle_ticker(data)

                    # Handle trade data
                    elif 'e' in data and data['e'] == 'trade':
                        await self._handle_trade(data)

                    # Handle book ticker
                    elif 'e' in data and data.get('e') == 'bookTicker':
                        await self._handle_book_ticker(data)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                if self.auto_reconnect and self.running:
                    await self._reconnect()
                else:
                    self.running = False
                    break

            except Exception as e:
                logger.error(f"Error in WebSocket listener: {e}")
                if self.auto_reconnect and self.running:
                    await self._reconnect()
                else:
                    self.running = False
                    break

    async def _reconnect(self):
        """Attempt to reconnect to WebSocket with exponential backoff"""
        self.reconnect_attempts += 1

        if self.max_reconnect_attempts > 0 and self.reconnect_attempts > self.max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self.max_reconnect_attempts}) reached, stopping")
            self.running = False
            # Record failed reconnection (max retries reached)
            record_websocket_reconnection(source='binance', success=False)
            return

        # Calculate backoff delay (exponential with max cap at 60s)
        delay = min(self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), 60)
        logger.info(f"Attempting reconnection #{self.reconnect_attempts} in {delay}s...")
        await asyncio.sleep(delay)

        try:
            # Close old connection if exists
            if self.ws:
                try:
                    await self.ws.close()
                except:
                    pass

            # Reconnect
            await self.connect()
            logger.info("WebSocket reconnected successfully")

            # Resubscribe to all streams
            await self._resubscribe_all()

            # Record successful reconnection
            record_websocket_reconnection(source='binance', success=True)

        except Exception as e:
            logger.error(f"Reconnection attempt #{self.reconnect_attempts} failed: {e}")
            # Note: We don't record failure here since we'll retry
            # Only record failure when max retries reached (see above)

    async def _resubscribe_all(self):
        """Resubscribe to all previously subscribed streams"""
        if not self.subscribed_streams:
            logger.info("No streams to resubscribe")
            return

        logger.info(f"Resubscribing to {len(self.subscribed_streams)} streams...")

        for stream in self.subscribed_streams:
            try:
                subscribe_msg = {
                    "method": "SUBSCRIBE",
                    "params": [stream],
                    "id": 1
                }
                await self.ws.send(json.dumps(subscribe_msg))
                logger.info(f"Resubscribed to {stream}")
            except Exception as e:
                logger.error(f"Failed to resubscribe to {stream}: {e}")

    async def _handle_kline(self, data: Dict):
        """Process kline data and store in buffer"""
        kline = data['k']
        symbol = data['s']

        # Parse kline data
        candle = {
            'timestamp': datetime.fromtimestamp(kline['t'] / 1000),
            'open': float(kline['o']),
            'high': float(kline['h']),
            'low': float(kline['l']),
            'close': float(kline['c']),
            'volume': float(kline['v']),
            'is_closed': kline['x']  # Is this kline closed?
        }

        # Only store closed candles in buffer
        if candle['is_closed']:
            if symbol in self.data_buffer:
                self.data_buffer[symbol].append(candle)
                logger.debug(f"Stored candle for {symbol}: {candle['close']}")

        # Call registered callback
        stream = f"{symbol.lower()}@kline_{kline['i']}"
        if stream in self.callbacks:
            await self.callbacks[stream](candle)

    async def _handle_ticker(self, data: Dict):
        """Process 24hr ticker data"""
        ticker = {
            'symbol': data['s'],
            'price_change': float(data['p']),
            'price_change_percent': float(data['P']),
            'last_price': float(data['c']),
            'volume': float(data['v']),
            'high': float(data['h']),
            'low': float(data['l']),
            'timestamp': datetime.fromtimestamp(data['E'] / 1000)
        }

        stream = f"{data['s'].lower()}@ticker"
        if stream in self.callbacks:
            await self.callbacks[stream](ticker)

    async def _handle_trade(self, data: Dict):
        """Process trade data"""
        trade = {
            'symbol': data['s'],
            'price': float(data['p']),
            'quantity': float(data['q']),
            'is_buyer_maker': data['m'],
            'timestamp': datetime.fromtimestamp(data['T'] / 1000)
        }

        stream = f"{data['s'].lower()}@trade"
        if stream in self.callbacks:
            await self.callbacks[stream](trade)

    async def _handle_book_ticker(self, data: Dict):
        """Process book ticker data (best bid/ask)"""
        book_ticker = {
            'symbol': data['s'],
            'best_bid': float(data['b']),
            'best_bid_qty': float(data['B']),
            'best_ask': float(data['a']),
            'best_ask_qty': float(data['A']),
            'timestamp': datetime.now()
        }

        stream = f"{data['s'].lower()}@bookTicker"
        if stream in self.callbacks:
            await self.callbacks[stream](book_ticker)

    def get_candles(self, symbol: str, count: int = None) -> List[Dict]:
        """
        Get stored candles for a symbol

        Args:
            symbol: Trading pair
            count: Number of recent candles (default: all)

        Returns:
            List of candle dictionaries
        """
        if symbol not in self.data_buffer:
            return []

        candles = list(self.data_buffer[symbol])
        if count:
            return candles[-count:]
        return candles

    async def unsubscribe(self, stream: str):
        """Unsubscribe from a stream"""
        unsubscribe_msg = {
            "method": "UNSUBSCRIBE",
            "params": [stream],
            "id": 1
        }

        await self.ws.send(json.dumps(unsubscribe_msg))

        if stream in self.callbacks:
            del self.callbacks[stream]

        logger.info(f"Unsubscribed from {stream}")

    async def close(self):
        """Close WebSocket connection and disable auto-reconnect"""
        self.running = False
        self.auto_reconnect = False  # Disable reconnection
        if self.ws:
            await self.ws.close()
            logger.info("WebSocket connection closed")
            # Update metrics to show connection is inactive
            update_websocket_connection_status(source='binance', connected=False)

    def is_connected(self) -> bool:
        """Check if WebSocket is connected and running"""
        return self.ws is not None and self.running and not self.ws.closed

    def get_connection_status(self) -> dict:
        """Get detailed connection status for monitoring"""
        return {
            'connected': self.is_connected(),
            'running': self.running,
            'auto_reconnect': self.auto_reconnect,
            'reconnect_attempts': self.reconnect_attempts,
            'subscribed_streams': len(self.subscribed_streams),
            'streams': self.subscribed_streams,
            'active_symbols': list(self.data_buffer.keys())
        }


# Example usage
async def example_usage():
    """Example of how to use the WebSocket client"""

    # Create client (testnet for safety)
    client = BinanceWebSocketClient(testnet=True)

    # Define callback for kline data
    async def on_kline(candle):
        print(f"New candle: {candle['timestamp']} - Close: {candle['close']}")

    # Subscribe to BTC/USDT 1-minute klines
    await client.subscribe_kline("BTCUSDT", "1m", callback=on_kline)

    # Listen for messages
    await client.listen()


if __name__ == "__main__":
    # Run example
    asyncio.run(example_usage())
