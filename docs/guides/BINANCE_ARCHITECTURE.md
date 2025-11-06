# Binance Trading Architecture

This document captures the current Binance-focused architecture that powers the trading bots, orchestration layer, and dashboard/API surface.

## High-Level Overview
- **Market Data**: `BinanceWebSocketClient` connects to Binance (testnet or production) and streams kline/ticker data. `BinanceDataManager` caches the most recent candles and prices in Redis so every bot and API call shares the same feed.
- **Order Execution**: `BinanceRESTClient` wraps Binance REST endpoints (orders, account info, exchange metadata) and supports a built-in simulation mode that mirrors responses without touching live capital.
- **Trading Bots**: Each bot is an instance of `TradingBot`, which runs a strategy loop, performs risk sizing, opens/closes positions via the REST client, and tracks PnL. Strategies inherit from `TradingStrategy`; `RSIStrategy` is the first example.
- **Bot Orchestration**: `BotOrchestrator` maintains the shared clients, creates asyncio tasks per bot, and exposes a simple API for lifecycle control. FastAPI injects the orchestrator into `src/api/routers/bots.py` during application startup.
- **API Layer**: The main FastAPI app hosts portfolio/trade endpoints, bot management routes, and the dashboard frontend. Bot routes are available under `/api/v1/bots` when the orchestrator is enabled with `BINANCE_ENABLE_BOTS=true`.
- **Frontend**: The `frontend/` bundle consumes the FastAPI endpoints and WebSocket feeds to render real-time dashboards. At the moment it still reads from the mock market generator until the Redis-backed feed is wired in.

## Component Details
### Market Data Pipeline (`src/binance/data_manager.py`)
- Maintains a single WebSocket connection per subscribed symbol.
- Persists the latest 200 closed candles per interval in Redis lists (`candles:{SYMBOL}:{INTERVAL}`) and the latest price in `price:{SYMBOL}` keys.
- Provides async helpers `get_candles` and `get_latest_price` for bots and future API endpoints.
- Health checks confirm Redis availability and WebSocket status for monitoring.

### REST Client (`src/binance/rest_client.py`)
- Handles request signing, order creation (market, limit, stop-loss), cancellation, balance queries, and exchange metadata.
- Uses `aiohttp` for asynchronous requests.
- Runs in safe simulation mode (`test_mode=True`) whenever API keys are missing or explicitly requested, returning deterministic stub responses that mimic Binance payloads.

### Trading Bot Core (`src/binance/trading_bot.py`)
- Exposes `TradingStrategy` abstract class with `analyze` and `get_parameters` hooks.
- `TradingBot` orchestrates the trading loop: fetch candles, evaluate strategy, size positions, submit orders, and manage exits (stop-loss/take-profit).
- Tracks per-bot stats (`total_pnl`, `win_rate`, open position) for exposure through the API.
- Provides graceful shutdown by closing open positions when the bot is stopped.

### RSI Strategy (`src/binance/strategies/rsi_strategy.py`)
- Calculates RSI from candle history (requires at least `period` candles).
- Emits `BUY` when RSI crosses below an oversold threshold and back above it, `SELL` is handled at the bot-level via exits.
- Returns reasoning metadata so bot logs explain trade decisions.

### Bot Orchestrator (`src/binance/bot_orchestrator.py`)
- Creates and caches bots keyed by `bot_id`.
- Starts a shared streaming task (`BinanceDataManager.start_streaming`) and keeps one REST client session alive for all bots.
- Offers async methods for create/start/stop/remove, as well as portfolio-level summaries and health checks.
- Ensures shutdown closes all tasks, the data manager, and the REST client session.

### API Router (`src/api/routers/bots.py`)
- Provides CRUD-like endpoints to control bots, plus aggregated stats and health info.
- Injects strategy instances dynamically (currently only RSI) based on request payloads.
- Returns `503` if the orchestrator is not initialized, preventing undefined behavior when the backend is running without Redis or Binance connectivity.

## Data Flow
1. FastAPI starts and, if `BINANCE_ENABLE_BOTS=true`, initializes `BotOrchestrator` with credentials and Redis settings.
2. When a bot is created, the orchestrator subscribes to the symbol via `BinanceDataManager`, ensuring future candle updates populate Redis.
3. The orchestrator spawns an asyncio task executing `TradingBot.start()`, which loops on `get_candles` + strategy analysis and optionally places orders through `BinanceRESTClient` (simulation by default).
4. Bot stats and portfolio summaries are stored in memory and exposed through the `/api/v1/bots` endpoints for the dashboard or external automation.
5. On shutdown, the orchestrator stops all bots, cancels the WebSocket listener, flushes Redis connections, and closes the REST session.

## Gaps & Risks
- **Dashboard Data**: The FastAPI `MarketDataGenerator` still serves mock equities data to the frontend. Replacing it with Redis-backed Binance data remains outstanding.
- **Persistence**: Bot configuration, trade history, and performance stats live in memory; restarts lose that state. Persisting to PostgreSQL is a priority for reliability.
- **Advanced Risk Controls**: Position sizing is basic and does not enforce portfolio-wide limits, trailing stops, or drawdown thresholds. Integrating the richer `src/core` risk modules is future work.
- **Scaling**: `BinanceDataManager` runs a single listener; scaling across processes or hosts will require coordination (Redis Pub/Sub, shared queues, or sharded orchestrators).
- **Error Handling**: Network interruptions (Redis, WebSocket, REST) rely on simple retry/log patterns. Production deployments should add exponential backoff, alerting, and circuit breakers.
- **Testing**: There are no automated tests around the orchestrator or strategy loop. Creating integration tests with faked Redis/Binance services will help guard against regressions.

## Deployment Notes
- Redis is required for live bots. Ensure it is reachable before enabling the orchestrator.
- Keep `BINANCE_TEST_MODE=true` while validating functionality; switch to `false` only after providing production credentials and reviewing order sizing logic.
- Run the FastAPI service with `uvicorn src.api.main:app --reload` during development. Use `docker-compose` or systemd for long-running deployments (see the docker assets in the repository).
- Monitor the `/api/v1/bots/health` endpoint to verify websocket, redis, and bot task status.

This architecture doc should be updated whenever new strategies, risk modules, or persistence layers are added to keep the overview accurate.
