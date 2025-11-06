# Project Context

## Overview
This is a quantitative trading dashboard with a FastAPI backend and vanilla JavaScript frontend, focused on Binance trading with support for both paper trading and live execution.

## Current State
- **Primary Focus**: Binance integration (paper + live trading)
- **Architecture**: FastAPI backend, WebSocket market data streaming, Redis for real-time data, PostgreSQL for persistence
- **Deployment**: Docker-based with `docker-compose.yml` and `start.sh` launcher
- **Testing**: Basic API tests in place, end-to-end coverage being expanded

## High-Level Priorities

### 1. Production Readiness
- Harden WebSocket connections and Redis reconnection logic
- Add comprehensive health checks and monitoring
- Ensure bot persistence survives process restarts
- Improve error handling and graceful degradation

### 2. Data Pipeline Stability
- Pipeline switching (Binance paper/live, legacy IB)
- Market data broadcast resilience
- Real-time data flow optimization
- Credential isolation between pipelines

### 3. Frontend Integration
- Connect dashboard to real backend APIs (remove placeholders)
- Implement pipeline switching UI
- Display actual portfolio and risk metrics
- Dynamic watchlist management

### 4. Testing & Quality
- End-to-end smoke tests
- CI-friendly test fixtures for Redis/Postgres
- Automated testing for pipeline switching
- Integration test coverage

### 5. Documentation & Developer Experience
- Keep active guides in `docs/guides/`
- Archive outdated material in `docs/archive/`
- Maintain clear setup instructions for new contributors
- Document deployment and troubleshooting workflows

## Key Technical Components

### Backend (`src/`)
- `main.py` - FastAPI application entry point
- `binance/` - Binance integration, bot orchestration, market data
- `core/` - Risk management, portfolio tracking, analytics
- `routers/` - API endpoints for market data, portfolio, bots, health
- `persistence/` - Database models and bot state management

### Frontend (`frontend/`)
- `index.html` - Dashboard UI
- `js/dashboard.js` - Main dashboard logic
- `js/api.js` - Backend API client
- `js/market-data.js` - WebSocket market data handling

### Infrastructure
- Redis: Real-time market data, pub/sub for WebSocket broadcasts
- PostgreSQL: Portfolio history, bot configurations, trade records
- Docker: Containerized services with orchestration

## Development Workflow
1. Use `./start.sh` to launch services locally
2. Check `docs/guides/` for setup and debugging guides
3. Run tests with `pytest tests/`
4. Review `todo.md` for current backlog

## Related Resources
- **Setup Guides**: See `docs/guides/BINANCE_SETUP.md`, `docs/guides/DOCKER_SETUP.md`
- **Architecture**: See `docs/guides/BINANCE_ARCHITECTURE.md`
- **Debugging**: See `docs/guides/README_SERVER_DEBUG.md`
- **Backlog**: See `todo.md` for task priorities
