# Quantitative Trading Dashboard

FastAPI backend + vanilla JS frontend for the Binance-focused trading dashboard.  
Use `./start.sh` to spin everything up (backend, optional static frontend server, and log wiring).

## Quick Start

```bash
./start.sh            # launches API on :8000, static assets on :3000 (optional)
export START_FRONTEND=false ./start.sh   # run only the backend
```

Key environment toggles live in `.env.example`. Paper mode and dashboard fixtures stay enabled by default, so the UI works even without Redis/Postgres/Binance credentials.

## Where things live

- `src/` – FastAPI app, routers, Binance orchestrator, persistence.
- `frontend/` – static dashboard assets (JS/CSS/HTML).
- `scripts/` – database setup helpers and schema installers.
- `tests/` – API + integration tests.
- `docs/` – project notes. Active guides in `docs/guides/`, legacy material in `docs/archive/`.
- `logs/` – runtime output captured by the launcher.

## Documentation index

See `docs/README.md` for a curated list of the guides that are still relevant. Older writeups have been moved into `docs/archive/` so the root folder stays clean.

---

Need something that isn't covered here? Check `context.md` for the latest high-level priorities or `todo.md` for the short-term backlog.
