# Binance Dashboard & Bot Orchestration Overview

This repository now exposes a Binance-focused trading stack built around FastAPI services, Redis-backed market data, and an asynchronous bot orchestrator. The goal is to support multiple automated strategies running in parallel while surfacing their state through the dashboard and API.

## Current Capabilities
- **Bot orchestration** via `src/binance/bot_orchestrator.py`, with lifecycle management (create/start/stop/remove) and shared connectivity for WebSocket market data plus REST trading.
- **REST trading client** in `src/binance/rest_client.py` covering market, limit, and stop-loss orders, open-order management, and exchange metadata, with an always-on simulated “test mode” fallback.
- **Strategy framework** provided by `src/binance/trading_bot.py`, including a base bot, position tracking, and per-trade risk sizing; concrete strategies live under `src/binance/strategies/` (currently an RSI example).
- **FastAPI bot endpoints** in `src/api/routers/bots.py` that surface orchestration controls and portfolio summaries once the orchestrator is enabled at startup.
- **Frontend dashboard** (vanilla JS) still rendered from `frontend/` via the FastAPI application for visual monitoring.

## Key Architectural Pieces
- **Market data pipeline** (`src/binance/data_manager.py` + `src/binance/websocket_client.py`): connects to Binance WebSocket streams, caches candles and latest prices in Redis, and feeds every active bot from a shared datastore.
- **Order execution** (`BinanceRESTClient`): signs requests with API credentials when provided, but automatically stays in simulated mode if API keys are missing or you keep `BINANCE_TEST_MODE=true`.
- **Trading bot base** (`TradingBot`): runs the strategy loop, constructs orders, enforces stop-loss/take-profit, and reports performance metrics.
- **RSI strategy** (`src/binance/strategies/rsi_strategy.py`): demonstrates a signal generator returning buy/hold actions based on configurable RSI thresholds.
- **Bot orchestrator** (`BotOrchestrator`): owns the shared REST client and data manager, spins a background listener for WebSocket traffic, and keeps per-bot asyncio tasks under control. The FastAPI router injects this orchestrator through `bots.set_orchestrator(...)` during application startup.

### FastAPI Integration
`src/api/main.py` wires the orchestrator when the environment variable `BINANCE_ENABLE_BOTS` is set to `true`. During startup it reads:
- `BINANCE_API_KEY` / `BINANCE_API_SECRET` – optional (test mode enforced when absent)
- `BINANCE_TEST_MODE` – keep `true` for paper trading
- `BINANCE_TESTNET` – toggle between testnet and production REST endpoints
- `REDIS_HOST` / `REDIS_PORT` – upstream Redis instance for candle caching

If initialization fails (for example because Redis is unavailable), the orchestrator is skipped and the bot endpoints return `503` instead of crashing the service.

## Operating The Bot Orchestrator
1. Start Redis and ensure Binance testnet credentials (or keep test mode on).
2. Export the environment variables above and set `BINANCE_ENABLE_BOTS=true` before launching FastAPI (e.g. via `uvicorn src.api.main:app`).
3. Use the following API routes under `/api/v1/bots`:
   - `POST /create` – register a bot (`RSIStrategy` is available by default).
   - `POST /{bot_id}/start` and `/stop` – control execution.
   - `GET /{bot_id}/stats` or `GET /` – inspect per-bot metrics.
   - `GET /portfolio/summary` – aggregate capital & PnL across bots.
   - `POST /start-all` / `/stop-all` – batch control.
   - `GET /health` – orchestrator and data pipeline health report.

Bots share the background listener started by the orchestrator, so subscribing a new symbol is as simple as creating a bot for it.

## Known Limitations & Gaps
- The dashboard’s market widgets still rely on the mock `MarketDataGenerator` inside `src/api/main.py`; wiring them directly to Redis-backed Binance data is tracked separately.
- Execution paths run in perpetual test mode unless real API keys are provided; production hardening (persistence, audit trails, hedge handling) remains future work.
- Risk controls are intentionally lightweight—there is no portfolio-wide exposure guard, margin management, or compliance pipeline yet.
- Redis connectivity is mandatory for live bots; consider adding graceful degradation or persistent storage for environments without Redis.
- There is not yet an automated process manager or deployment recipe. Use the provided Docker assets as a starting point.

## Backlog
- Replace the mock dashboard data sources with Binance data served from Redis so the UI reflects real streaming prices and bot state.
- Persist bot configuration, trade history, and performance metrics to the PostgreSQL layer for recovery after restarts.
- Expand the strategy catalog (e.g., MACD, mean reversion) and add parameter validation utilities.
- Enrich risk management with trailing stops, max drawdown guards, and portfolio-level throttles.
- Build integration tests around the orchestrator and API router to catch regressions in async lifecycle management.

Refer to `docs/` for deeper design notes, including the Binance architecture document generated alongside this README.
