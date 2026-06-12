# Project Memory

## Goal

Deploy Freqtrade locally with Docker Compose for Binance dry-run by default, with OKX template support.

## Boundaries

- Default is dry-run only.
- No real exchange credentials are stored in the repository.
- Source and runtime artifacts live under `/Volumes/NINJAV/Codex_Projects/freqtrade-deploy`.

## Runtime

- Start: `scripts/start-dev.sh`
- Stop: `scripts/stop-dev.sh`
- Status: `scripts/dev-status.sh`
- UI: `http://localhost:8080`

## Verification

- Local structural tests: `python3 -m pytest tests`
- Container validation requires Docker Desktop.
