# Grafana Dashboard Configuration

This directory contains Grafana provisioning configuration and dashboards for the TikTok Analyzing Trading System.

## Directory Structure

```
config/grafana/
├── provisioning/
│   ├── datasources/
│   │   └── prometheus.yml          # Prometheus datasource configuration
│   └── dashboards/
│       └── default.yml              # Dashboard provisioning configuration
├── dashboards/
│   ├── system-overview.json         # Main system dashboard
│   ├── trading-performance.json     # Trading metrics dashboard
│   └── infrastructure.json          # Infrastructure monitoring dashboard
└── README.md                        # This file
```

## Dashboards

### 1. System Overview Dashboard
**UID:** `trading-system-overview`
**Refresh:** 10 seconds

**Panels:**
- API Service Status
- Active Bots count
- Total Portfolio Value (USD)
- Total P&L %
- API Request Rate (5m avg)
- API Response Time (p50, p95)
- Active WebSocket Connections
- Redis Operations Rate

**Use Case:** Quick health check and system status at a glance.

### 2. Trading Performance Dashboard
**UID:** `trading-performance`
**Refresh:** 10 seconds

**Panels:**
- Portfolio Value Over Time
- Portfolio P&L Percentage
- Active/Total/Inactive Bots
- Trades (Last Hour)
- Win Rate
- Total P&L (USD)
- Open Positions Count
- Trades by Result (Profit/Loss - Hourly)
- Bot Status Over Time
- Market Data Update Rate by Symbol

**Use Case:** Monitor trading bot performance, profitability, and trade execution.

### 3. Infrastructure Monitoring Dashboard
**UID:** `infrastructure-monitoring`
**Refresh:** 10 seconds

**Panels:**
- Redis Operations Rate (GET/SET/DELETE)
- Redis Operation Latency (p50, p95)
- Redis Connection Status
- Active WebSocket Connections
- WebSocket Messages (Last Minute)
- API Request Rate
- WebSocket Connection Metrics
- WebSocket Message Rate (Sent/Received)
- API Endpoints Request Rate
- API Response Status Codes

**Use Case:** Monitor infrastructure health, identify bottlenecks, and troubleshoot issues.

## Access

### Local Development
- **URL:** http://localhost:3000
- **Username:** admin
- **Password:** Set via `GRAFANA_PASSWORD` environment variable (default: `admin`)

### Production
- **URL:** Configure based on your deployment
- **Authentication:** Change default password immediately in production

## Starting Grafana

### With Monitoring Stack (Development)
```bash
docker-compose -f docker-compose.monitoring.yml --profile grafana up -d
```

### With Production Stack
```bash
docker-compose -f docker-compose.production.yml --profile monitoring up -d
```

## Metrics Available

The dashboards use the following Prometheus metrics:

### API Metrics
- `fastapi_app_info` - API service information
- `fastapi_requests_total` - Total HTTP requests
- `fastapi_request_duration_seconds_bucket` - Request duration histogram

### Trading Metrics
- `trading_bots_active_total` - Active bots count
- `trading_bots_total` - Total bots count
- `trading_trades_total` - Trade count by result
- `trading_portfolio_total_value_usd` - Portfolio value
- `trading_portfolio_pnl_percent` - Portfolio P&L percentage
- `trading_portfolio_pnl_usd` - Portfolio P&L in USD
- `trading_portfolio_positions_count` - Open positions count

### Market Data Metrics
- `trading_market_updates_total` - Market data updates

### WebSocket Metrics
- `trading_websocket_connections_active` - Active WebSocket connections
- `trading_websocket_connections_total` - Total WebSocket connections
- `trading_websocket_subscribers_total` - Subscribers per channel
- `trading_websocket_messages_total` - Messages sent/received
- `trading_websocket_broadcast_duration_seconds` - Broadcast timing

### Redis Metrics
- `trading_redis_operations_total` - Redis operations count
- `trading_redis_operation_duration_seconds_bucket` - Redis latency
- `trading_redis_connection_pool_active` - Connection pool status

## Customization

### Adding New Dashboards
1. Create a new JSON dashboard file in `config/grafana/dashboards/`
2. Dashboards are auto-discovered and loaded on Grafana startup
3. No restart required - dashboards update within 10 seconds

### Modifying Existing Dashboards
1. Edit via Grafana UI (recommended)
2. Export the dashboard JSON
3. Replace the file in `config/grafana/dashboards/`
4. Changes persist across container restarts

### Adding New Datasources
1. Add configuration to `config/grafana/provisioning/datasources/`
2. Restart Grafana container to apply changes

## Troubleshooting

### Dashboard Not Loading
- Check Grafana logs: `docker logs trading_grafana`
- Verify volume mounts in docker-compose
- Ensure JSON files are valid

### No Data in Panels
- Verify Prometheus is running and accessible
- Check Prometheus targets: http://localhost:9090/targets
- Ensure metrics are being exported from the API

### Permission Issues
- Ensure dashboard files have correct permissions (readable)
- Check volume mount paths are correct

## Alert Rules (Future Enhancement)

Consider adding Grafana alerts for:
- High API error rates (>5%)
- Low bot win rates (<40%)
- High Redis latency (>100ms p95)
- WebSocket connection drops
- Portfolio drawdown thresholds

## Performance Considerations

- Dashboards refresh every 10 seconds by default
- Prometheus retention set to 30 days
- Consider adjusting query intervals for high-frequency data
- Use recording rules for complex queries in production

## Further Reading

- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Metrics](https://prometheus.io/docs/concepts/metric_types/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
