#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(os.getenv("FT_PROJECT_ROOT", "/freqtrade"))
USER_DATA = ROOT / "user_data"
DATA_DIR = USER_DATA / "data" / "okx"
OUTPUT_DIR = ROOT / "output" / "ml_raw_3mo"
EVIDENCE_PATH = OUTPUT_DIR / "gemini_evidence_pack.json"
SUMMARY_PATH = OUTPUT_DIR / "dataset_summary.json"
DATASET_PATH = OUTPUT_DIR / "features_labels_1h.csv"
CLEAN_DATASET_PATH = OUTPUT_DIR / "features_labels_1h_clean.csv"
QUALITY_PATH = OUTPUT_DIR / "data_quality_report.json"

HORIZON_CANDLES = int(os.getenv("ML_LABEL_HORIZON_CANDLES", "5"))
LONG_HORIZON_CANDLES = int(os.getenv("ML_LONG_LABEL_HORIZON_CANDLES", "12"))
BARRIER_HORIZON_CANDLES = int(os.getenv("ML_BARRIER_HORIZON_CANDLES", "12"))
BARRIER_TAKE_PROFIT_PCT = float(os.getenv("ML_BARRIER_TAKE_PROFIT_PCT", "3.0"))
BARRIER_STOP_LOSS_PCT = float(os.getenv("ML_BARRIER_STOP_LOSS_PCT", "2.0"))
TRICLASS_UP_ATR = float(os.getenv("ML_TRICLASS_UP_ATR", "0.6"))
TRICLASS_DOWN_ATR = float(os.getenv("ML_TRICLASS_DOWN_ATR", "-0.6"))
MIN_ATR_PCT_FOR_LABEL = float(os.getenv("ML_MIN_ATR_PCT_FOR_LABEL", "0.01"))
LOOKBACK_DAYS = int(os.getenv("ML_LOOKBACK_DAYS", "90"))
TIMEFRAME = os.getenv("ML_DATASET_TIMEFRAME", "1h")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_float(value: Any) -> float | None:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def quantiles(series: pd.Series) -> dict[str, float | None]:
    clean = finite_series(series)
    if clean.empty:
        return {"p05": None, "p25": None, "p50": None, "p75": None, "p95": None}
    return {
        "p05": as_float(clean.quantile(0.05)),
        "p25": as_float(clean.quantile(0.25)),
        "p50": as_float(clean.quantile(0.50)),
        "p75": as_float(clean.quantile(0.75)),
        "p95": as_float(clean.quantile(0.95)),
    }


def finite_series(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric[numeric.notna() & numeric.map(math.isfinite)]


def pair_from_file(path: Path) -> str:
    stem = path.stem
    suffix = f"-{TIMEFRAME}"
    if stem.endswith(suffix):
        stem = stem[: -len(suffix)]
    return stem.replace("_", "/")


def load_ohlcv(path: Path) -> pd.DataFrame:
    if path.suffix == ".feather":
        frame = pd.read_feather(path)
    elif path.suffix == ".parquet":
        frame = pd.read_parquet(path)
    elif path.suffix == ".json":
        frame = pd.read_json(path)
    elif path.suffix == ".gz" and path.name.endswith(".json.gz"):
        frame = pd.read_json(path, compression="gzip")
    else:
        raise ValueError(f"Unsupported data file: {path}")

    rename = {}
    for candidate in ("date", "timestamp"):
        if candidate in frame.columns:
            rename[candidate] = "date"
            break
    frame = frame.rename(columns=rename)
    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")
    frame = frame[required].copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date")


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    previous_close = df["close"].shift(1)
    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - previous_close).abs(),
            (df["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def add_features(frame: pd.DataFrame, pair: str) -> pd.DataFrame:
    df = frame.copy()
    df["pair"] = pair
    df["return_1"] = df["close"].pct_change()
    df["return_3"] = df["close"].pct_change(3)
    df["return_6"] = df["close"].pct_change(6)
    df["return_24"] = df["close"].pct_change(24)
    df["volatility_24"] = df["return_1"].rolling(24).std()
    df["atr_14"] = atr(df, 14)
    df["atr_14_pct"] = (df["atr_14"] / df["close"]) * 100
    df["volume_mean_24"] = df["volume"].rolling(24).mean().shift(1)
    df["volume_ratio_24"] = df["volume"] / df["volume_mean_24"].replace(0, pd.NA)
    df["breakout_high_24"] = df["high"].rolling(24).max().shift(1)
    df["breakout_distance_pct"] = (df["close"] / df["breakout_high_24"] - 1) * 100
    df["rsi_14"] = rsi(df["close"], 14)
    ema_12 = df["close"].ewm(span=12, adjust=False).mean()
    ema_26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema_12 - ema_26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    df["future_entry_open"] = df["open"].shift(-1)
    df["future_exit_open_5"] = df["open"].shift(-(HORIZON_CANDLES + 1))
    df["label_return_5_open_pct"] = (df["future_exit_open_5"] / df["future_entry_open"] - 1) * 100
    df["label_up_5"] = (df["label_return_5_open_pct"] > 0).astype("Int64")
    usable_atr_pct = df["atr_14_pct"].where(df["atr_14_pct"].abs() >= MIN_ATR_PCT_FOR_LABEL)
    df["label_return_5_atr"] = df["label_return_5_open_pct"] / usable_atr_pct
    df["label_triclass_5_atr"] = triclass_label(df["label_return_5_atr"])
    df["future_exit_open_12"] = df["open"].shift(-(LONG_HORIZON_CANDLES + 1))
    df["label_return_12_open_pct"] = (df["future_exit_open_12"] / df["future_entry_open"] - 1) * 100
    df["label_up_12"] = (df["label_return_12_open_pct"] > 0).astype("Int64")
    df["label_barrier_long_12"] = barrier_label(df)
    return df


def triclass_label(series: pd.Series) -> pd.Series:
    values: list[int | None] = []
    for value in series:
        if pd.isna(value):
            values.append(None)
        elif value >= TRICLASS_UP_ATR:
            values.append(1)
        elif value <= TRICLASS_DOWN_ATR:
            values.append(-1)
        else:
            values.append(0)
    return pd.Series(values, index=series.index, dtype="Int64")


def barrier_label(df: pd.DataFrame) -> pd.Series:
    values: list[int | None] = []
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    entry = df["future_entry_open"].to_numpy()
    take_multiplier = 1 + (BARRIER_TAKE_PROFIT_PCT / 100)
    stop_multiplier = 1 - (BARRIER_STOP_LOSS_PCT / 100)
    for index, entry_price in enumerate(entry):
        if pd.isna(entry_price) or entry_price <= 0:
            values.append(None)
            continue
        take_price = entry_price * take_multiplier
        stop_price = entry_price * stop_multiplier
        outcome: int | None = 0
        for future_index in range(index + 1, min(index + 1 + BARRIER_HORIZON_CANDLES, len(df))):
            hit_stop = lows[future_index] <= stop_price
            hit_take = highs[future_index] >= take_price
            if hit_stop and hit_take:
                outcome = 0
                break
            if hit_take:
                outcome = 1
                break
            if hit_stop:
                outcome = 0
                break
        if index + BARRIER_HORIZON_CANDLES >= len(df):
            outcome = None
        values.append(outcome)
    return pd.Series(values, index=df.index, dtype="Int64")


def correlation_summary(dataset: pd.DataFrame) -> list[dict[str, Any]]:
    feature_columns = [
        "return_1",
        "return_3",
        "return_6",
        "return_24",
        "volatility_24",
        "atr_14",
        "atr_14_pct",
        "volume_ratio_24",
        "breakout_distance_pct",
        "rsi_14",
        "macd",
        "macd_hist",
    ]
    rows: list[dict[str, Any]] = []
    target = dataset["label_return_5_open_pct"]
    for column in feature_columns:
        if column not in dataset:
            continue
        corr = dataset[column].corr(target)
        rows.append({"factor": column, "corr_to_label": as_float(corr)})
    return sorted(rows, key=lambda item: abs(item["corr_to_label"] or 0), reverse=True)


def quality_report(dataset: pd.DataFrame) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for pair, group in dataset.groupby("pair"):
        label = group["label_return_5_open_pct"]
        row = {
            "pair": pair,
            "rows": int(len(group)),
            "zero_volume_rate": as_float((group["volume"] <= 0).mean()),
            "volume_ratio_24_median": as_float(group["volume_ratio_24"].replace([float("inf"), -float("inf")], pd.NA).median()),
            "nonzero_label_rate": as_float((label.abs() > 1e-12).mean()),
            "label_up_5_rate": as_float(group["label_up_5"].mean()),
        }
        row["passed"] = bool(
            row["rows"] >= 1000
            and (row["zero_volume_rate"] or 1.0) <= 0.20
            and (row["volume_ratio_24_median"] or 0.0) >= 0.01
            and (row["nonzero_label_rate"] or 0.0) >= 0.20
        )
        reasons = []
        if row["rows"] < 1000:
            reasons.append("too_few_rows")
        if (row["zero_volume_rate"] or 1.0) > 0.20:
            reasons.append("too_many_zero_volume_candles")
        if (row["volume_ratio_24_median"] or 0.0) < 0.01:
            reasons.append("low_volume_ratio_median")
        if (row["nonzero_label_rate"] or 0.0) < 0.20:
            reasons.append("too_many_flat_future_returns")
        row["failed_reasons"] = reasons
        rows.append(row)
    passed_pairs = sorted(row["pair"] for row in rows if row["passed"])
    rejected_pairs = sorted(row["pair"] for row in rows if not row["passed"])
    return {
        "rules": {
            "min_rows": 1000,
            "max_zero_volume_rate": 0.20,
            "min_volume_ratio_24_median": 0.01,
            "min_nonzero_label_rate": 0.20,
            "row_filter": "volume > 0 and volume_mean_24 > 0",
        },
        "pairs_total": len(rows),
        "pairs_passed": len(passed_pairs),
        "pairs_rejected": len(rejected_pairs),
        "passed_pairs": passed_pairs,
        "rejected_pairs": rejected_pairs,
        "pair_quality": sorted(rows, key=lambda item: (not item["passed"], item["pair"])),
    }


def clean_dataset(dataset: pd.DataFrame, quality: dict[str, Any]) -> pd.DataFrame:
    passed_pairs = set(quality["passed_pairs"])
    cleaned = dataset[
        dataset["pair"].isin(passed_pairs)
        & (dataset["volume"] > 0)
        & (dataset["volume_mean_24"] > 0)
    ].copy()
    cleaned["rank_label_return_5"] = cleaned.groupby("date")["label_return_5_open_pct"].rank(pct=True, ascending=True)
    return cleaned.dropna(subset=["rank_label_return_5"])


def add_cross_sectional_features(dataset: pd.DataFrame) -> pd.DataFrame:
    df = dataset.copy()
    grouped = df.groupby("date")
    df["market_return_6"] = grouped["return_6"].transform("mean")
    df["market_return_24"] = grouped["return_24"].transform("mean")
    df["return_6_excess"] = df["return_6"] - df["market_return_6"]
    df["return_24_excess"] = df["return_24"] - df["market_return_24"]
    df["cs_rank_return_6"] = grouped["return_6"].rank(pct=True)
    df["cs_rank_return_24"] = grouped["return_24"].rank(pct=True)
    df["cs_rank_volume_ratio_24"] = grouped["volume_ratio_24"].rank(pct=True)
    df["cs_rank_rsi_14"] = grouped["rsi_14"].rank(pct=True)
    return df


def build() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = utc_now() - timedelta(days=LOOKBACK_DAYS)
    pattern = f"*-{TIMEFRAME}.*"
    files = sorted(path for path in DATA_DIR.glob(pattern) if not path.name.startswith("._"))
    frames = []
    skipped: list[dict[str, str]] = []
    for path in files:
        try:
            pair = pair_from_file(path)
            frame = load_ohlcv(path)
            frame = frame[frame["date"] >= cutoff]
            if len(frame) < 120:
                skipped.append({"file": str(path), "reason": f"too_few_rows:{len(frame)}"})
                continue
            frames.append(add_features(frame, pair))
        except Exception as exc:  # noqa: BLE001 - report per-file failure.
            skipped.append({"file": str(path), "reason": f"{type(exc).__name__}: {exc}"[:300]})

    if not frames:
        summary = {
            "generated_at": utc_now().isoformat(),
            "ok": False,
            "error": f"No usable {TIMEFRAME} OHLCV files under {DATA_DIR}",
            "skipped": skipped,
        }
        SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        EVIDENCE_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return summary

    dataset = pd.concat(frames, ignore_index=True)
    dataset = dataset.sort_values(["date", "pair"])
    dataset["rank_label_return_5"] = dataset.groupby("date")["label_return_5_open_pct"].rank(pct=True, ascending=True)
    dataset["rank_label_return_12"] = dataset.groupby("date")["label_return_12_open_pct"].rank(pct=True, ascending=True)
    dataset = dataset.dropna(subset=["label_return_5_open_pct", "future_entry_open", "future_exit_open_5"])
    dataset = add_cross_sectional_features(dataset)

    pair_stats = []
    for pair, group in dataset.groupby("pair"):
        pair_stats.append(
            {
                "pair": pair,
                "rows": int(len(group)),
                "start": group["date"].min().isoformat(),
                "end": group["date"].max().isoformat(),
                "label_return_5_open_pct_mean": as_float(group["label_return_5_open_pct"].mean()),
                "label_return_5_open_pct_quantiles": quantiles(group["label_return_5_open_pct"]),
                "label_up_5_rate": as_float(group["label_up_5"].mean()),
                "volume_ratio_24_median": as_float(group["volume_ratio_24"].median()),
            }
        )
    pair_stats = sorted(pair_stats, key=lambda item: item["rows"], reverse=True)

    compact_columns = [
        "date",
        "pair",
        "open",
        "high",
        "low",
        "close",
        "volume",
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
        "future_entry_open",
        "future_exit_open_5",
        "label_return_5_open_pct",
        "label_up_5",
        "label_return_5_atr",
        "label_triclass_5_atr",
        "future_exit_open_12",
        "label_return_12_open_pct",
        "label_up_12",
        "label_barrier_long_12",
        "rank_label_return_5",
        "rank_label_return_12",
    ]
    dataset[compact_columns].to_csv(DATASET_PATH, index=False)
    quality = quality_report(dataset)
    clean = clean_dataset(dataset, quality)
    clean[compact_columns].to_csv(CLEAN_DATASET_PATH, index=False)
    QUALITY_PATH.write_text(
        json.dumps({**quality, "clean_rows": int(len(clean)), "clean_pairs": int(clean["pair"].nunique())}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    evidence = {
        "generated_at": utc_now().isoformat(),
        "ok": True,
        "source": "freqtrade_downloaded_ohlcv",
        "exchange": "okx",
        "timeframe": TIMEFRAME,
        "lookback_days": LOOKBACK_DAYS,
        "label_definition": {
            "name": "label_return_5_open_pct",
            "formula": "future_exit_open_5 / future_entry_open - 1",
            "entry_price": "next candle open, open.shift(-1)",
            "exit_price": f"open after {HORIZON_CANDLES} candles, open.shift(-{HORIZON_CANDLES + 1})",
            "reason": "uses next tradable open instead of current/previous close",
        },
        "alternative_label_definitions": {
            "label_return_12_open_pct": {
                "formula": "future_exit_open_12 / future_entry_open - 1",
                "entry_price": "next candle open, open.shift(-1)",
                "exit_price": f"open after {LONG_HORIZON_CANDLES} candles, open.shift(-{LONG_HORIZON_CANDLES + 1})",
                "reason": "longer prediction window to reduce 1h noise",
            },
            "label_barrier_long_12": {
                "formula": f"1 if +{BARRIER_TAKE_PROFIT_PCT}% take-profit is touched before -{BARRIER_STOP_LOSS_PCT}% stop-loss within {BARRIER_HORIZON_CANDLES} candles else 0",
                "entry_price": "next candle open, open.shift(-1)",
                "reason": "event label closer to live trade outcome than raw return",
            },
        },
        "task_views": {
            "regression": "predict label_return_5_open_pct",
            "binary_classification": "predict label_up_5",
            "cross_sectional_ranking": "rank_label_return_5 by timestamp across pairs",
            "long_horizon_regression": "predict label_return_12_open_pct",
            "barrier_classification": "predict label_barrier_long_12",
            "atr_normalized_regression": "predict label_return_5_atr",
            "triclass_classification": "predict label_triclass_5_atr where -1=down, 0=no-trade/chop, 1=up",
        },
        "rows": int(len(dataset)),
        "pairs": int(dataset["pair"].nunique()),
        "clean_rows": int(len(clean)),
        "clean_pairs": int(clean["pair"].nunique()),
        "start": dataset["date"].min().isoformat(),
        "end": dataset["date"].max().isoformat(),
        "label_return_5_open_pct": {
            "mean": as_float(dataset["label_return_5_open_pct"].mean()),
            "std": as_float(dataset["label_return_5_open_pct"].std()),
            "quantiles": quantiles(dataset["label_return_5_open_pct"]),
            "up_rate": as_float(dataset["label_up_5"].mean()),
        },
        "label_return_12_open_pct": {
            "mean": as_float(dataset["label_return_12_open_pct"].mean()),
            "std": as_float(dataset["label_return_12_open_pct"].std()),
            "quantiles": quantiles(dataset["label_return_12_open_pct"]),
            "up_rate": as_float(dataset["label_up_12"].mean()),
        },
        "label_barrier_long_12": {
            "positive_rate": as_float(dataset["label_barrier_long_12"].mean()),
            "take_profit_pct": BARRIER_TAKE_PROFIT_PCT,
            "stop_loss_pct": BARRIER_STOP_LOSS_PCT,
            "horizon_candles": BARRIER_HORIZON_CANDLES,
        },
        "label_return_5_atr": {
            "mean": as_float(finite_series(dataset["label_return_5_atr"]).mean()),
            "std": as_float(finite_series(dataset["label_return_5_atr"]).std()),
            "quantiles": quantiles(dataset["label_return_5_atr"]),
            "description": "5-candle open-to-open return divided by ATR percentage",
            "min_atr_pct_for_label": MIN_ATR_PCT_FOR_LABEL,
        },
        "label_triclass_5_atr": {
            "class_distribution": {str(key): int(value) for key, value in dataset["label_triclass_5_atr"].value_counts(dropna=True).sort_index().items()},
            "down_threshold_atr": TRICLASS_DOWN_ATR,
            "up_threshold_atr": TRICLASS_UP_ATR,
            "description": "-1=down, 0=no-trade/chop, 1=up",
        },
        "factor_correlations": correlation_summary(dataset),
        "clean_factor_correlations": correlation_summary(clean) if not clean.empty else [],
        "data_quality": quality,
        "pair_stats": pair_stats[:80],
        "sample_rows": json.loads(dataset[compact_columns].tail(60).to_json(orient="records", date_format="iso")),
        "skipped_files": skipped,
        "dataset_path": str(DATASET_PATH),
        "clean_dataset_path": str(CLEAN_DATASET_PATH),
        "data_quality_path": str(QUALITY_PATH),
    }
    SUMMARY_PATH.write_text(json.dumps({k: v for k, v in evidence.items() if k != "sample_rows"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    EVIDENCE_PATH.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return evidence


def main() -> int:
    result = build()
    print(json.dumps({k: result.get(k) for k in ("ok", "rows", "pairs", "clean_rows", "clean_pairs", "start", "end", "dataset_path", "clean_dataset_path", "error")}, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
