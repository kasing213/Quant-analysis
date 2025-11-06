"""
Binance Data Manager
Centralized data pipeline: WebSocket → Redis → Bots

Features:
- Automatic reconnection with exponential backoff
- Redis connection resilience
- WebSocket recovery handling
- Health monitoring
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
import redis.asyncio as redis
import pandas as pd
from .websocket_client import BinanceWebSocketClient

logger = logging.getLogger(__name__)

# Prometheus metrics (optional)
try:
    from src.api.metrics import (
        record_redis_operation,
        record_market_data_update,
        REDIS_CONNECTION_ERRORS,
        MARKET_DATA_LAG
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.debug("Metrics module not available")


class ConnectionError(Exception):
    """Raised when connection attempts fail"""
    pass


class BinanceDataManager:
    """
    Centralized data manager for multiple trading bots.

    Architecture:
    - Single WebSocket connection per trading pair
    - Real-time data stored in Redis
    - All bots read from shared Redis cache
    - Handles 10+ bots efficiently
    """

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_password: Optional[str] = None,
        redis_db: int = 0,
        testnet: bool = True,
        max_retries: int = 5,
        base_backoff: float = 1.0,
        max_backoff: float = 60.0
    ):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_password = redis_password
        self.redis_db = redis_db
        self.testnet = testnet

        # Retry configuration
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff

        self.ws_client = BinanceWebSocketClient(testnet=testnet)
        self.redis_client = None
        self.active_symbols = set()

        # Connection state tracking
        self._redis_connected = False
        self._ws_connected = False
        self._shutdown = False
        self._reconnect_task = None

    async def _exponential_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay"""
        delay = min(self.base_backoff * (2 ** attempt), self.max_backoff)
        # Add jitter to prevent thundering herd
        import random
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter

    async def _connect_redis(self) -> bool:
        """Connect to Redis with retry logic"""
        for attempt in range(self.max_retries):
            try:
                if self._shutdown:
                    logger.info("Shutdown requested, aborting Redis connection")
                    return False

                logger.info(f"Connecting to Redis (attempt {attempt + 1}/{self.max_retries})...")

                self.redis_client = await redis.Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    password=self.redis_password,
                    db=self.redis_db,
                    decode_responses=True,
                    socket_connect_timeout=5.0,
                    socket_timeout=5.0,
                    retry_on_timeout=True
                )

                # Verify connection
                await self.redis_client.ping()
                self._redis_connected = True
                logger.info("Successfully connected to Redis")
                return True

            except (redis.ConnectionError, redis.TimeoutError, OSError) as e:
                logger.warning(f"Redis connection attempt {attempt + 1} failed: {e}")

                if attempt < self.max_retries - 1:
                    delay = await self._exponential_backoff(attempt)
                    logger.info(f"Retrying in {delay:.2f}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max retries reached for Redis connection")
                    self._redis_connected = False
                    return False

            except Exception as e:
                logger.error(f"Unexpected error connecting to Redis: {e}")
                self._redis_connected = False
                return False

        return False

    async def _connect_websocket(self) -> bool:
        """Connect to WebSocket with retry logic"""
        for attempt in range(self.max_retries):
            try:
                if self._shutdown:
                    logger.info("Shutdown requested, aborting WebSocket connection")
                    return False

                logger.info(f"Connecting to Binance WebSocket (attempt {attempt + 1}/{self.max_retries})...")

                await self.ws_client.connect()
                self._ws_connected = True
                logger.info("Successfully connected to Binance WebSocket")
                return True

            except Exception as e:
                logger.warning(f"WebSocket connection attempt {attempt + 1} failed: {e}")

                if attempt < self.max_retries - 1:
                    delay = await self._exponential_backoff(attempt)
                    logger.info(f"Retrying in {delay:.2f}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max retries reached for WebSocket connection")
                    self._ws_connected = False
                    return False

        return False

    async def connect(self):
        """Initialize connections to WebSocket and Redis with retry logic"""
        # Connect to Redis
        redis_ok = await self._connect_redis()
        if not redis_ok:
            raise ConnectionError("Failed to connect to Redis after all retries")

        # Connect to Binance WebSocket
        ws_ok = await self._connect_websocket()
        if not ws_ok:
            raise ConnectionError("Failed to connect to Binance WebSocket after all retries")

        logger.info("Data Manager fully connected to Redis and Binance WebSocket")

    async def subscribe_symbol(self, symbol: str, interval: str = "1m"):
        """
        Subscribe to a trading pair and start streaming data to Redis

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            interval: Candle interval (1m, 5m, 15m, etc.)
        """
        if symbol in self.active_symbols:
            logger.info(f"{symbol} already subscribed")
            return

        # Define callback to store data in Redis
        async def store_candle(candle: Dict):
            await self._store_candle_to_redis(symbol, candle, interval)

        # Subscribe to kline stream
        await self.ws_client.subscribe_kline(symbol, interval, callback=store_candle)
        self.active_symbols.add(symbol)

        logger.info(f"Subscribed to {symbol} {interval} candles")

    async def _store_candle_to_redis(self, symbol: str, candle: Dict, interval: str):
        """Store candle data to Redis with error handling and reconnection"""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Check if Redis is connected
                if not self._redis_connected:
                    logger.warning("Redis not connected, attempting reconnection...")
                    reconnected = await self._connect_redis()
                    if not reconnected:
                        logger.error("Failed to reconnect to Redis, skipping candle storage")
                        return

                # Redis key format: "candles:BTCUSDT:1m"
                redis_key = f"candles:{symbol}:{interval}"

                # Convert candle to JSON
                candle_data = {
                    'timestamp': candle['timestamp'].isoformat(),
                    'open': candle['open'],
                    'high': candle['high'],
                    'low': candle['low'],
                    'close': candle['close'],
                    'volume': candle['volume'],
                    'is_closed': candle['is_closed']
                }

                # Store in Redis list (FIFO, keep last 200)
                await self.redis_client.lpush(redis_key, json.dumps(candle_data))
                await self.redis_client.ltrim(redis_key, 0, 199)  # Keep only 200 candles

                # Also store latest price separately for quick access
                latest_price_key = f"price:{symbol}"
                await self.redis_client.set(latest_price_key, candle['close'])

                # Record metrics
                if METRICS_AVAILABLE:
                    record_redis_operation("set", "success")
                    record_market_data_update(symbol, "binance")

                logger.debug(f"Stored {symbol} candle in Redis: {candle['close']}")
                return  # Success, exit retry loop

            except (redis.ConnectionError, redis.TimeoutError) as e:
                logger.warning(f"Redis connection error on attempt {attempt + 1}/{max_attempts}: {e}")
                self._redis_connected = False

                # Record error metrics
                if METRICS_AVAILABLE:
                    record_redis_operation("set", "error")
                    REDIS_CONNECTION_ERRORS.inc()

                if attempt < max_attempts - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))  # Simple backoff
                else:
                    logger.error(f"Failed to store candle after {max_attempts} attempts")

            except Exception as e:
                logger.error(f"Unexpected error storing candle to Redis: {e}")
                return  # Don't retry on unexpected errors

    async def get_candles(self, symbol: str, interval: str = "1m", count: int = 200) -> pd.DataFrame:
        """
        Get candles from Redis as a pandas DataFrame with retry logic

        Args:
            symbol: Trading pair
            interval: Candle interval
            count: Number of candles to retrieve

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Check Redis connection
                if not self._redis_connected:
                    logger.warning("Redis not connected, attempting reconnection...")
                    reconnected = await self._connect_redis()
                    if not reconnected:
                        logger.error("Failed to reconnect to Redis")
                        return pd.DataFrame()

                redis_key = f"candles:{symbol}:{interval}"

                # Get candles from Redis
                candles_json = await self.redis_client.lrange(redis_key, 0, count - 1)

                # Record successful Redis get operation
                if METRICS_AVAILABLE:
                    record_redis_operation("get", "success")

                if not candles_json:
                    logger.warning(f"No candles found in Redis for {symbol}")
                    return pd.DataFrame()

                # Parse JSON and create DataFrame
                candles = [json.loads(c) for c in reversed(candles_json)]

                df = pd.DataFrame(candles)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.sort_values('timestamp').reset_index(drop=True)

                return df

            except (redis.ConnectionError, redis.TimeoutError) as e:
                logger.warning(f"Redis error on attempt {attempt + 1}/{max_attempts}: {e}")
                self._redis_connected = False

                # Record error metrics
                if METRICS_AVAILABLE:
                    record_redis_operation("get", "error")
                    REDIS_CONNECTION_ERRORS.inc()

                if attempt < max_attempts - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    logger.error(f"Failed to get candles after {max_attempts} attempts")
                    return pd.DataFrame()

            except Exception as e:
                logger.error(f"Unexpected error getting candles from Redis: {e}")
                return pd.DataFrame()

        return pd.DataFrame()

    async def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price for a symbol from Redis with retry logic"""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Check Redis connection
                if not self._redis_connected:
                    logger.warning("Redis not connected, attempting reconnection...")
                    reconnected = await self._connect_redis()
                    if not reconnected:
                        logger.error("Failed to reconnect to Redis")
                        return None

                price_key = f"price:{symbol}"
                price = await self.redis_client.get(price_key)
                return float(price) if price else None

            except (redis.ConnectionError, redis.TimeoutError) as e:
                logger.warning(f"Redis error on attempt {attempt + 1}/{max_attempts}: {e}")
                self._redis_connected = False

                if attempt < max_attempts - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    logger.error(f"Failed to get latest price after {max_attempts} attempts")
                    return None

            except Exception as e:
                logger.error(f"Unexpected error getting latest price: {e}")
                return None

        return None

    async def subscribe_multiple_symbols(self, symbols: List[str], interval: str = "1m"):
        """Subscribe to multiple symbols at once"""
        tasks = [self.subscribe_symbol(symbol, interval) for symbol in symbols]
        await asyncio.gather(*tasks)

    async def start_streaming(self):
        """Start listening to WebSocket streams"""
        logger.info("Starting WebSocket streaming...")
        await self.ws_client.listen()

    async def health_check(self) -> Dict:
        """Check health of connections with detailed status"""
        health = {
            'websocket': {
                'connected': self._ws_connected,
                'running': self.ws_client.running if self.ws_client else False
            },
            'redis': {
                'connected': self._redis_connected,
                'ping_ok': False
            },
            'active_symbols': list(self.active_symbols),
            'shutdown': self._shutdown,
            'timestamp': datetime.now().isoformat()
        }

        # Check Redis with ping
        if self.redis_client and self._redis_connected:
            try:
                await asyncio.wait_for(self.redis_client.ping(), timeout=2.0)
                health['redis']['ping_ok'] = True
            except asyncio.TimeoutError:
                logger.warning("Redis ping timed out")
                health['redis']['ping_ok'] = False
                self._redis_connected = False
            except Exception as e:
                logger.warning(f"Redis ping failed: {e}")
                health['redis']['ping_ok'] = False
                self._redis_connected = False

        return health

    async def close(self):
        """Clean up connections gracefully"""
        logger.info("Shutting down Data Manager...")
        self._shutdown = True

        # Cancel reconnect task if running
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        # Close WebSocket
        try:
            await self.ws_client.close()
            self._ws_connected = False
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")

        # Close Redis
        if self.redis_client:
            try:
                await self.redis_client.close()
                self._redis_connected = False
            except Exception as e:
                logger.error(f"Error closing Redis: {e}")

        logger.info("Data Manager shutdown complete")


# Example usage
async def example():
    """Example: Stream BTC and ETH data to Redis"""

    # Create data manager
    manager = BinanceDataManager(testnet=True)

    # Connect
    await manager.connect()

    # Subscribe to multiple symbols
    await manager.subscribe_multiple_symbols(['BTCUSDT', 'ETHUSDT'], interval='1m')

    # Start streaming in background
    stream_task = asyncio.create_task(manager.start_streaming())

    # Simulate reading data after 10 seconds
    await asyncio.sleep(10)

    # Get candles from Redis
    btc_candles = await manager.get_candles('BTCUSDT', count=10)
    print("BTC Candles:")
    print(btc_candles)

    # Get latest price
    btc_price = await manager.get_latest_price('BTCUSDT')
    print(f"\nLatest BTC Price: {btc_price}")

    # Health check
    health = await manager.health_check()
    print(f"\nHealth: {health}")

    # Keep streaming
    await stream_task


if __name__ == "__main__":
    asyncio.run(example())
