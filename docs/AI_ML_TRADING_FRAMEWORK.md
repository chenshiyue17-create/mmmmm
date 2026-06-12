# AI ML Trading Framework

This project maps the AI trading workflow to a trainee workflow:

```text
出题(define labels) -> 教材(build factors) -> 学习(train models) -> 上岗(output gated signals)
```

Freqtrade remains the execution engine. AI models produce research signals first. A strategy may consume those signals only through the deployment gate.

## 1. 出题: Labels

The primary label is live-tradable because it uses the next candle open as entry:

```text
label_return_5_open_pct = open.shift(-6) / open.shift(-1) - 1
```

Meaning:

- Entry price: next candle open, `open.shift(-1)`.
- Exit price: open after 5 candles, `open.shift(-6)`.
- Positive label means the next 5-candle open-to-open return is bullish.

The framework intentionally avoids:

- 1-candle prediction as the primary target, because short-horizon noise dominates.
- Previous close as the denominator, because live orders cannot fill at yesterday's close.

Additional labels exist for comparison:

```text
label_return_12_open_pct
label_barrier_long_12
label_return_5_atr
label_triclass_5_atr
rank_label_return_5
```

## 2. 教材: Factors

The factor set is built from downloaded OKX OHLCV data:

```text
return_1, return_3, return_6, return_24
volatility_24, atr_14_pct
volume_ratio_24
breakout_distance_pct
rsi_14
macd, macd_hist
market_return_6, market_return_24
return_6_excess, return_24_excess
cs_rank_return_6, cs_rank_return_24
cs_rank_volume_ratio_24, cs_rank_rsi_14
```

Pipeline command:

```bash
scripts/accumulate-market-data.sh
```

Core artifacts:

```text
output/ml_raw_3mo/features_labels_1h.csv
output/ml_raw_3mo/features_labels_1h_clean.csv
output/ml_raw_3mo/data_quality_report.json
output/ml_raw_3mo/dataset_summary.json
```

## 3. 学习: Model Tasks

The same label supports three views:

```text
Regression: predict exact return -> pred_return_5_open_pct
Binary classification: predict up/down -> pred_up_probability
Cross-sectional ranking: compare pairs -> pred_rank_score
```

Ranking modes:

- Head-only: long the strongest candidates.
- Balanced: long strong candidates and avoid or short weak candidates when the engine supports it.
- Tail-only: identify weak candidates to avoid or short in a short-enabled system.

This project is spot-long only, so ranking is used as head-only long-candidate selection and avoidance evidence.

## 4. Models

### Local Gradient Boosting

Command:

```bash
scripts/train-ml-models.sh
```

Role:

- Fast tabular baseline.
- No temporal memory.
- Produces regression, binary classification, and ranking outputs.

Artifacts:

```text
output/ml_models/training_report.json
output/ml_models/latest_signals.json
output/ml_models/predictions_latest.csv
```

### Qlib LightGBM

Commands:

```bash
scripts/prepare-qlib-data.sh
scripts/run-qlib-smoke.sh
scripts/build-qlib-research-image.sh
scripts/run-qlib-dump.sh
scripts/run-qlib-qrun.sh
```

Role:

- Isolated Microsoft Qlib research workflow.
- Uses LightGBM and records IC / Rank IC signal analysis.
- Does not receive exchange API keys.

Artifacts:

```text
output/qlib/okx_1h/qlib_okx_lgbm_config.yaml
output/qlib/okx_1h/mlruns/
```

### Sequence Baseline

Command:

```bash
scripts/train-sequence-models.sh
```

Role:

- Builds 24-candle lag windows.
- Provides a runnable sequence baseline when deep-learning dependencies are unavailable.

Artifacts:

```text
output/ml_sequence_models/sequence_report.json
output/ml_sequence_models/sequence_predictions_latest.csv
```

### LSTM And Transformer

Command:

```bash
scripts/train-deep-sequence-models.sh
```

Role:

- LSTM: short-term sequence memory over recent candles.
- Transformer: attention over longer feature windows.
- Both output 5-candle return predictions where positive pred means bullish.

Artifacts:

```text
output/ml_deep_sequence_models/deep_sequence_report.json
output/ml_deep_sequence_models/deep_sequence_predictions_latest.csv
output/ml_deep_sequence_models/lstm_regressor.pt
output/ml_deep_sequence_models/transformer_regressor.pt
```

## 5. 上岗: Signal Gate And Strategy Hook

Signals are allowed to influence strategy behavior only through:

```text
output/ml_models/latest_signals.json
deployment_gate.passed == true
ML_SIGNAL_FILTER_ENABLED=1
```

Default:

```text
ML_SIGNAL_FILTER_ENABLED=0
```

When enabled, `DatugouBreakoutStrategy` reads the latest signal file from `/freqtrade/output/ml_models/latest_signals.json`. If the gate fails, the ML filter blocks entries instead of forcing trades.

## 6. Core Formula

```text
标签定目标，因子给信息，模型学映射，pred 出信号。
择时看阈值，择币看排名。
```

In this project:

```text
label_return_5_open_pct -> factors -> models -> pred -> deployment gate -> strategy filter -> Freqtrade
```
