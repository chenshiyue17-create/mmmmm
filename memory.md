# Project Runtime Memory

- Initialized project memory.

- 20260610T093626Z: Created Freqtrade Docker deployment project on NINJAV with dry-run Binance config, OKX template, screen lifecycle scripts, README, tests. Docker Desktop is not installed locally, so runtime start is blocked until installed; local pytest smoke tests pass.

- 20260610T100158Z: Completed one-shot Freqtrade deployment: installed Docker CLI, Docker Compose, Colima via Homebrew; configured Colima mount for /Volumes/NINJAV; started freqtradeorg/freqtrade:stable dry-run container with Binance default and OKX template; added install/start/stop/status/download/backtest/verify scripts; verified pytest, container Up, screen session, and /api/v1/ping.

- 20260610T110930Z: Freqtrade deployment UI safety hardening: removed login/password controls from custom analysis page, blocked native trading/dashboard routes with Chinese safety notice, kept backend auth intact, verified pytest/runtime/browser checks.

- 20260610T111604Z: Freqtrade API scope hardening: user prefers only exchange APIs, no third-party APIs. Closed OpenAPI docs, documented OKX/Binance-only credentials, added scripts/check-api-scope.sh and tests, restarted service and verified runtime/browser.

- 20260610T111911Z: Evaluated Freqtrade deployment tool: tests/runtime pass, exchange-only API scope pass, local UI works; found residual risk that /openapi.json is still exposed by Freqtrade despite config flag, and Binance env injection is not complete.

- 20260610T112642Z: One-step hardening completed: added read-only local proxy on 8080, moved Freqtrade backend to 18080, blocked /api/* and /openapi.json at user entrypoint, added exchange switcher, fixed screen cleanup, verified pytest/runtime/browser.

- 20260610T112946Z: Added desktop shortcut /Users/cc/Desktop/Freqtrade只读分析.command and project launcher scripts/open-analysis.sh. Shortcut starts read-only proxy architecture and opens analysis page. Verified permissions, pytest, runtime.

- 20260610T113254Z: Desktop shortcut did not visibly launch for user. Added robust desktop-launch.sh with PATH and logs, updated .command, created /Users/cc/Desktop/Freqtrade只读分析.app via osacompile. Verified app opens and logs successful launch.

- 20260610T113723Z: User requested cancel disabling. Restored native Freqtrade UI by default: READONLY_PROXY_ENABLED=0, backend port 8080, start path /dashboard, disabled JS safety block unless FT_DISABLE_NATIVE_UI=true. Verified API/openapi/dashboard 200 and browser login page visible.

- 20260610T114331Z: Implemented persistent local UI login via AUTO_LOGIN_ENABLED=1. Added generate-local-login.py to create ignored local-login.json from .env, mounted into UI assets, and freqtrade-zh.js auto-fills/submits login form. Verified browser reaches dashboard without password field.

- 20260610T115410Z: Fixed Chinese localization complaint. Added cache-busted freqtrade-zh.js, more translations, periodic translation pass, safer footer-only analysis link insertion, and forceBrandText for FreqtradeUI logo. Verified browser no core English remains.

- 20260610T144554Z: Freqtrade deploy 方向纠偏：停止快照分析主线，改为原生 Freqtrade 功能闭环；启动真实 freqtradeorg/freqtrade 容器、验证 API/UI、策略 list-strategies、配置 validate-config、测试通过。

- 20260611T084334Z: Fixed unusable Freqtrade UI by switching default from webserver to trade dry-run mode, loading DryRunRsiStrategy, enabling dry-run force-entry UI operations, switching active exchange to Binance because OKX trade-mode market loading fails with CCXT NoneType sorting error. Verified status/profit/balance 200 and browser dashboard usable.

- 20260611T090213Z: OKX sandbox API uses ccxt set_sandbox_mode(True); public market check passes, private balance requires OKX_PASSWORD/passphrase; keep Freqtrade UI on Binance dry-run until OKX passphrase and Freqtrade OKX market-load issue are resolved.

- 20260611T091344Z: Simulation delivery now includes run-dryrun-trade-test open/close cycle, run-simulation-test aggregate report, OKX sandbox public market proof, and explicit OKX_PASSWORD/passphrase blocker for private OKX balance/order testing.

- 20260611T174836Z: Freqtrade OKX sandbox consolidated as the only active trading UI: stopped local 8088 paper console/watch, restarted Freqtrade on 8080, verified OKX sandbox mode and balances, fixed desktop command to open /dashboard only, validated runtime/tests.

- 20260611T181319Z: Restructured quant stack after user feedback: researched open-source bot options, kept Freqtrade as execution layer, preserved /Users/cc/Documents/量化 as strategy research source, imported datugou strategy-flow YAML into Freqtrade JSON params, replaced fixed whitelist with dynamic OKX USDT PercentChangePairList chain, verified tests/runtime/auto-watch.

- 20260611T181929Z: Started OKX sandbox Freqtrade trading, confirmed 3 active trade records, set auto-watch default to 30s, fixed verify-runtime long-running heartbeat check, verified tests/runtime/browser dashboard. Do not store or reveal secrets.

- 20260612T120727Z: OKX sandbox virtual trading is the active safe execution mode: Freqtrade dry_run=false with OKX_SANDBOX_MODE=1 is allowed, UI must label it OKX 模拟盘 rather than 实盘/dry-run, and validation should include a forceenter/forceexit sandbox trade plus security leak scan.
