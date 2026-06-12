#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(os.getenv("FT_PROJECT_ROOT", Path(__file__).resolve().parents[1]))
RUNTIME_ROOT = Path(os.getenv("QLIB_RUNTIME_ROOT", ROOT))
SOURCE_DATASET = Path(os.getenv("QLIB_SOURCE_DATASET", ROOT / "output" / "ml_raw_3mo" / "features_labels_1h_clean.csv"))
QUALITY_PATH = ROOT / "output" / "ml_raw_3mo" / "data_quality_report.json"
OUTPUT_ROOT = Path(os.getenv("QLIB_OUTPUT_DIR", ROOT / "output" / "qlib" / "okx_1h"))
CSV_DIR = OUTPUT_ROOT / "csv"
QLIB_BIN_DIR = OUTPUT_ROOT / "qlib_bin"
REPORT_PATH = OUTPUT_ROOT / "qlib_fusion_report.json"
CONFIG_PATH = OUTPUT_ROOT / "qlib_okx_lgbm_config.yaml"
MANIFEST_PATH = OUTPUT_ROOT / "manifest.json"

SYMBOL_COLUMN = "symbol"
DATE_COLUMN = "date"
FREQ = os.getenv("QLIB_FREQ", "60min")
MODEL_FAMILY = os.getenv("QLIB_MODEL_FAMILY", "LightGBM")

FEATURE_COLUMNS = [
    "return_1",
    "return_3",
    "return_6",
    "return_24",
    "volatility_24",
    "atr_14_pct",
    "volume_ratio_24",
    "breakout_distance_pct",
    "rsi_14",
    "macd",
    "macd_hist",
    "market_return_6",
    "market_return_24",
    "return_6_excess",
    "return_24_excess",
    "cs_rank_return_6",
    "cs_rank_return_24",
    "cs_rank_volume_ratio_24",
    "cs_rank_rsi_14",
]
LABEL_COLUMNS = [
    "label_return_5_open_pct",
    "label_up_5",
    "label_return_5_atr",
    "label_triclass_5_atr",
    "label_return_12_open_pct",
    "label_up_12",
    "label_barrier_long_12",
    "rank_label_return_5",
    "rank_label_return_12",
]
PRICE_COLUMNS = ["open", "high", "low", "close", "volume"]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_symbol(pair: str) -> str:
    return pair.replace("/", "_").replace("-", "_").upper()


def scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "item"):
        return scalar(value.item())
    return value


def runtime_path(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(ROOT.resolve())
        return str(RUNTIME_ROOT / rel)
    except ValueError:
        return str(path)


def load_quality() -> dict[str, Any]:
    if not QUALITY_PATH.exists():
        return {"available": False}
    payload = json.loads(QUALITY_PATH.read_text(encoding="utf-8"))
    payload["available"] = True
    return payload


def qlib_timestamp(value: Any) -> str:
    return pd.Timestamp(value).tz_localize(None).strftime("%Y-%m-%d %H:%M:%S")


def split_segments(dates: pd.Series) -> dict[str, list[str]]:
    unique_dates = dates.drop_duplicates().sort_values().reset_index(drop=True)
    if len(unique_dates) < 30:
        raise ValueError("Qlib fusion needs at least 30 timestamps for train/valid/test segments.")
    train_end = unique_dates.iloc[int(len(unique_dates) * 0.70)]
    valid_end = unique_dates.iloc[int(len(unique_dates) * 0.85)]
    return {
        "train": [qlib_timestamp(unique_dates.iloc[0]), qlib_timestamp(train_end)],
        "valid": [qlib_timestamp(unique_dates[unique_dates > train_end].iloc[0]), qlib_timestamp(valid_end)],
        "test": [qlib_timestamp(unique_dates[unique_dates > valid_end].iloc[0]), qlib_timestamp(unique_dates.iloc[-1])],
    }


def write_qlib_config(segments: dict[str, list[str]], symbols: list[str]) -> None:
    feature_expr = ", ".join(f'"${column}"' for column in FEATURE_COLUMNS)
    feature_names = ", ".join(f'"{column.upper()}"' for column in FEATURE_COLUMNS)
    start_time = segments["train"][0]
    end_time = segments["test"][1]
    config = f"""qlib_init:
  provider_uri: "{runtime_path(QLIB_BIN_DIR)}"
  region: us
market: &market all
benchmark: &benchmark {symbols[0] if symbols else "BTC_USDT"}
data_handler_config: &data_handler_config
  start_time: "{start_time}"
  end_time: "{end_time}"
  instruments: *market
  data_loader:
    class: QlibDataLoader
    kwargs:
      config:
        feature:
          - [{feature_expr}]
          - [{feature_names}]
        label:
          - ["$label_return_5_open_pct"]
          - ["LABEL0"]
      freq: "{FREQ}"
  learn_processors:
    - class: DropnaLabel
    - class: CSRankNorm
      kwargs:
        fields_group: label
port_analysis_config: &port_analysis_config
  executor:
    class: SimulatorExecutor
    module_path: qlib.backtest.executor
    kwargs:
      time_per_step: "{FREQ}"
      generate_portfolio_metrics: true
  strategy:
    class: TopkDropoutStrategy
    module_path: qlib.contrib.strategy
    kwargs:
      signal: <PRED>
      topk: 3
      n_drop: 1
  backtest:
    start_time: "{segments["test"][0]}"
    end_time: "{segments["test"][1]}"
    account: 10000
    benchmark: null
    exchange_kwargs:
      freq: "{FREQ}"
      deal_price: close
      open_cost: 0.001
      close_cost: 0.001
      min_cost: 0
task:
  model:
    class: LGBModel
    module_path: qlib.contrib.model.gbdt
    kwargs:
      loss: mse
      learning_rate: 0.05
      max_depth: 8
      num_leaves: 64
      num_threads: 4
  dataset:
    class: DatasetH
    module_path: qlib.data.dataset
    kwargs:
      handler:
        class: DataHandlerLP
        module_path: qlib.data.dataset.handler
        kwargs: *data_handler_config
      segments:
        train: ["{segments["train"][0]}", "{segments["train"][1]}"]
        valid: ["{segments["valid"][0]}", "{segments["valid"][1]}"]
        test: ["{segments["test"][0]}", "{segments["test"][1]}"]
  record:
    - class: SignalRecord
      module_path: qlib.workflow.record_temp
      kwargs:
        model: <MODEL>
        dataset: <DATASET>
    - class: SigAnaRecord
      module_path: qlib.workflow.record_temp
      kwargs:
        ana_long_short: false
        ann_scaler: 8760
"""
    CONFIG_PATH.write_text(config, encoding="utf-8")


def build() -> dict[str, Any]:
    if not SOURCE_DATASET.exists():
        raise FileNotFoundError(f"Missing source dataset: {SOURCE_DATASET}. Run scripts/accumulate-market-data.sh first.")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    QLIB_BIN_DIR.mkdir(parents=True, exist_ok=True)
    for stale_csv in list(CSV_DIR.glob("*.csv")) + list(CSV_DIR.glob("._*.csv")):
        stale_csv.unlink(missing_ok=True)

    frame = pd.read_csv(SOURCE_DATASET)
    frame[DATE_COLUMN] = pd.to_datetime(frame[DATE_COLUMN], utc=True)
    required_columns = ["pair", DATE_COLUMN, *PRICE_COLUMNS, *FEATURE_COLUMNS, *LABEL_COLUMNS]
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Source dataset is missing columns: {missing}")
    frame = frame.replace([float("inf"), -float("inf")], pd.NA).dropna(subset=["pair", DATE_COLUMN, "close", "label_return_5_open_pct"])
    frame[SYMBOL_COLUMN] = frame["pair"].map(safe_symbol)
    export_columns = [DATE_COLUMN, SYMBOL_COLUMN, *PRICE_COLUMNS, *FEATURE_COLUMNS, *LABEL_COLUMNS]

    symbols: list[str] = []
    rows_by_symbol: dict[str, int] = {}
    for symbol, group in frame.groupby(SYMBOL_COLUMN):
        symbols.append(symbol)
        out = group.sort_values(DATE_COLUMN)[export_columns].copy()
        out[DATE_COLUMN] = out[DATE_COLUMN].dt.strftime("%Y-%m-%d %H:%M:%S")
        out.to_csv(CSV_DIR / f"{symbol.lower()}.csv", index=False)
        rows_by_symbol[symbol] = int(len(out))

    symbols = sorted(symbols)
    segments = split_segments(frame[DATE_COLUMN])
    write_qlib_config(segments, symbols)
    manifest = {
        "generated_at": now_utc(),
        "source_dataset": runtime_path(SOURCE_DATASET),
        "csv_dir": runtime_path(CSV_DIR),
        "qlib_bin_dir": runtime_path(QLIB_BIN_DIR),
        "config_path": runtime_path(CONFIG_PATH),
        "freq": FREQ,
        "symbols": symbols,
        "feature_columns": FEATURE_COLUMNS,
        "label_columns": LABEL_COLUMNS,
        "segments": segments,
        "dump_command": (
            "python3 vendor/qlib/scripts/dump_bin.py dump_all "
            f"--data_path {runtime_path(CSV_DIR)} --qlib_dir {runtime_path(QLIB_BIN_DIR)} --freq {FREQ} "
            "--date_field_name date --symbol_field_name symbol --file_suffix .csv --exclude_fields symbol"
        ),
        "qrun_command": f"qrun {runtime_path(CONFIG_PATH)}",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    quality = load_quality()
    report = {
        "generated_at": now_utc(),
        "ok": True,
        "integration": "qlib_research_layer_for_freqtrade_execution_runtime",
        "qlib_source_path": runtime_path(ROOT / "vendor" / "qlib"),
        "source_dataset": runtime_path(SOURCE_DATASET),
        "rows": int(len(frame)),
        "symbols": len(symbols),
        "rows_by_symbol": rows_by_symbol,
        "start": frame[DATE_COLUMN].min().isoformat(),
        "end": frame[DATE_COLUMN].max().isoformat(),
        "segments": segments,
        "model_family": MODEL_FAMILY,
        "qlib_ready_csv_dir": runtime_path(CSV_DIR),
        "qlib_bin_dir": runtime_path(QLIB_BIN_DIR),
        "qlib_config_path": runtime_path(CONFIG_PATH),
        "manifest_path": runtime_path(MANIFEST_PATH),
        "quality": {
            "available": quality.get("available"),
            "pairs_passed": quality.get("pairs_passed"),
            "pairs_rejected": quality.get("pairs_rejected"),
            "passed_pairs": quality.get("passed_pairs"),
            "rejected_pairs": quality.get("rejected_pairs"),
        },
        "safety": {
            "execution_engine": "Freqtrade remains the only trading engine.",
            "qlib_role": "research, factor/model/backtest workflow only.",
            "live_trade_gate": "Qlib predictions must pass existing deployment_gate before strategy integration.",
        },
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    report = build()
    print(json.dumps({k: report[k] for k in ["ok", "rows", "symbols", "start", "end", "qlib_ready_csv_dir", "qlib_config_path"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
