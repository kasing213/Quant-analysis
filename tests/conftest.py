"""
Pytest configuration and shared fixtures for testing

Provides mocked services (Redis, Postgres) for CI environments
and real service fixtures for integration testing.
"""

import pytest
import asyncio
import os
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


# ===================================
# Environment Configuration
# ===================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables"""
    os.environ["TESTING"] = "true"
    os.environ.setdefault("PIPELINE_MODE", "BINANCE_PAPER")
    os.environ.setdefault("BINANCE_TEST_MODE", "true")
    os.environ.setdefault("BINANCE_ENABLE_BOTS", "false")
    os.environ.setdefault("BINANCE_ENABLE_MARKET_DATA", "false")
    os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test_db")
    os.environ.setdefault("REDIS_HOST", "localhost")
    os.environ.setdefault("REDIS_PORT", "6379")


# ===================================
# Event Loop Fixtures
# ===================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ===================================
# Mock Service Fixtures
# ===================================

@pytest.fixture
def mock_redis():
    """Mock Redis client for testing"""
    mock = MagicMock()
    mock.ping = AsyncMock(return_value=True)
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.exists = AsyncMock(return_value=0)
    mock.hgetall = AsyncMock(return_value={})
    mock.hset = AsyncMock(return_value=1)
    mock.publish = AsyncMock(return_value=1)
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_postgres():
    """Mock PostgreSQL connection pool for testing"""
    mock_pool = MagicMock()
    mock_conn = MagicMock()

    # Mock connection methods
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.fetchval = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock(return_value="SELECT 1")

    # Mock pool acquire context manager
    mock_pool.acquire = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_pool.close = AsyncMock()

    return mock_pool


@pytest.fixture
def mock_binance_client():
    """Mock Binance REST client for testing"""
    mock = MagicMock()
    mock.get_account = AsyncMock(return_value={
        "balances": [
            {"asset": "USDT", "free": "1000.00", "locked": "0.00"},
            {"asset": "BTC", "free": "0.5", "locked": "0.0"}
        ]
    })
    mock.get_ticker = AsyncMock(return_value={
        "symbol": "BTCUSDT",
        "price": "50000.00"
    })
    mock.get_klines = AsyncMock(return_value=[
        [1609459200000, "29000", "29200", "28800", "29100", "100", 1609462800000, "2910000", 150, "50", "1455000", "0"]
    ])
    mock.create_order = AsyncMock(return_value={
        "orderId": "12345",
        "status": "FILLED",
        "executedQty": "0.01"
    })
    return mock


@pytest.fixture
def mock_binance_data_manager():
    """Mock Binance data manager for testing"""
    mock = MagicMock()
    mock.connect = AsyncMock()
    mock.close = AsyncMock()
    mock.subscribe_symbol = AsyncMock()
    mock.subscribe_multiple_symbols = AsyncMock()
    mock.get_latest_candle = AsyncMock(return_value={
        "symbol": "BTCUSDT",
        "timestamp": "2024-01-01T00:00:00Z",
        "open": 50000.0,
        "high": 51000.0,
        "low": 49000.0,
        "close": 50500.0,
        "volume": 1000.0
    })
    mock.get_quote = AsyncMock(return_value={
        "symbol": "BTCUSDT",
        "bid": 50000.0,
        "ask": 50100.0,
        "last": 50050.0
    })
    mock.health_check = AsyncMock(return_value={"status": "healthy"})
    return mock


@pytest.fixture
def mock_bot_orchestrator():
    """Mock bot orchestrator for testing"""
    mock = MagicMock()
    mock.initialize = AsyncMock()
    mock.shutdown = AsyncMock()
    mock.create_bot = AsyncMock()
    mock.start_bot = AsyncMock()
    mock.stop_bot = AsyncMock()
    mock.remove_bot = AsyncMock()
    mock.get_bot_stats = MagicMock(return_value={
        "bot_id": "test_bot",
        "symbol": "BTCUSDT",
        "strategy": "RSI",
        "capital": 1000.0,
        "total_pnl": 50.0,
        "total_trades": 10,
        "win_rate": 60.0,
        "running": True
    })
    mock.get_all_stats = MagicMock(return_value={
        "orchestrator": {
            "total_bots": 1,
            "running_bots": 1
        },
        "bots": {}
    })
    mock.get_portfolio_summary = MagicMock(return_value={
        "total_bots": 1,
        "total_capital": 1000.0,
        "total_pnl": 50.0,
        "total_trades": 10
    })
    mock.health_check = AsyncMock(return_value={"status": "healthy"})
    return mock


@pytest.fixture
def mock_bot_persistence():
    """Mock bot persistence layer for testing"""
    mock = MagicMock()
    mock.initialize = AsyncMock()
    mock.close = AsyncMock()
    mock.save_bot_config = AsyncMock(return_value="bot_123")
    mock.get_bot_config = AsyncMock(return_value={
        "bot_id": "test_bot",
        "symbol": "BTCUSDT",
        "strategy_name": "RSI_14"
    })
    mock.get_all_bot_configs = AsyncMock(return_value=[])
    mock.update_bot_status = AsyncMock()
    mock.save_bot_state = AsyncMock(return_value="state_123")
    mock.get_latest_bot_state = AsyncMock(return_value=None)
    mock.record_trade = AsyncMock(return_value="trade_123")
    mock.get_bot_trades = AsyncMock(return_value=[])
    mock.get_bot_status = AsyncMock(return_value=None)
    mock.get_all_bot_statuses = AsyncMock(return_value=[])
    return mock


# ===================================
# Application Fixtures
# ===================================

@pytest.fixture
async def app_with_mocks(
    mock_redis,
    mock_postgres,
    mock_binance_data_manager,
    mock_bot_orchestrator
):
    """FastAPI app with mocked dependencies"""
    from src.api.main import app

    # Mock the dependencies
    with patch('src.api.main.bot_orchestrator', mock_bot_orchestrator), \
         patch('src.api.main.binance_data_manager', mock_binance_data_manager):
        yield app


# ===================================
# Database Fixtures (for integration tests)
# ===================================

@pytest.fixture
async def real_postgres():
    """Real PostgreSQL connection for integration tests"""
    try:
        import asyncpg
        from src.database.pg_config import get_async_pool

        pool = await get_async_pool()
        yield pool
        await pool.close()
    except Exception as e:
        pytest.skip(f"PostgreSQL not available: {e}")


@pytest.fixture
async def real_redis():
    """Real Redis connection for integration tests"""
    try:
        import redis.asyncio as redis

        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True
        )
        await client.ping()
        yield client
        await client.close()
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


# ===================================
# Utility Fixtures
# ===================================

@pytest.fixture
def sample_candle_data():
    """Sample market candle data for testing"""
    return {
        "symbol": "BTCUSDT",
        "timestamp": "2024-01-01T00:00:00Z",
        "open": 50000.0,
        "high": 51000.0,
        "low": 49000.0,
        "close": 50500.0,
        "volume": 1000.0
    }


@pytest.fixture
def sample_bot_config():
    """Sample bot configuration for testing"""
    return {
        "bot_id": "test_bot",
        "symbol": "BTCUSDT",
        "strategy_name": "RSI_14",
        "capital": 1000.0,
        "risk_per_trade": 0.02,
        "max_position_size": 0.1
    }


# ===================================
# Pytest Configuration
# ===================================

def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires real services)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )


# Run integration tests only when --integration flag is passed
def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers"""
    if not config.getoption("--integration", default=False):
        skip_integration = pytest.mark.skip(reason="need --integration option to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


def pytest_addoption(parser):
    """Add custom pytest options"""
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="run integration tests that require real services"
    )
