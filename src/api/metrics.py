"""
Prometheus metrics for monitoring the trading system.
"""
import logging
from typing import Dict, Any
from prometheus_client import Counter, Gauge, Histogram, Info

logger = logging.getLogger(__name__)

# API Metrics (FastAPI Instrumentator provides basic HTTP metrics)
# We add custom business metrics here

# Bot Metrics
ACTIVE_BOTS = Gauge(
    'trading_bots_active_total',
    'Number of currently active trading bots',
    ['status']  # running, paused, stopped
)

BOT_TRADES_TOTAL = Counter(
    'trading_bot_trades_total',
    'Total number of trades executed by bots',
    ['bot_id', 'symbol', 'side', 'status']  # side: buy/sell, status: filled/rejected/cancelled
)

BOT_PNL = Gauge(
    'trading_bot_pnl_usd',
    'Current profit/loss for each bot in USD',
    ['bot_id', 'symbol']
)

# Portfolio Metrics
PORTFOLIO_VALUE = Gauge(
    'portfolio_total_value_usd',
    'Total portfolio value in USD'
)

PORTFOLIO_POSITIONS = Gauge(
    'portfolio_positions_count',
    'Number of open positions in portfolio',
    ['symbol']
)

PORTFOLIO_CASH = Gauge(
    'portfolio_cash_balance_usd',
    'Available cash balance in USD'
)

# Market Data Metrics
MARKET_DATA_UPDATES = Counter(
    'market_data_updates_total',
    'Total number of market data updates received',
    ['symbol', 'source']  # source: binance, websocket, rest
)

MARKET_DATA_LAG = Histogram(
    'market_data_lag_seconds',
    'Lag between market data timestamp and processing time',
    ['symbol'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

WEBSOCKET_CONNECTIONS = Gauge(
    'websocket_connections_active',
    'Number of active WebSocket connections',
    ['endpoint']  # market_data, bot_updates, etc.
)

# Redis Metrics (custom)
REDIS_OPERATIONS = Counter(
    'redis_operations_total',
    'Total number of Redis operations',
    ['operation', 'status']  # operation: get/set/delete, status: success/error
)

REDIS_CONNECTION_ERRORS = Counter(
    'redis_connection_errors_total',
    'Total number of Redis connection errors'
)

# Database Metrics (custom)
DB_QUERIES = Counter(
    'database_queries_total',
    'Total number of database queries',
    ['operation', 'table', 'status']  # operation: select/insert/update/delete
)

DB_QUERY_DURATION = Histogram(
    'database_query_duration_seconds',
    'Database query execution time',
    ['operation', 'table'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

# System Info
SYSTEM_INFO = Info(
    'trading_system_info',
    'Information about the trading system'
)


def initialize_metrics():
    """Initialize system information metrics."""
    try:
        import platform
        SYSTEM_INFO.info({
            'version': '1.0.0',
            'python_version': platform.python_version(),
            'platform': platform.platform(),
        })
        logger.info("Metrics initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize metrics: {e}")


def update_bot_metrics(bot_data: Dict[str, Any]):
    """
    Update bot-related metrics.

    Args:
        bot_data: Dictionary containing bot status information
    """
    try:
        status = bot_data.get('status', 'unknown')
        bot_id = bot_data.get('id', 'unknown')

        # Update active bots gauge
        if status in ['running', 'paused', 'stopped']:
            ACTIVE_BOTS.labels(status=status).set(bot_data.get('count', 0))

        # Update P&L if available
        if 'pnl' in bot_data and 'symbol' in bot_data:
            BOT_PNL.labels(
                bot_id=bot_id,
                symbol=bot_data['symbol']
            ).set(bot_data['pnl'])

    except Exception as e:
        logger.error(f"Error updating bot metrics: {e}")


def update_portfolio_metrics(portfolio_data: Dict[str, Any]):
    """
    Update portfolio-related metrics.

    Args:
        portfolio_data: Dictionary containing portfolio information
    """
    try:
        if 'total_value' in portfolio_data:
            PORTFOLIO_VALUE.set(portfolio_data['total_value'])

        if 'cash_balance' in portfolio_data:
            PORTFOLIO_CASH.set(portfolio_data['cash_balance'])

        if 'positions' in portfolio_data:
            for position in portfolio_data['positions']:
                symbol = position.get('symbol', 'unknown')
                quantity = position.get('quantity', 0)
                PORTFOLIO_POSITIONS.labels(symbol=symbol).set(quantity)

    except Exception as e:
        logger.error(f"Error updating portfolio metrics: {e}")


def record_trade(bot_id: str, symbol: str, side: str, status: str):
    """
    Record a trade execution.

    Args:
        bot_id: Bot identifier
        symbol: Trading symbol
        side: Trade side (buy/sell)
        status: Trade status (filled/rejected/cancelled)
    """
    try:
        BOT_TRADES_TOTAL.labels(
            bot_id=bot_id,
            symbol=symbol,
            side=side,
            status=status
        ).inc()
    except Exception as e:
        logger.error(f"Error recording trade: {e}")


def record_market_data_update(symbol: str, source: str, lag_seconds: float = 0.0):
    """
    Record a market data update.

    Args:
        symbol: Trading symbol
        source: Data source (binance, websocket, rest)
        lag_seconds: Lag in seconds between data timestamp and processing
    """
    try:
        MARKET_DATA_UPDATES.labels(symbol=symbol, source=source).inc()
        if lag_seconds > 0:
            MARKET_DATA_LAG.labels(symbol=symbol).observe(lag_seconds)
    except Exception as e:
        logger.error(f"Error recording market data update: {e}")


def record_redis_operation(operation: str, status: str = 'success'):
    """
    Record a Redis operation.

    Args:
        operation: Type of operation (get/set/delete)
        status: Operation status (success/error)
    """
    try:
        REDIS_OPERATIONS.labels(operation=operation, status=status).inc()
    except Exception as e:
        logger.error(f"Error recording Redis operation: {e}")


def record_db_query(operation: str, table: str, duration_seconds: float, status: str = 'success'):
    """
    Record a database query.

    Args:
        operation: Type of operation (select/insert/update/delete)
        table: Table name
        duration_seconds: Query execution time
        status: Query status (success/error)
    """
    try:
        DB_QUERIES.labels(operation=operation, table=table, status=status).inc()
        DB_QUERY_DURATION.labels(operation=operation, table=table).observe(duration_seconds)
    except Exception as e:
        logger.error(f"Error recording database query: {e}")
