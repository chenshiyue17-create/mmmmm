# Freqtrade Deploy

Docker Compose deployment for Freqtrade on macOS or an Aliyun Linux server, defaulting to OKX sandbox meme-coin trading with a local auto-watch status monitor.

## What This Includes

- Freqtrade stable Docker image deployment.
- OKX sandbox trade-mode config in `user_data/config.json`.
- OKX meme pair template in `config_templates/config.okx.json`.
- Binance exchange template in `config_templates/config.binance.json`.
- Chinese overlay for the native Freqtrade UI in `custom_ui/`.
- OKX meme breakout strategy in `user_data/strategies/DatugouBreakoutStrategy.py`.
- Official Freqtrade command wrappers for config validation, strategy listing, data download, and backtesting.
- Persistent `user_data/`, `logs/`, and `output/` directories.
- `screen`-based start, stop, auto-watch, Gemini optimizer, stability guardian, and status scripts.
- OKX sandbox API connectivity check with macOS Keychain secret loading.
- Structural smoke tests and runtime verification.

See `docs/RESTRUCTURE_DECISION.md` for the current two-project architecture: the original quant project remains the research and strategy-flow source, while this project is the Freqtrade execution runtime.

See `docs/AI_ML_TRADING_FRAMEWORK.md` for the full AI workflow mapping: labels, factors, model tasks, LightGBM/Qlib, LSTM, Transformer, pred signals, deployment gate, and strategy hook.

See `docs/HYBRID_SERVER_LOCAL_ARCHITECTURE.md` for the split runtime model: server executes trades 24/7, local machine computes data/research and optionally syncs bounded strategy files.

## Requirements

### macOS Local

- Homebrew.
- Docker CLI, Docker Compose v2, and Colima. Install them with `scripts/install-runtime.sh`.
- `screen`, already available on macOS.
- Python 3 for local smoke tests.

### Aliyun Server

- Linux server with SSH access.
- Docker Engine and Docker Compose v2. `deploy/aliyun/bootstrap.sh` can install them.
- `git`, `screen`, `curl`, `lsof`, and `python3`.
- Server-local `.env`; never commit exchange API keys.
- Server is the trading execution node. Local research is optional and must not be required for 24h trading.

## Quick Start

```bash
cd /Volumes/NINJAV/Codex_Projects/freqtrade-deploy
scripts/install-runtime.sh
cp .env.example .env
scripts/start-dev.sh
scripts/verify-runtime.sh
```

Open the native Freqtrade UI:

```text
http://localhost:8080/dashboard
```

The default mode is Freqtrade `trade` with `dry_run: false` plus `OKX_SANDBOX_MODE=1`, so orders are routed to OKX sandbox/demo trading. The UI and API bind to `127.0.0.1`, not a public network interface.

## Aliyun Pull Deployment

The target repository is:

```text
https://github.com/chenshiyue17-create/mmmmm.git
```

Run on the Aliyun server after the repository has been pushed:

```bash
export REPO_URL=https://github.com/chenshiyue17-create/mmmmm.git
export BRANCH=main
export APP_DIR=/opt/freqtrade-deploy
bash -lc "$(curl -fsSL https://raw.githubusercontent.com/chenshiyue17-create/mmmmm/main/deploy/aliyun/bootstrap.sh)"
```

The first run creates `/opt/freqtrade-deploy/.env` and stops. Fill the server-local secrets there, then start:

```bash
sudo systemctl start freqtrade-deploy
cd /opt/freqtrade-deploy
scripts/dev-status.sh
```

Open the server UI from your computer through an SSH tunnel:

```bash
ssh -L 8080:127.0.0.1:8080 root@YOUR_SERVER_IP
```

Then open:

```text
http://localhost:8080/analysis.html
```

Full server notes: `deploy/aliyun/README.md`.

## Server Trades, Local Computes

For 24h trading, deploy the execution runtime on Aliyun and keep local computation separate:

- Server: Freqtrade, OKX API, auto-watch, stability guardian, systemd.
- Local: market data, ML/Qlib/Gemini research, parameter generation.
- Sync direction: local -> server, small bounded strategy files only.
- No dependency: server keeps trading when the local computer is off.

Sync local research outputs to the server:

```bash
SERVER_HOST=YOUR_SERVER_IP SERVER_USER=root scripts/sync-research-to-server.sh
```

By default this does not restart server trading. Use `RESTART_AFTER_SYNC=1` only when intentionally reloading strategy/config.

## Commands

```bash
scripts/start-dev.sh
scripts/dev-status.sh
scripts/stop-dev.sh
scripts/start-auto-watch.sh
scripts/stop-auto-watch.sh
scripts/start-gemini-optimizer.sh
scripts/stop-gemini-optimizer.sh
scripts/start-stability-guardian.sh
scripts/stop-stability-guardian.sh
scripts/accumulate-market-data.sh
scripts/train-ml-models.sh
scripts/train-sequence-models.sh
scripts/train-deep-sequence-models.sh
scripts/prepare-qlib-data.sh
scripts/run-qlib-smoke.sh
scripts/build-qlib-research-image.sh
scripts/run-qlib-dump.sh
scripts/run-qlib-qrun.sh
scripts/download-data.sh
scripts/backtest.sh
scripts/validate-config.sh
scripts/verify-runtime.sh
scripts/check-api-scope.sh
scripts/check-okx-sandbox-api.sh
scripts/run-dryrun-trade-test.sh
scripts/run-simulation-test.sh
scripts/security-leak-check.sh
scripts/freqtrade.sh list-strategies --userdir /freqtrade/user_data
scripts/switch-exchange.py okx
scripts/switch-exchange.py binance
python3 -m pytest tests
```

## Chinese UI

The UI is localized through mounted overlay files:

```text
custom_ui/index.html
custom_ui/freqtrade-zh.js
custom_ui/BotBalance-CfdHVrDj.js
```

After editing localization text, restart with:

```bash
scripts/start-dev.sh
```

## Freqtrade Runtime

This project uses the upstream `freqtradeorg/freqtrade:stable` image and the normal Freqtrade command surface:

- `trade` for native UI, REST API, strategy loading, balances, profit, status, and dry-run loop execution.
- `webserver` is only useful for UI-only diagnostics; most trading dashboard endpoints will not work there.
- `download-data` for OHLCV data.
- `backtesting` for strategy evaluation.
- `list-strategies` and `show-config` for validation.

The bundled strategy is `DatugouBreakoutStrategy`, and the active config is `user_data/config.json`.

The active OKX sandbox meme whitelist is:

```text
DOGE/USDT
SHIB/USDT
PEPE/USDT
WIF/USDT
FLOKI/USDT
TURBO/USDT
MEME/USDT
NOT/USDT
BOME/USDT
PNUT/USDT
GOAT/USDT
```

`scripts/start-dev.sh` also starts `freqtrade-auto-watch`, a local monitor that writes:

```text
output/auto-watch-status.json
output/auto-watch-events.jsonl
logs/auto-watch.log
```

The monitor checks every 30 seconds by default. Override it with:

```bash
AUTO_WATCH_INTERVAL_SECONDS=15 scripts/start-auto-watch.sh
```

## 24h Stability And Local Gemini Optimization

Before asking Gemini for optimization, accumulate raw market evidence:

```bash
scripts/accumulate-market-data.sh
```

This downloads the current relevant OKX pairs for the last 90 days and builds:

```text
output/ml_raw_3mo/relevant-pairs.json
output/ml_raw_3mo/features_labels_1h.csv
output/ml_raw_3mo/features_labels_1h_clean.csv
output/ml_raw_3mo/data_quality_report.json
output/ml_raw_3mo/dataset_summary.json
output/ml_raw_3mo/gemini_evidence_pack.json
```

The ML label follows the live-tradable rule:

```text
label_return_5_open_pct = open.shift(-6) / open.shift(-1) - 1
```

That means the model is trained to predict the return from the next candle open to the open after 5 candles, avoiding impossible fills at the previous close.

The dataset also includes alternative labels for comparison:

```text
label_return_12_open_pct = open.shift(-13) / open.shift(-1) - 1
label_barrier_long_12 = 1 when +3% take-profit is touched before -2% stop-loss within 12 candles
label_return_5_atr = label_return_5_open_pct / atr_14_pct
label_triclass_5_atr = -1 / 0 / 1 by ATR-normalized return thresholds
```

The ATR-normalized label prevents the model from treating a 1% move on a quiet coin and a 1% move on a high-volatility coin as the same event. The tri-class label creates an explicit no-trade/chop bucket, so the learning target is not forced to guess long or short when the next 5 candles are just noise. Defaults:

```text
ML_TRICLASS_DOWN_ATR=-0.6
ML_TRICLASS_UP_ATR=0.6
ML_MIN_ATR_PCT_FOR_LABEL=0.01
```

The raw dataset is preserved. Training defaults to the clean dataset, which removes pairs and rows failing quality checks:

```text
rows >= 1000
zero volume candle rate <= 20%
volume_ratio_24 median >= 0.01
non-zero forward-return label rate >= 20%
row volume > 0 and rolling volume mean > 0
```

Train the local ML views after data accumulation:

```bash
scripts/train-ml-models.sh
scripts/train-sequence-models.sh
scripts/train-deep-sequence-models.sh
```

The trainer implements the three task views from the same label:

```text
Regression: pred_return_5_open_pct
Binary classification: pred_up_probability
Cross-sectional ranking: pred_rank_score
```

It also evaluates auxiliary targets:

```text
long_horizon_12_regression
long_horizon_12_classification
barrier_long_12_classification
atr_normalized_5_regression
atr_triclass_5_classification
```

Gemini receives the redacted 90-day evidence pack, not raw secrets and not an empty prompt. The evidence pack includes pair universe, raw/clean row counts, data quality rejections, factor correlations, label distributions, ATR-normalized labels, tri-class distribution, sample rows, model metrics, latest pred signals, and deployment-gate status. Treat Gemini output as an advisory research memo unless the out-of-sample gate passes.

Artifacts:

```text
output/ml_models/training_report.json
output/ml_models/predictions_latest.csv
output/ml_models/latest_signals.json
output/ml_models/sklearn_hist_gradient_models.pkl
```

The sequence training layer builds 24-candle feature windows from the same clean dataset and trains a runnable lag-window baseline for the same three views:

```text
Sequence regression: seq_pred_return_5_open_pct
Sequence binary classification: seq_pred_up_probability
Sequence cross-sectional ranking: seq_pred_rank_score
```

Artifacts:

```text
output/ml_sequence_models/sequence_report.json
output/ml_sequence_models/sequence_predictions_latest.csv
output/ml_sequence_models/sequence_window_baseline.pkl
```

The current Freqtrade image does not include `torch`, so true LSTM and Transformer training is gated and reported as `skipped_missing_torch` instead of being faked. The sequence report still records the intended role of each deep model: LSTM for short-term sequence memory and Transformer for longer-window attention.

For real LSTM and Transformer training, use the isolated PyTorch CPU research image:

```bash
scripts/train-deep-sequence-models.sh
```

This builds `deep-research` without exchange API secrets, trains both models on the same 24-candle sequence tensor, and writes:

```text
output/ml_deep_sequence_models/deep_sequence_report.json
output/ml_deep_sequence_models/deep_sequence_predictions_latest.csv
output/ml_deep_sequence_models/lstm_regressor.pt
output/ml_deep_sequence_models/transformer_regressor.pt
```

The deep report exposes LSTM pred, Transformer pred, an ensemble pred, derived timing classification, and cross-sectional ranking metrics. These remain research signals until ranking and deployment gates are positive out of sample.

Pred signals are protected by an out-of-sample deployment gate. The model stays in `research_only_do_not_trade` mode unless all checks pass:

```text
regression corr >= 0.10
classification precision >= 0.55
ranking Spearman >= 0.05
```

The current Freqtrade image does not include LightGBM, so the script uses sklearn `HistGradientBoosting` as a local gradient-boosting fallback. If LightGBM is installed later, this training layer can be switched without changing the label/factor dataset contract.

## Qlib Research Fusion

Microsoft Qlib is deployed under:

```text
vendor/qlib
```

Qlib is fused as a research/model/signal-analysis layer. Freqtrade remains the only execution engine, and Qlib signals must pass the same out-of-sample deployment gate before they can influence strategy behavior. The `qlib-research` Docker service does not receive exchange API keys.

Prepare Qlib-ready data from the existing OKX factor/label dataset:

```bash
scripts/prepare-qlib-data.sh
scripts/run-qlib-smoke.sh
```

Artifacts:

```text
output/qlib/okx_1h/csv/
output/qlib/okx_1h/qlib_bin/
output/qlib/okx_1h/qlib_okx_lgbm_config.yaml
output/qlib/okx_1h/manifest.json
output/qlib/okx_1h/qlib_fusion_report.json
output/qlib/okx_1h/mlruns/
```

The generated CSV files use Qlib's expected import shape: one file per symbol, with `date`, `symbol`, OHLCV, factors, and labels. Build the isolated Qlib research image:

```bash
scripts/build-qlib-research-image.sh
```

Convert the CSV set to Qlib binary storage:

```bash
scripts/run-qlib-dump.sh
```

Then run the generated LightGBM workflow. The default qrun trains the model, writes `pred.pkl`, and records IC / Rank IC signal analysis. Portfolio backtests are intentionally not enabled in the default qrun because Qlib's portfolio benchmark path requests 1-minute data, while this project currently prepares 60-minute OKX bars.

```bash
scripts/run-qlib-qrun.sh
```

`scripts/start-dev.sh` also starts:

```text
freqtrade-gemini-optimizer
freqtrade-stability-guardian
```

The Gemini optimizer calls the local `gemini` CLI in plan mode. It receives a redacted trading snapshot plus the 90-day factor/label evidence pack plus the latest ML training report and pred signals, then writes advisory reports:

```text
output/gemini-optimizer-status.json
output/gemini-optimizer-contract.json
output/gemini-optimizer-request.json
output/gemini-optimizer-response.json
output/gemini-optimizer-actions.jsonl
output/gemini-optimizer-backlog.json
output/gemini-optimizer-report.md
logs/gemini-optimizer.log
```

It now has an autopilot interface. Gemini can emit bounded `update_strategy_flow` JSON actions; the local validator applies them automatically to:

```text
user_data/datugou_flow.autopilot.json
```

The strategy reads this overlay at runtime. The autopilot is allowed to update only bounded strategy parameters such as breakout window, volume ratio, momentum threshold, stop-loss percentage, take-profit percentage, and trailing-stop percentage. It does not hot-edit strategy source code, expose secrets, change position size, enable leverage, or switch real trading modes.

Run a local autopilot smoke test:

```bash
python3 scripts/gemini-autopilot-smoke.py
```

Tune cadence and automation with:

```bash
GEMINI_AUTOMATION_ENABLED=1
GEMINI_AUTOMATION_MIN_CONFIDENCE=0.55
GEMINI_OPTIMIZER_INTERVAL_SECONDS=900 scripts/start-gemini-optimizer.sh
```

The stability guardian checks Docker, Freqtrade API, auto-watch freshness, Gemini optimizer session health, the Freqtrade log screen, and macOS sleep prevention. It runs indefinitely by default and only stops when you run the stop script. After repeated failures it recovers Docker/Colima, the Freqtrade container, auto-watch, Gemini optimizer, analysis snapshots, and the `caffeinate` sleep-prevention session:

```text
output/stability-guardian-status.json
output/stability-guardian-events.jsonl
logs/stability-guardian.log
```

Useful overrides:

```bash
GUARDIAN_RUNTIME_HOURS=0 scripts/start-stability-guardian.sh
GUARDIAN_RUNTIME_HOURS=24 scripts/start-stability-guardian.sh
GUARDIAN_FAILURE_THRESHOLD=3 scripts/start-stability-guardian.sh
```

`GUARDIAN_RUNTIME_HOURS=0` means run until manual stop. The normal project startup uses this mode automatically:

```bash
scripts/start-dev.sh
scripts/stop-dev.sh
```

Runtime mode defaults to:

```bash
FREQTRADE_RUN_MODE=trade
```

For trading safety, OpenAPI docs are disabled and only exchange API variables are allowed. Freqtrade displays runmode `live` because `dry_run` is disabled, but `OKX_SANDBOX_MODE=1` forces OKX sandbox/demo trading.

The strategy has a guarded AI signal hook:

```bash
ML_SIGNAL_FILTER_ENABLED=0
```

Default `0` means the breakout strategy runs without ML filtering. If set to `1`, `DatugouBreakoutStrategy` reads `output/ml_models/latest_signals.json` through the mounted `/freqtrade/output` path and permits entries only when `deployment_gate.passed` is true and the pair is a bullish long candidate. If the gate fails, the ML filter blocks entries instead of forcing trades.

## Read-Only Proxy

The read-only proxy is optional and disabled by default:

```bash
READONLY_PROXY_ENABLED=0
```

If enabled manually, Freqtrade moves behind:

```text
http://localhost:18080
```

The proxy blocks:

```text
/api/*
/openapi.json
/docs
/redoc
/login
/dashboard
/balance
/open_trades
/trade_history
/pairlist
```

## API Scope

Only exchange APIs are allowed:

```text
OKX_KEY
OKX_SECRET
OKX_PASSWORD
BINANCE_KEY
BINANCE_SECRET
```

Do not add third-party API keys for signals, alerts, AI, messaging, market-data vendors, or automation services. Telegram and webhooks are disabled, OpenAPI docs are disabled, and the API scope checker enforces this rule:

```bash
scripts/check-api-scope.sh
scripts/validate-config.sh
```

## OKX And Binance

The active config is `user_data/config.json` and defaults to Binance:

```json
"exchange": {
  "name": "binance"
}
```

For Binance, set these exchange-only variables in `.env` when you are ready to test with real exchange credentials:

```bash
BINANCE_KEY=
BINANCE_SECRET=
```

To switch exchanges without manual JSON editing:

```bash
scripts/switch-exchange.py okx
scripts/switch-exchange.py binance
scripts/start-dev.sh
```

OKX template remains available:

```bash
OKX_KEY=
OKX_SECRET=
OKX_PASSWORD=
```

Store OKX credentials in macOS Keychain instead of `.env`:

```bash
OKX_KEY='your-api-key' OKX_SECRET='your-secret-key' scripts/set-okx-keychain.sh
OKX_PASSWORD='your-okx-api-passphrase' scripts/set-okx-keychain.sh
```

Or enter the OKX passphrase without showing it in the terminal:

```bash
scripts/set-okx-keychain.sh --prompt-password
```

If the report says `api_key_environment_mismatch`, the key is valid for OKX live read-only access but is not a Demo Trading API key. Create a separate API key inside OKX Demo Trading, then store that key/secret/passphrase in Keychain before rerunning the simulation test.

Run the OKX sandbox connectivity test:

```bash
scripts/check-okx-sandbox-api.sh
```

Run the full local simulation acceptance test:

```bash
scripts/run-simulation-test.sh
```

The report is written to:

```text
output/okx-sandbox-api-check.json
output/dryrun-trade-test.json
output/simulation-test-report.json
output/simulation-test-report.md
output/security-leak-check.json
```

Run a full sensitive-value leak check:

```bash
scripts/security-leak-check.sh
```

To check a one-off value without writing it to project files:

```bash
EXTRA_SECRET='value-to-check' scripts/security-leak-check.sh
```

Note: with the current `freqtradeorg/freqtrade:stable` image, OKX trade-mode market loading may fail in CCXT with a `NoneType` market-id sorting error unless CCXT sandbox mode is enabled with `set_sandbox_mode(true)`. Freqtrade does not expose native OKX demo trading in this image, so OKX sandbox API checks run through `scripts/check-okx-sandbox-api.sh`. Binance remains the default UI runtime because it starts cleanly in dry-run trade mode. This does not lock the project to simulation; live trading still requires deliberate review, complete OKX passphrase setup, `dry_run: false`, and small-stake validation.

Keep `dry_run: true` while validating.

## Live Trading Safety

- Never enable withdrawal permission on API keys.
- Do not create or paste third-party API keys into this project.
- Keep API keys IP-restricted when the exchange supports it.
- Run backtests and dry-run before live trading.
- Change `dry_run` to `false` only after reviewing strategy, pair list, stake size, and logs.
- Start with small stake sizes.

## Troubleshooting

- `Docker CLI is not installed`: run `scripts/install-runtime.sh`.
- `Docker Compose v2 is not available`: run `scripts/install-runtime.sh`.
- `Config file not found` inside the container: restart Colima with `/Volumes/NINJAV` mounted, or run `scripts/install-runtime.sh`.
- UI not opening: run `scripts/dev-status.sh`, then inspect `logs/freqtrade-compose.log`.
- Exchange connection errors: confirm region availability, API key permissions, and pair symbols.
- Port conflict: set `FREQTRADE_UI_PORT` in `.env`.

## References

- Freqtrade documentation: https://www.freqtrade.io/
- Freqtrade Docker docs: https://www.freqtrade.io/en/stable/docker_quickstart/
- Freqtrade GitHub: https://github.com/freqtrade/freqtrade
