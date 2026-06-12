# Freqtrade Deployment Checklist

- Install Docker CLI, Compose, and Colima with `scripts/install-runtime.sh`.
- Copy `.env.example` to `.env`.
- Do not add third-party API keys. Only exchange API keys for OKX/Binance are allowed.
- Keep the local Freqtrade API credentials as internal UI/server credentials only.
- Keep `dry_run: true` until data download, backtest, and dry-run behavior are reviewed.
- Start with `scripts/start-dev.sh`.
- Verify with `scripts/verify-runtime.sh`.
- Verify API scope with `scripts/check-api-scope.sh`.
- Open only `http://localhost:8080/analysis.html`.
- Treat `http://localhost:18080` as internal backend only.
- Review logs in `logs/freqtrade-compose.log` and `user_data/logs/freqtrade.log`.
- Only add exchange API keys after confirming they have no withdrawal permission.
