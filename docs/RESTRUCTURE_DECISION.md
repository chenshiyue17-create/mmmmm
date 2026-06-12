# Quant Stack Restructure Decision

## Decision

Use Freqtrade as the execution runtime and keep `/Users/cc/Documents/量化` as the research and strategy-authoring project.

This avoids rewriting the whole system while still using a mature open-source execution engine for OKX sandbox orders.

## Current Roles

### Research Project

Path: `/Users/cc/Documents/量化`

Role:

- Strategy research and backtest experiments.
- Strategy-flow authoring in `strategies/datugou_profit_flow.yaml`.
- Candidate-pool ideas and OKX market research tasks.
- Historical reports and local analysis artifacts.

### Execution Project

Path: `/Volumes/NINJAV/Codex_Projects/freqtrade-deploy`

Role:

- Freqtrade Docker runtime.
- OKX sandbox API execution.
- Dynamic pair discovery from OKX USDT spot markets.
- Web UI, balances, trades, order state, and logs.
- Local `auto-watch` status monitor.

## Bridge

`scripts/import-research-flow.py` imports:

```text
/Users/cc/Documents/量化/strategies/datugou_profit_flow.yaml
```

and writes:

```text
user_data/datugou_flow.json
```

`DatugouBreakoutStrategy` consumes that JSON for:

- breakout lookback
- volume window
- momentum window
- minimum volume ratio
- minimum momentum percent

`scripts/start-dev.sh` runs the import automatically before starting Freqtrade.

## Dynamic Pair Discovery

The execution config no longer uses a fixed meme whitelist.

The boundary is:

```text
.*/USDT
```

The active pairlist chain is:

```text
PercentChangePairList -> SpreadFilter -> PriceFilter -> ShuffleFilter
```

This makes the system follow current OKX movers while blacklisting large majors, stable pairs, and leveraged-token patterns.

## Why Freqtrade Remains The Base

After checking current open-source projects, Freqtrade remains the best fit for this local stack because it already provides:

- OKX exchange support through CCXT.
- Dynamic pairlist plugins.
- Strategy lifecycle hooks.
- Order management, stoploss, ROI, Web UI, REST API, and persistence.
- Docker-friendly unattended runtime.

Hummingbot is stronger for market-making/liquidity strategies. Jesse is strong for strategy research. For this project, execution reliability and dynamic exchange pairlists matter more, so Freqtrade remains the execution layer.
