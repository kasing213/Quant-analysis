# Monitoring Quick Start Guide

## ✅ Prometheus is Running!

Your Prometheus instance is now collecting metrics.

## Access Points

### Prometheus UI
- **URL:** http://localhost:9090
- **Status:** http://localhost:9090/targets
- **Config:** http://localhost:9090/config

### API Metrics Endpoint
- **URL:** http://localhost:8000/metrics (when API is running)

## Quick Setup Steps

### 1. Start Your Trading API

Make sure your API is running so Prometheus can scrape metrics:

```bash
# Option A: Using Docker Compose
docker-compose up -d api

# Option B: Local development
./start.sh
```

### 2. Verify Metrics Endpoint

Once the API is running:

```bash
# Check if metrics are being exposed
curl http://localhost:8000/metrics
```

You should see output like:
```
# HELP trading_bots_active_total Number of currently active trading bots
# TYPE trading_bots_active_total gauge
trading_bots_active_total{status="running"} 3.0
trading_bots_active_total{status="stopped"} 1.0
...
```

### 3. Check Prometheus Targets

1. Open http://localhost:9090/targets
2. Look for the `api` job
3. Status should show "UP" (green)

**Expected targets:**
- `api` (localhost:8000)
- `bot` (localhost:8001) - if bot service is running
- `prometheus` (self-monitoring)

### 4. Query Metrics in Prometheus

Go to http://localhost:9090 and try these queries:

#### Active Bots
```promql
trading_bots_active_total
```

#### Trade Rate (per minute)
```promql
rate(trading_bot_trades_total[5m]) * 60
```

#### Portfolio Value
```promql
portfolio_total_value_usd
```

#### HTTP Request Rate
```promql
rate(http_requests_total[5m])
```

#### API Response Time (95th percentile)
```promql
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

#### Market Data Update Rate
```promql
rate(market_data_updates_total[1m])
```

#### Redis Success Rate
```promql
rate(redis_operations_total{status="success"}[5m]) / rate(redis_operations_total[5m])
```

## Troubleshooting

### Prometheus Shows "api" Target as DOWN

**Symptoms:**
- Target shows as "DOWN" with red indicator
- Error: "connection refused" or "timeout"

**Solutions:**

1. **Check if API is running:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check Docker network:**
   ```bash
   # If API is in Docker, update prometheus.yml to use container name
   # Change: targets: ['api:8000']
   # Instead of: targets: ['localhost:8000']
   ```

3. **Update Prometheus config for local development:**

   Edit `config/prometheus/prometheus.yml`:
   ```yaml
   scrape_configs:
     - job_name: 'api'
       static_configs:
         - targets: ['host.docker.internal:8000']  # For Docker Desktop
         # OR
         - targets: ['172.17.0.1:8000']  # For Linux Docker
   ```

   Then reload Prometheus:
   ```bash
   docker kill -s HUP trading_prometheus
   ```

### No Custom Metrics Appearing

**Check if prometheus libraries are installed:**
```bash
pip list | grep prometheus
```

Expected output:
```
prometheus-client                 0.19.0
prometheus-fastapi-instrumentator 7.0.0
```

**Install if missing:**
```bash
pip install -r requirements/binance.txt
```

### Metrics Endpoint Returns 404

**Verify FastAPI instrumentator is loaded:**

Check API logs for:
```
Prometheus instrumentation enabled on /metrics endpoint
```

If missing, the prometheus libraries might not be installed.

## Container Management

### View Prometheus Logs
```bash
docker logs -f trading_prometheus
```

### Restart Prometheus
```bash
docker-compose -f docker-compose.monitoring.yml restart prometheus
```

### Stop Prometheus
```bash
docker-compose -f docker-compose.monitoring.yml down
```

### View Container Status
```bash
docker ps | grep prometheus
```

## Optional: Add Grafana

For better visualization, start Grafana:

```bash
docker-compose -f docker-compose.monitoring.yml --profile grafana up -d
```

**Access Grafana:**
- URL: http://localhost:3000
- Default login: `admin` / `admin`

**Add Prometheus as Data Source:**
1. Go to Configuration → Data Sources
2. Add Prometheus
3. URL: `http://prometheus:9090`
4. Save & Test

## Next Steps

1. ✅ Prometheus is running
2. ⏳ Start your API service
3. ⏳ Verify /metrics endpoint
4. ⏳ Check Prometheus targets
5. ⏳ Create Grafana dashboards (optional)

## Useful Commands

```bash
# Check all monitoring containers
docker ps --filter "name=trading_" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# View Prometheus config
docker exec trading_prometheus cat /etc/prometheus/prometheus.yml

# Reload Prometheus config (without restart)
curl -X POST http://localhost:9090/-/reload

# Check Prometheus health
curl http://localhost:9090/-/healthy

# Export metrics from API
curl http://localhost:8000/metrics > metrics.txt
```

## Documentation

For more details, see:
- [docs/TELEMETRY_SETUP.md](docs/TELEMETRY_SETUP.md) - Complete setup guide
- [config/prometheus/prometheus.yml](config/prometheus/prometheus.yml) - Prometheus configuration
- [src/api/metrics.py](src/api/metrics.py) - Custom metrics definitions

## Support

If you encounter issues:
1. Check container logs: `docker logs trading_prometheus`
2. Verify network connectivity: `docker network inspect trading-analyzing_trading_network`
3. Test metrics endpoint: `curl http://localhost:8000/metrics`
4. Check Prometheus targets: http://localhost:9090/targets
