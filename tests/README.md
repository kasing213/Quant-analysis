# Testing Guide

This directory contains tests for the Quantitative Trading Dashboard.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── test_e2e_smoke.py       # End-to-end smoke tests
├── test_simple_api.py      # Simple API tests
├── test_db_connection.py   # Database connectivity tests
├── test_risk_management.py # Risk management tests
└── README.md               # This file
```

## Installation

Install test dependencies:

```bash
pip install -r requirements/test.txt
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run specific test file
```bash
pytest tests/test_e2e_smoke.py
```

### Run with verbose output
```bash
pytest -v
```

### Run with coverage report
```bash
pytest --cov=src --cov-report=html
```

### Run only unit tests (no integration tests)
```bash
pytest -m "not integration"
```

### Run integration tests (requires real services)
```bash
pytest --integration
```

### Run smoke tests only
```bash
pytest -m smoke
```

### Run with specific markers
```bash
# Run only async tests
pytest -m asyncio

# Run only fast tests
pytest -m "not slow"

# Run e2e tests
pytest -m e2e
```

## Test Types

### Smoke Tests (`test_e2e_smoke.py`)
Quick tests to verify basic functionality works:
- Health endpoints
- Database connectivity
- Portfolio endpoints
- Market data endpoints
- WebSocket connections

**Run:** `pytest tests/test_e2e_smoke.py -v`

### Unit Tests
Test individual components in isolation with mocked dependencies.

**Run:** `pytest -m unit`

### Integration Tests
Test components with real services (Redis, PostgreSQL).

**Requires:** Running Redis and PostgreSQL instances

**Run:** `pytest --integration`

## Continuous Integration

Tests are designed to run in CI environments without requiring real services.

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements/test.txt
      - run: pytest -v --cov=src
```

## Test Environment Variables

Tests use the following environment variables (automatically set in `conftest.py`):

```bash
TESTING=true
PIPELINE_MODE=BINANCE_PAPER
BINANCE_TEST_MODE=true
BINANCE_ENABLE_BOTS=false
BINANCE_ENABLE_MARKET_DATA=false
```

Override in your shell:
```bash
export BINANCE_ENABLE_BOTS=true
pytest tests/test_e2e_smoke.py
```

## Mocked Services

The test suite includes mocks for:
- Redis client
- PostgreSQL connection pool
- Binance REST client
- Binance data manager
- Bot orchestrator
- Bot persistence layer

See `conftest.py` for mock implementations.

## Writing New Tests

### Example: Unit Test

```python
import pytest
from src.binance.trading_bot import TradingBot

def test_bot_initialization(mock_binance_client, mock_binance_data_manager):
    """Test bot can be initialized"""
    bot = TradingBot(
        bot_id="test",
        symbol="BTCUSDT",
        strategy=mock_strategy,
        rest_client=mock_binance_client,
        data_manager=mock_binance_data_manager
    )
    assert bot.bot_id == "test"
    assert bot.symbol == "BTCUSDT"
```

### Example: Async Test

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """Test health endpoint"""
    response = await client.get("/health")
    assert response.status_code == 200
```

### Example: Integration Test

```python
import pytest

@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_query(real_postgres):
    """Test real database query"""
    async with real_postgres.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
        assert result == 1
```

## Fixtures

Common fixtures available in `conftest.py`:

- `mock_redis` - Mocked Redis client
- `mock_postgres` - Mocked PostgreSQL pool
- `mock_binance_client` - Mocked Binance client
- `mock_binance_data_manager` - Mocked data manager
- `mock_bot_orchestrator` - Mocked orchestrator
- `mock_bot_persistence` - Mocked persistence layer
- `real_postgres` - Real PostgreSQL connection (integration tests)
- `real_redis` - Real Redis connection (integration tests)
- `sample_candle_data` - Sample market data
- `sample_bot_config` - Sample bot configuration

## Coverage Reports

Generate HTML coverage report:

```bash
pytest --cov=src --cov-report=html
```

View report:
```bash
open htmlcov/index.html  # macOS
start htmlcov/index.html # Windows
xdg-open htmlcov/index.html # Linux
```

## Troubleshooting

### Import Errors
Ensure you're running tests from the project root:
```bash
cd /path/to/Tiktok-analyzing
pytest
```

### Async Test Errors
Install pytest-asyncio:
```bash
pip install pytest-asyncio
```

### Database Connection Errors
Check PostgreSQL is running and environment variables are set:
```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/dbname"
pytest --integration
```

### Redis Connection Errors
Check Redis is running:
```bash
redis-cli ping  # Should return PONG
pytest --integration
```

## Best Practices

1. **Keep tests isolated** - Each test should be independent
2. **Use fixtures** - Leverage conftest.py fixtures for common setup
3. **Mock external dependencies** - Don't hit real APIs in unit tests
4. **Mark tests appropriately** - Use `@pytest.mark.integration`, etc.
5. **Test error cases** - Don't just test happy paths
6. **Keep tests fast** - Unit tests should run in milliseconds
7. **Document complex tests** - Add docstrings explaining what's tested

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Async Testing](https://pytest-asyncio.readthedocs.io/)
