#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import math
import os
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import accuracy_score, mean_absolute_error, mean_squared_error, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(os.getenv("FT_PROJECT_ROOT", "/freqtrade"))
INPUT_PATH = ROOT / "output" / "ml_raw_3mo" / "features_labels_1h_clean.csv"
MODEL_DIR = ROOT / "output" / "ml_sequence_models"
REPORT_PATH = MODEL_DIR / "sequence_report.json"
PREDICTIONS_PATH = MODEL_DIR / "sequence_predictions_latest.csv"
MODEL_PATH = MODEL_DIR / "sequence_window_baseline.pkl"

LOOKBACK = int(os.getenv("ML_SEQUENCE_LOOKBACK_CANDLES", "24"))
TEST_FRACTION = float(os.getenv("ML_SEQUENCE_TEST_FRACTION", "0.20"))
PROBA_THRESHOLD = float(os.getenv("ML_SEQUENCE_PROBA_THRESHOLD", "0.55"))

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
TARGET_RETURN = "label_return_5_open_pct"
TARGET_UP = "label_up_5"
TARGET_RANK = "rank_label_return_5"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def scalar(value: Any) -> float | int | str | bool | None:
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        numeric = float(value)
        if math.isnan(numeric) or math.isinf(numeric):
            return None
        return numeric
    return value


def dependency_status() -> dict[str, Any]:
    return {
        "torch": importlib.util.find_spec("torch") is not None,
        "tensorflow": importlib.util.find_spec("tensorflow") is not None,
        "keras": importlib.util.find_spec("keras") is not None,
    }


def load_dataset() -> pd.DataFrame:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Missing clean ML dataset: {INPUT_PATH}. Run scripts/build-ml-dataset.py first.")
    frame = pd.read_csv(INPUT_PATH)
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    required = ["date", "pair", TARGET_RETURN, TARGET_UP, TARGET_RANK, *FEATURE_COLUMNS]
    frame = frame.dropna(subset=required).sort_values(["pair", "date"]).reset_index(drop=True)
    if frame.empty:
        raise ValueError("Clean ML dataset has no usable rows for sequence training.")
    return frame


def build_sequence_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    rows: list[dict[str, Any]] = []
    feature_names = [f"{column}_lag_{lag}" for lag in range(LOOKBACK, 0, -1) for column in FEATURE_COLUMNS]
    for pair, group in frame.groupby("pair", sort=True):
        group = group.sort_values("date").reset_index(drop=True)
        values = group[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=float)
        for index in range(LOOKBACK - 1, len(group)):
            window = values[index - LOOKBACK + 1 : index + 1]
            row = {
                "date": group.loc[index, "date"],
                "pair": pair,
                "close": group.loc[index, "close"] if "close" in group else None,
                TARGET_RETURN: group.loc[index, TARGET_RETURN],
                TARGET_UP: int(group.loc[index, TARGET_UP]),
                TARGET_RANK: group.loc[index, TARGET_RANK],
            }
            row.update(dict(zip(feature_names, window.reshape(-1))))
            rows.append(row)
    sequence_frame = pd.DataFrame(rows).sort_values(["date", "pair"]).reset_index(drop=True)
    if sequence_frame.empty:
        raise ValueError(f"Not enough rows to build {LOOKBACK}-candle sequences.")
    return sequence_frame, feature_names


def split_by_time(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    unique_dates = frame["date"].drop_duplicates().sort_values()
    if len(unique_dates) < 20:
        raise ValueError("Sequence dataset does not have enough timestamps for a time split.")
    split_index = max(1, min(len(unique_dates) - 1, int(len(unique_dates) * (1 - TEST_FRACTION))))
    split_date = unique_dates.iloc[split_index]
    train = frame[frame["date"] < split_date].copy()
    test = frame[frame["date"] >= split_date].copy()
    if train.empty or test.empty:
        raise ValueError("Sequence time split produced empty train or test set.")
    return train, test


def regression_metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, Any]:
    corr = pd.Series(y_pred).corr(pd.Series(y_true).reset_index(drop=True))
    return {
        "mae": scalar(mean_absolute_error(y_true, y_pred)),
        "rmse": scalar(math.sqrt(mean_squared_error(y_true, y_pred))),
        "corr": scalar(corr),
        "pred_mean": scalar(np.mean(y_pred)),
    }


def classification_metrics(y_true: pd.Series, proba: np.ndarray) -> dict[str, Any]:
    pred = (proba >= PROBA_THRESHOLD).astype(int)
    return {
        "threshold": PROBA_THRESHOLD,
        "accuracy": scalar(accuracy_score(y_true, pred)),
        "precision": scalar(precision_score(y_true, pred, zero_division=0)),
        "recall": scalar(recall_score(y_true, pred, zero_division=0)),
        "positive_rate": scalar(np.mean(pred)),
        "mean_probability": scalar(np.mean(proba)),
    }


def ranking_metrics(test: pd.DataFrame, scores: np.ndarray) -> dict[str, Any]:
    scored = test[["date", TARGET_RANK, TARGET_RETURN]].copy()
    scored["score"] = scores
    corrs: list[float] = []
    top_returns: list[float] = []
    bottom_returns: list[float] = []
    for _, group in scored.groupby("date"):
        if len(group) < 3:
            continue
        corr = group["score"].corr(group[TARGET_RANK], method="spearman")
        if not math.isnan(corr):
            corrs.append(float(corr))
        top_returns.append(float(group.sort_values("score", ascending=False).head(3)[TARGET_RETURN].mean()))
        bottom_returns.append(float(group.sort_values("score", ascending=True).head(3)[TARGET_RETURN].mean()))
    return {
        "spearman_mean_by_timestamp": scalar(np.mean(corrs) if corrs else None),
        "top3_forward_return_mean_pct": scalar(np.mean(top_returns) if top_returns else None),
        "bottom3_forward_return_mean_pct": scalar(np.mean(bottom_returns) if bottom_returns else None),
        "timestamps_evaluated": len(corrs),
    }


def train() -> dict[str, Any]:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    raw = load_dataset()
    sequence_frame, feature_names = build_sequence_frame(raw)
    train_frame, test_frame = split_by_time(sequence_frame)
    x_train = train_frame[feature_names]
    x_test = test_frame[feature_names]

    regressor = Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", HistGradientBoostingRegressor(max_iter=140, learning_rate=0.045, l2_regularization=0.03, random_state=42)),
        ]
    )
    classifier = Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", HistGradientBoostingClassifier(max_iter=140, learning_rate=0.045, l2_regularization=0.03, random_state=42)),
        ]
    )
    ranker = Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", HistGradientBoostingRegressor(max_iter=140, learning_rate=0.045, l2_regularization=0.03, random_state=42)),
        ]
    )
    regressor.fit(x_train, train_frame[TARGET_RETURN])
    classifier.fit(x_train, train_frame[TARGET_UP].astype(int))
    ranker.fit(x_train, train_frame[TARGET_RANK])

    pred_return = regressor.predict(x_test)
    pred_up = classifier.predict_proba(x_test)[:, 1]
    pred_rank = ranker.predict(x_test)

    latest_date = sequence_frame["date"].max()
    latest = sequence_frame[sequence_frame["date"] == latest_date].copy()
    latest_x = latest[feature_names]
    latest["seq_pred_return_5_open_pct"] = regressor.predict(latest_x)
    latest["seq_pred_up_probability"] = classifier.predict_proba(latest_x)[:, 1]
    latest["seq_pred_rank_score"] = ranker.predict(latest_x)
    latest["seq_rank_position"] = latest["seq_pred_rank_score"].rank(ascending=False, method="first").astype(int)
    latest["seq_pred_signal"] = np.where(latest["seq_pred_return_5_open_pct"] > 0, "bullish", "bearish")
    latest = latest.sort_values(["seq_rank_position", "pair"])
    prediction_columns = [
        "date",
        "pair",
        "close",
        "seq_pred_return_5_open_pct",
        "seq_pred_up_probability",
        "seq_pred_rank_score",
        "seq_rank_position",
        "seq_pred_signal",
    ]
    latest[prediction_columns].to_csv(PREDICTIONS_PATH, index=False)

    deps = dependency_status()
    report = {
        "generated_at": now_utc(),
        "ok": True,
        "model_family": "sequence_window_gradient_boosting_baseline",
        "lookback_candles": LOOKBACK,
        "target": TARGET_RETURN,
        "input_path": str(INPUT_PATH),
        "dataset": {
            "raw_rows": int(len(raw)),
            "sequence_rows": int(len(sequence_frame)),
            "pairs": int(sequence_frame["pair"].nunique()),
            "start": sequence_frame["date"].min().isoformat(),
            "end": sequence_frame["date"].max().isoformat(),
            "train_rows": int(len(train_frame)),
            "test_rows": int(len(test_frame)),
            "features_per_step": len(FEATURE_COLUMNS),
            "flattened_features": len(feature_names),
        },
        "tasks": {
            "sequence_regression": regression_metrics(test_frame[TARGET_RETURN], pred_return),
            "sequence_binary_classification": classification_metrics(test_frame[TARGET_UP].astype(int), pred_up),
            "sequence_cross_sectional_ranking": ranking_metrics(test_frame, pred_rank),
        },
        "deep_learning_models": {
            "lstm": {
                "status": "skipped_missing_torch" if not deps["torch"] else "ready_for_torch_training",
                "required_dependency": "torch",
                "intended_use": "short-term sequence memory over recent candles",
            },
            "transformer": {
                "status": "skipped_missing_torch" if not deps["torch"] else "ready_for_torch_training",
                "required_dependency": "torch",
                "intended_use": "attention over longer feature windows",
            },
        },
        "dependency_status": deps,
        "signal_contract": {
            "seq_pred_return_5_open_pct": "positive means bullish for 5-candle open-to-open label",
            "seq_pred_up_probability": "binary probability; threshold controls timing",
            "seq_pred_rank_score": "higher means better cross-sectional long candidate",
            "seq_rank_position": "1 is strongest sequence candidate at the latest timestamp",
        },
        "latest_timestamp": latest_date.isoformat(),
        "top_sequence_candidates": json.loads(latest[prediction_columns].head(10).to_json(orient="records", date_format="iso")),
        "bottom_sequence_candidates": json.loads(latest[prediction_columns].tail(10).to_json(orient="records", date_format="iso")),
        "artifacts": {
            "model_path": str(MODEL_PATH),
            "sequence_report": str(REPORT_PATH),
            "sequence_predictions_latest": str(PREDICTIONS_PATH),
        },
    }
    with MODEL_PATH.open("wb") as handle:
        pickle.dump(
            {
                "feature_columns": feature_names,
                "regressor": regressor,
                "classifier": classifier,
                "ranker": ranker,
                "report": report,
            },
            handle,
        )
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    report = train()
    print(json.dumps({"ok": report["ok"], "model_family": report["model_family"], "artifacts": report["artifacts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
