# Telemetry and Monitoring Setup

## Overview

Complete observability stack implemented with Prometheus metrics for comprehensive monitoring of the trading system.

## Architecture

```
┌─────────────────┐
│  FastAPI App    │ ──> Prometheus Instrumentator ──> /metrics endpoint
│  (Port 8000)    │
└─────────────────┘
         │
         ├─> Custom Business Metrics
         │   ├─> Bot Metrics (active bots, P&L, trades)
         │   ├─> Portfolio Metrics (value, positions, cash)
         │   ├─> Market Data Metrics (updates, lag)
         │   └─> Infrastructure Metrics (Redis, WebSocket)
         │
         v
┌─────────────────┐
│  Prometheus     │ ──> Scrapes /metrics every 10-15s
│  (Port 9090)    │
└─────────────────┘
         │
         v
┌─────────────────┐
│  Grafana        │ ──> Visualize metrics (optional)
│  (Port 3000)    │
└─────────────────┘
```

## Components

### 1. Prometheus Configuration

**File:** `config/prometheus/prometheus.yml`

Configures Prometheus to scrape metrics from:
- API service (port 8000) - every 10s
- Bot service (port 8001) - every 10s
- Redis exporter (optional)
- Postgres exporter (optional)

### 2. Metrics Module

**File:** `src/api/metrics.py`

Defines all custom business metrics:

#### Bot Metrics
- `trading_bots_active_total` - Number of active bots by status (running/paused/stopped)
- `trading_bot_trades_total` - Total trades by bot, symbol, side, and status
- `trading_bot_pnl_usd` - Current P&L for each bot

#### Portfolio Metrics
- `portfolio_total_value_usd` - Total portfolio value
- `portfolio_positions_count` - Number of open positions by symbol
- `portfolio_cash_balance_usd` - Available cash balance

#### Market Data Metrics
- `market_data_updates_total` - Total market data updates by symbol and source
- `market_data_lag_seconds` - Lag between data timestamp and processing (histogram)
- `websocket_connections_active` - Active WebSocket connections by endpoint

#### Infrastructure Metrics
- `redis_operations_total` - Redis operations by type and status
- `redis_connection_errors_total` - Redis connection errors counter
- `database_queries_total` - Database queries by operation, table, and status
- `database_query_duration_seconds` - Query execution time (histogram)

### 3. Instrumentation Points

#### FastAPI Application (`src/api/main.py`)

```python
# Automatic HTTP metrics via Instrumentator
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app, endpoint="/metrics")
```

Provides:
- HTTP request count by method, endpoint, status
- Request duration histogram
- Request size histogram
- Response size histogram

#### WebSocket Connections (`src/api/main.py:506-520`)

Tracks active WebSocket connections:
```python
WEBSOCKET_CONNECTIONS.labels(endpoint="general").set(len(self.active_connections))
```

#### Market Data Updates (`src/api/main.py:661-663`)

Records each market data update:
```python
record_market_data_update(symbol, "websocket")
```

#### BinanceDataManager (`src/binance/data_manager.py`)

- Redis operation metrics (lines 240-242, 294-295)
- Redis connection error tracking (lines 252-254, 315-317)
- Market data update recording

#### Bot Router (`src/api/routers/bots.py:290-303`)

Updates bot metrics on status queries:
```python
ACTIVE_BOTS.labels(status="running").set(running_count)
BOT_PNL.labels(bot_id=bot_id, symbol=symbol).set(pnl)
```

#### Portfolio Router (`src/api/routers/portfolio.py:138-143`)

Updates portfolio metrics:
```python
update_portfolio_metrics({
    'total_value': total_capital + total_pnl,
    'cash_balance': total_capital
})
```

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements/binance.txt
```

This includes:
- `prometheus-client>=0.19.0` - Core Prometheus client
- `prometheus-fastapi-instrumentator>=7.0.0` - FastAPI auto-instrumentation

### 2. Start Services

The Prometheus service is already configured in `docker-compose.production.yml`:

```bash
docker-compose -f docker-compose.production.yml up -d prometheus
```

### 3. Verify Metrics Endpoint

```bash
curl http://localhost:8000/metrics
```

Should return Prometheus-formatted metrics like:
```
# HELP trading_bots_active_total Number of currently active trading bots
# TYPE trading_bots_active_total gauge
trading_bots_active_total{status="running"} 3.0
trading_bots_active_total{status="stopped"} 1.0

# HELP trading_bot_pnl_usd Current profit/loss for each bot in USD
# TYPE trading_bot_pnl_usd gauge
trading_bot_pnl_usd{bot_id="bot1",symbol="BTCUSDT"} 125.50
```

## Accessing Metrics

### Prometheus UI

1. Open http://localhost:9090
2. Query metrics with PromQL:
   - `trading_bots_active_total`
   - `rate(trading_bot_trades_total[5m])`
   - `portfolio_total_value_usd`
   - `rate(market_data_updates_total[1m])`

### Example Queries

**Active Bots:**
```promql
sum(trading_bots_active_total{status="running"})
```

**Trade Rate (per minute):**
```promql
rate(trading_bot_trades_total[5m]) * 60
```

**Total Portfolio Value:**
```promql
portfolio_total_value_usd
```

**Market Data Update Rate:**
```promql
rate(market_data_updates_total[1m])
```

**WebSocket Connections:**
```promql
websocket_connections_active
```

**Redis Operation Success Rate:**
```promql
rate(redis_operations_total{status="success"}[5m]) /
rate(redis_operations_total[5m])
```

**95th Percentile Market Data Lag:**
```promql
histogram_quantile(0.95, market_data_lag_seconds_bucket)
```

## Grafana Dashboard (Optional)

### Setup

1. Add Prometheus as data source:
   - URL: `http://prometheus:9090`

2. Create dashboard with panels for:
   - Active bots gauge
   - Trade volume over time
   - Portfolio value line chart
   - P&L by bot
   - Market data update rate
   - Redis/DB operation rates
   - WebSocket connections
   - System resource usage

### Pre-built Dashboard

A sample Grafana dashboard configuration can be created based on these metrics.

## Monitoring Best Practices

### Alert Rules

Create Prometheus alert rules for:

1. **Bot Health:**
   ```yaml
   - alert: NoActiveBotsRunning
     expr: sum(trading_bots_active_total{status="running"}) == 0
     for: 5m
   ```

2. **Market Data Lag:**
   ```yaml
   - alert: HighMarketDataLag
     expr: histogram_quantile(0.95, market_data_lag_seconds_bucket) > 5
     for: 2m
   ```

3. **Redis Errors:**
   ```yaml
   - alert: HighRedisErrorRate
     expr: rate(redis_connection_errors_total[5m]) > 0.1
     for: 1m
   ```

4. **Portfolio Drawdown:**
   ```yaml
   - alert: HighPortfolioDrawdown
     expr: (portfolio_total_value_usd - portfolio_cash_balance_usd) / portfolio_cash_balance_usd < -0.15
     for: 5m
   ```

## Performance Considerations

### Metric Cardinality

Be cautious with high-cardinality labels:
- ✅ Good: `bot_id`, `symbol`, `status` (limited values)
- ⚠️ Caution: Individual trade IDs, timestamps
- ❌ Avoid: User IDs, session IDs, unique identifiers

Current implementation uses low-cardinality labels, making it efficient.

### Scrape Interval

- API/Bot metrics: 10s (real-time monitoring)
- Infrastructure: 30s (less volatile)
- Adjust in `prometheus.yml` based on needs

### Retention

Default Prometheus retention is 15 days. Configure in `docker-compose.production.yml`:

```yaml
prometheus:
  command:
    - '--storage.tsdb.retention.time=30d'
    - '--storage.tsdb.retention.size=10GB'
```

## Troubleshooting

### Metrics Not Appearing

1. **Check if prometheus-client is installed:**
   ```bash
   pip list | grep prometheus
   ```

2. **Verify /metrics endpoint:**
   ```bash
   curl http://localhost:8000/metrics
   ```

3. **Check Prometheus targets:**
   - Open http://localhost:9090/targets
   - Verify all endpoints are "UP"

### Missing Business Metrics

If custom metrics (bots, portfolio) are missing:

1. Check if orchestrator is initialized:
   ```bash
   curl http://localhost:8000/api/v1/bots/
   ```

2. Verify metrics module loaded:
   - Check logs for "Metrics initialized successfully"
   - Look for "METRICS_AVAILABLE" in debug logs

### High Memory Usage

If Prometheus uses too much memory:
1. Reduce retention time
2. Decrease scrape frequency
3. Limit metric cardinality (reduce unique label combinations)

## Future Enhancements

- [ ] Add Grafana dashboard templates
- [ ] Configure AlertManager for notifications
- [ ] Add trace instrumentation (OpenTelemetry)
- [ ] Export metrics to remote storage (Thanos, Cortex)
- [ ] Add custom recording rules for complex queries
- [ ] Implement metric aggregation for multi-instance deployments

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [prometheus_client Python Library](https://github.com/prometheus/client_python)
- [FastAPI Instrumentator](https://github.com/trallnag/prometheus-fastapi-instrumentator)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
