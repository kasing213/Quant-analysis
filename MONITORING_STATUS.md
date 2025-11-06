# Monitoring System Status

## ✅ Current Status

### Running Services
- ✅ **Prometheus** - Running on http://localhost:9090
- ✅ **Redis** - Running on localhost:6379
- ⏳ **API** - Not started (needed for metrics)
- ⏳ **Trading Bot** - Not started

### Prometheus Configuration
- ✅ Config loaded: `/etc/prometheus/prometheus.yml`
- ✅ Supports both Docker and local development
- ✅ 30-day retention configured
- ✅ Web UI accessible

## 📊 What's Configured

### Scrape Targets

Prometheus is configured to scrape metrics from:

1. **API Service** (port 8000)
   - Docker: `api:8000`
   - Local: `host.docker.internal:8000`
   - Interval: 10 seconds

2. **Bot Service** (port 8001)
   - Docker: `bot:8001`
   - Local: `host.docker.internal:8001`
   - Interval: 10 seconds

3. **Prometheus Self** (port 9090)
   - Target: `localhost:9090`
   - Self-monitoring

### Current Target Status

Check at: http://localhost:9090/targets

**Expected:**
- `api` targets: DOWN (until API starts)
- `bot` targets: DOWN (until bot starts)
- `prometheus`: UP ✅

This is **normal** - targets will turn green once you start your services.

## 🚀 Next Steps to Get Full Monitoring

### Step 1: Install Prometheus Dependencies

```bash
# Make sure you're in your virtual environment
source .venv/bin/activate  # or: source venv/bin/activate

# Install monitoring dependencies
pip install prometheus-client>=0.19.0 prometheus-fastapi-instrumentator>=7.0.0

# Or install all requirements
pip install -r requirements/binance.txt
```

### Step 2: Start Your API Service

Choose one option:

**Option A: Using start.sh**
```bash
./start.sh
```

**Option B: Docker Compose**
```bash
docker-compose up -d api
```

**Option C: Direct Python**
```bash
cd src
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Step 3: Verify Metrics Endpoint

Once the API is running:

```bash
# Test the metrics endpoint
curl http://localhost:8000/metrics

# You should see Prometheus-formatted metrics
```

### Step 4: Check Prometheus Targets

1. Go to http://localhost:9090/targets
2. The `api` job with `env=local` should now show **UP** (green)
3. Click on the endpoint to see the raw metrics

### Step 5: Query Your First Metric

1. Go to http://localhost:9090
2. In the query box, type: `up`
3. Click "Execute"
4. You should see your services listed with value `1` (up) or `0` (down)

## 📈 Available Metrics

Once your API is running, you'll have access to:

### HTTP Metrics (Automatic)
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency
- `http_request_size_bytes` - Request size
- `http_response_size_bytes` - Response size

### Trading Metrics (Custom)
- `trading_bots_active_total{status="running|stopped"}` - Active bots
- `trading_bot_pnl_usd{bot_id, symbol}` - Bot P&L
- `trading_bot_trades_total{bot_id, symbol, side, status}` - Trade count
- `portfolio_total_value_usd` - Portfolio value
- `portfolio_cash_balance_usd` - Cash balance
- `portfolio_positions_count{symbol}` - Position counts

### Market Data Metrics
- `market_data_updates_total{symbol, source}` - Update count
- `market_data_lag_seconds` - Data lag histogram
- `websocket_connections_active{endpoint}` - WebSocket count

### Infrastructure Metrics
- `redis_operations_total{operation, status}` - Redis ops
- `redis_connection_errors_total` - Redis errors
- `database_queries_total{operation, table, status}` - DB queries
- `database_query_duration_seconds` - Query latency

## 🔍 Example Queries

Try these in the Prometheus UI:

### Check Service Health
```promql
up{job="api"}
```

### Active Trading Bots
```promql
sum(trading_bots_active_total{status="running"})
```

### API Request Rate (per minute)
```promql
rate(http_requests_total[5m]) * 60
```

### API 95th Percentile Response Time
```promql
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

### Trade Volume (per minute)
```promql
rate(trading_bot_trades_total[5m]) * 60
```

### Redis Success Rate
```promql
sum(rate(redis_operations_total{status="success"}[5m])) /
sum(rate(redis_operations_total[5m]))
```

## 📁 Important Files

- **Config**: [config/prometheus/prometheus.yml](config/prometheus/prometheus.yml)
- **Metrics Module**: [src/api/metrics.py](src/api/metrics.py)
- **Quick Start**: [MONITORING_QUICKSTART.md](MONITORING_QUICKSTART.md)
- **Full Guide**: [docs/TELEMETRY_SETUP.md](docs/TELEMETRY_SETUP.md)

## 🐛 Troubleshooting

### Prometheus Shows Targets as DOWN

**Normal if:**
- ✅ API service not started yet
- ✅ Bot service not started yet

**Problem if:**
- ❌ API is running but still shows DOWN
  - Check if API is on port 8000: `curl http://localhost:8000/health`
  - Check if metrics endpoint exists: `curl http://localhost:8000/metrics`
  - Verify prometheus libraries installed: `pip list | grep prometheus`

### Metrics Endpoint Returns 404

**Solution:**
```bash
# Install required packages
pip install prometheus-client prometheus-fastapi-instrumentator

# Restart API
```

### No Custom Metrics (only http_* metrics)

This means:
- ✅ Prometheus instrumentation is working
- ❌ Custom metrics not initialized

**Causes:**
1. Trading bots not active (metrics only appear when bots run)
2. Endpoints not called yet (call `/api/v1/bots/` to populate metrics)
3. Orchestrator not initialized

## 🎯 Success Criteria

You'll know monitoring is fully working when:

1. ✅ Prometheus UI accessible at http://localhost:9090
2. ✅ API target shows "UP" at http://localhost:9090/targets
3. ✅ `/metrics` endpoint returns data at http://localhost:8000/metrics
4. ✅ Custom metrics visible (search for `trading_bots_active_total`)
5. ✅ Queries return data in Prometheus UI

## 📞 Quick Commands

```bash
# Check Prometheus status
docker ps | grep prometheus
curl http://localhost:9090/-/healthy

# View Prometheus logs
docker logs -f trading_prometheus

# Reload Prometheus config
curl -X POST http://localhost:9090/-/reload

# Test API metrics
curl http://localhost:8000/metrics

# Test API health
curl http://localhost:8000/health

# Check running services
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

## 🎉 Summary

**Current Status:**
- ✅ Prometheus installed and running
- ✅ Configuration loaded and supports local/docker
- ⏳ Waiting for API to start

**What You Have:**
- Complete metrics infrastructure
- Prometheus collecting and storing metrics
- Ready to scrape API when started
- 30 days of metrics retention

**Next Action:**
→ Start your API service to begin collecting metrics!

**Files to Review:**
1. [MONITORING_QUICKSTART.md](MONITORING_QUICKSTART.md) - Getting started
2. [docs/TELEMETRY_SETUP.md](docs/TELEMETRY_SETUP.md) - Complete documentation
3. [todo.md](todo.md) - Project status

---

**Last Updated:** 2025-10-24
**Prometheus Version:** 3.7.2
**Status:** ✅ Ready for API startup
