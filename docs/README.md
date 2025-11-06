# Project Documentation

This repository now groups documentation into two simple buckets so you can find what you need quickly and ignore the noise.

## Active Guides (`docs/guides/`)
Essential references that map directly to the current Binance dashboard and API stack:

- `GUIDES/PIPELINE_USAGE_GUIDE.md` – switching between Binance paper/live and legacy IB pipelines.
- `GUIDES/PIPELINE_IMPLEMENTATION_SUMMARY.md` – how the pipeline selector is wired end to end.
- `GUIDES/README_DASHBOARD.md` – dashboard UI behaviour and data flow.
- `GUIDES/README_SERVER_DEBUG.md` – backend debug workflow.
- `GUIDES/DOCKER_SETUP.md` – containerized deployment checklist.
- `GUIDES/BINANCE_SETUP.md` – Binance keys, environment flags, Redis notes.
- `GUIDES/BINANCE_TRADING_ARCHITECTURE.md` – current orchestrator + data manager design.
- `GUIDES/BINANCE_ARCHITECTURE.md` – detailed architectural breakdown generated for the latest build.

## Archive (`docs/archive/`)
Older reference material kept for posterity (IB setup notes, regulatory writeups, historical session logs, etc.). Nothing in here is required for day‑to‑day development, but it’s still accessible if you need to dig into the history.

---

Keep new documentation in `docs/guides/`. When a guide stops being relevant, move it to `docs/archive/` so the top level stays clean. Use this README as the index.
