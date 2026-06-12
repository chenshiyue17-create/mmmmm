#!/usr/bin/env python3
from __future__ import annotations

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
from sklearn.metrics import accuracy_score, balanced_accuracy_score, mean_absolute_error, mean_squared_error, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(os.getenv("FT_PROJECT_ROOT", "/freqtrade"))
INPUT_PATH = ROOT / "output" / "ml_raw_3mo" / "features_labels_1h.csv"
CLEAN_INPUT_PATH = ROOT / "output" / "ml_raw_3mo" / "features_labels_1h_clean.csv"
QUALITY_PATH = ROOT / "output" / "ml_raw_3mo" / "data_quality_report.json"
MODEL_DIR = ROOT / "output" / "ml_models"
REPORT_PATH = MODEL_DIR / "training_report.json"
PREDICTIONS_PATH = MODEL_DIR / "predictions_latest.csv"
SIGNALS_PATH = MODEL_DIR / "latest_signals.json"
MODEL_PATH = MODEL_DIR / "sklearn_hist_gradient_models.pkl"

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
TARGET_RETURN_12 = "label_return_12_open_pct"
TARGET_UP_12 = "label_up_12"
TARGET_BARRIER = "label_barrier_long_12"
TARGET_RETURN_ATR = "label_return_5_atr"
TARGET_TRICLASS = "label_triclass_5_atr"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def scalar(value: Any) -> float | int | str | None:
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    return value


def load_dataset() -> pd.DataFrame:
    path = CLEAN_INPUT_PATH if CLEAN_INPUT_PATH.exists() else INPUT_PATH
    if not path.exists():
        raise FileNotFoundError(f"Missing dataset: {path}. Run scripts/accumulate-market-data.sh first.")
    frame = pd.read_csv(path)
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    frame = frame.dropna(subset=FEATURE_COLUMNS + [TARGET_RETURN, TARGET_UP, TARGET_RANK, "pair"])
    frame = frame.sort_values(["date", "pair"]).reset_index(drop=True)
    return frame


def load_quality() -> dict[str, Any]:
    if not QUALITY_PATH.exists():
        return {"available": False, "path": str(QUALITY_PATH)}
    payload = json.loads(QUALITY_PATH.read_text(encoding="utf-8"))
    payload["available"] = True
    return payload


def feature_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    base = frame[FEATURE_COLUMNS].copy()
    pair_dummies = pd.get_dummies(frame["pair"], prefix="pair", dtype=float)
    return pd.concat([base, pair_dummies], axis=1).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def split_by_time(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    unique_dates = frame["date"].drop_duplicates().sort_values()
    if len(unique_dates) < 20:
        raise ValueError("Dataset does not have enough timestamps for a time split.")
    split_index = max(1, int(len(unique_dates) * 0.8))
    split_date = unique_dates.iloc[split_index]
    train = frame[frame["date"] < split_date].copy()
    test = frame[frame["date"] >= split_date].copy()
    if train.empty or test.empty:
        raise ValueError("Time split produced empty train or test set.")
    return train, test


def regression_metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, Any]:
    corr = pd.Series(y_pred).corr(pd.Series(y_true).reset_index(drop=True))
    return {
        "mae": scalar(mean_absolute_error(y_true, y_pred)),
        "rmse": scalar(math.sqrt(mean_squared_error(y_true, y_pred))),
        "corr": scalar(corr),
        "pred_mean": scalar(np.mean(y_pred)),
    }


def classification_metrics(y_true: pd.Series, proba: np.ndarray, threshold: float = 0.55) -> dict[str, Any]:
    pred = (proba >= threshold).astype(int)
    return {
        "threshold": threshold,
        "accuracy": scalar(accuracy_score(y_true, pred)),
        "precision": scalar(precision_score(y_true, pred, zero_division=0)),
        "recall": scalar(recall_score(y_true, pred, zero_division=0)),
        "positive_rate": scalar(np.mean(pred)),
        "mean_probability": scalar(np.mean(proba)),
    }


def ranking_metrics(test: pd.DataFrame, scores: np.ndarray) -> dict[str, Any]:
    scored = test[["date", TARGET_RANK, TARGET_RETURN]].copy()
    scored["score"] = scores
    corrs = []
    top_rows = []
    for _, group in scored.groupby("date"):
        if len(group) < 3:
            continue
        corr = group["score"].corr(group[TARGET_RANK], method="spearman")
        if not math.isnan(corr):
            corrs.append(corr)
        top = group.sort_values("score", ascending=False).head(3)
        top_rows.append(float(top[TARGET_RETURN].mean()))
    return {
        "spearman_mean_by_timestamp": scalar(np.mean(corrs) if corrs else None),
        "top3_forward_return_mean_pct": scalar(np.mean(top_rows) if top_rows else None),
        "timestamps_evaluated": len(corrs),
    }


def deployment_gate(tasks: dict[str, Any]) -> dict[str, Any]:
    regression_corr = tasks["regression"].get("corr") or 0.0
    classification_precision = tasks["binary_classification"].get("precision") or 0.0
    ranking_spearman = tasks["cross_sectional_ranking"].get("spearman_mean_by_timestamp") or 0.0
    checks = {
        "regression_corr_at_least_0_10": regression_corr >= 0.10,
        "classification_precision_at_least_0_55": classification_precision >= 0.55,
        "ranking_spearman_at_least_0_05": ranking_spearman >= 0.05,
    }
    passed = all(checks.values())
    reasons = [name for name, ok in checks.items() if not ok]
    return {
        "passed": passed,
        "mode": "candidate_for_strategy_filter" if passed else "research_only_do_not_trade",
        "checks": checks,
        "failed_checks": reasons,
        "rule": "pred signals may influence strategy only when every gate check passes on out-of-sample data",
    }


def train_regression_task(train_frame: pd.DataFrame, test_frame: pd.DataFrame, target: str) -> dict[str, Any]:
    scoped_train = train_frame.dropna(subset=[target])
    scoped_test = test_frame.dropna(subset=[target])
    if scoped_train.empty or scoped_test.empty:
        return {"ok": False, "error": "empty_train_or_test"}
    x_train = feature_matrix(scoped_train)
    x_test = feature_matrix(scoped_test).reindex(columns=x_train.columns, fill_value=0.0)
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", HistGradientBoostingRegressor(max_iter=180, learning_rate=0.055, l2_regularization=0.02, random_state=42)),
        ]
    )
    model.fit(x_train, scoped_train[target])
    pred = model.predict(x_test)
    return {"ok": True, "rows": int(len(scoped_train) + len(scoped_test)), **regression_metrics(scoped_test[target], pred)}


def train_classification_task(train_frame: pd.DataFrame, test_frame: pd.DataFrame, target: str, threshold: float = 0.55) -> dict[str, Any]:
    scoped_train = train_frame.dropna(subset=[target])
    scoped_test = test_frame.dropna(subset=[target])
    if scoped_train.empty or scoped_test.empty or scoped_train[target].nunique() < 2:
        return {"ok": False, "error": "empty_or_single_class_train"}
    x_train = feature_matrix(scoped_train)
    x_test = feature_matrix(scoped_test).reindex(columns=x_train.columns, fill_value=0.0)
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", HistGradientBoostingClassifier(max_iter=180, learning_rate=0.055, l2_regularization=0.02, random_state=42)),
        ]
    )
    model.fit(x_train, scoped_train[target].astype(int))
    proba = model.predict_proba(x_test)[:, 1]
    return {
        "ok": True,
        "rows": int(len(scoped_train) + len(scoped_test)),
        "positive_rate": scalar(scoped_train[target].mean()),
        **classification_metrics(scoped_test[target].astype(int), proba, threshold=threshold),
    }


def train_multiclass_task(train_frame: pd.DataFrame, test_frame: pd.DataFrame, target: str) -> dict[str, Any]:
    scoped_train = train_frame.dropna(subset=[target])
    scoped_test = test_frame.dropna(subset=[target])
    if scoped_train.empty or scoped_test.empty or scoped_train[target].nunique() < 3:
        return {"ok": False, "error": "empty_or_missing_classes"}
    x_train = feature_matrix(scoped_train)
    x_test = feature_matrix(scoped_test).reindex(columns=x_train.columns, fill_value=0.0)
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", HistGradientBoostingClassifier(max_iter=180, learning_rate=0.055, l2_regularization=0.02, random_state=42)),
        ]
    )
    model.fit(x_train, scoped_train[target].astype(int))
    pred = model.predict(x_test)
    distribution = scoped_train[target].astype(int).value_counts().sort_index()
    return {
        "ok": True,
        "rows": int(len(scoped_train) + len(scoped_test)),
        "train_class_distribution": {str(int(key)): int(value) for key, value in distribution.items()},
        "accuracy": scalar(accuracy_score(scoped_test[target].astype(int), pred)),
        "balanced_accuracy": scalar(balanced_accuracy_score(scoped_test[target].astype(int), pred)),
        "predicted_trade_rate": scalar(np.mean(pred != 0)),
    }


def train() -> dict[str, Any]:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    frame = load_dataset()
    quality = load_quality()
    train_frame, test_frame = split_by_time(frame)
    x_train = feature_matrix(train_frame)
    x_test = feature_matrix(test_frame).reindex(columns=x_train.columns, fill_value=0.0)

    regressor = Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", HistGradientBoostingRegressor(max_iter=180, learning_rate=0.055, l2_regularization=0.02, random_state=42)),
        ]
    )
    classifier = Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", HistGradientBoostingClassifier(max_iter=180, learning_rate=0.055, l2_regularization=0.02, random_state=42)),
        ]
    )
    ranker = Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", HistGradientBoostingRegressor(max_iter=180, learning_rate=0.055, l2_regularization=0.02, random_state=42)),
        ]
    )

    regressor.fit(x_train, train_frame[TARGET_RETURN])
    classifier.fit(x_train, train_frame[TARGET_UP].astype(int))
    ranker.fit(x_train, train_frame[TARGET_RANK])

    pred_return = regressor.predict(x_test)
    pred_up_probability = classifier.predict_proba(x_test)[:, 1]
    pred_rank = ranker.predict(x_test)

    latest_date = frame["date"].max()
    latest_frame = frame[frame["date"] == latest_date].copy()
    latest_x = feature_matrix(latest_frame).reindex(columns=x_train.columns, fill_value=0.0)
    latest_frame["pred_return_5_open_pct"] = regressor.predict(latest_x)
    latest_frame["pred_up_probability"] = classifier.predict_proba(latest_x)[:, 1]
    latest_frame["pred_rank_score"] = ranker.predict(latest_x)
    latest_frame["pred_signal"] = np.where(latest_frame["pred_return_5_open_pct"] > 0, "bullish", "bearish")
    latest_frame["rank_position"] = latest_frame["pred_rank_score"].rank(ascending=False, method="first").astype(int)
    latest_frame = latest_frame.sort_values(["rank_position", "pair"])

    prediction_columns = [
        "date",
        "pair",
        "close",
        "volume",
        "pred_return_5_open_pct",
        "pred_up_probability",
        "pred_rank_score",
        "rank_position",
        "pred_signal",
    ]
    latest_frame[prediction_columns].to_csv(PREDICTIONS_PATH, index=False)

    task_metrics = {
        "regression": regression_metrics(test_frame[TARGET_RETURN], pred_return),
        "binary_classification": classification_metrics(test_frame[TARGET_UP].astype(int), pred_up_probability),
        "cross_sectional_ranking": ranking_metrics(test_frame, pred_rank),
    }
    auxiliary_tasks = {
        "long_horizon_12_regression": train_regression_task(train_frame, test_frame, TARGET_RETURN_12)
        if TARGET_RETURN_12 in frame.columns
        else {"ok": False, "error": "missing_target"},
        "long_horizon_12_classification": train_classification_task(train_frame, test_frame, TARGET_UP_12)
        if TARGET_UP_12 in frame.columns
        else {"ok": False, "error": "missing_target"},
        "barrier_long_12_classification": train_classification_task(train_frame, test_frame, TARGET_BARRIER, threshold=0.50)
        if TARGET_BARRIER in frame.columns
        else {"ok": False, "error": "missing_target"},
        "atr_normalized_5_regression": train_regression_task(train_frame, test_frame, TARGET_RETURN_ATR)
        if TARGET_RETURN_ATR in frame.columns
        else {"ok": False, "error": "missing_target"},
        "atr_triclass_5_classification": train_multiclass_task(train_frame, test_frame, TARGET_TRICLASS)
        if TARGET_TRICLASS in frame.columns
        else {"ok": False, "error": "missing_target"},
    }
    gate = deployment_gate(task_metrics)
    tradable = latest_frame[
        (latest_frame["pred_return_5_open_pct"] > 0)
        & (latest_frame["pred_up_probability"] >= 0.55)
        & (latest_frame["rank_position"] <= 5)
        & (latest_frame["volume"] > 0)
    ].copy()
    signals = {
        "generated_at": now_utc(),
        "source_dataset": str(INPUT_PATH),
        "latest_timestamp": latest_date.isoformat(),
        "deployment_gate": gate,
        "label_horizon": "5 candles, next open to open after 5 candles",
        "pred_definition": {
            "pred_return_5_open_pct": "regression estimate; positive means bullish",
            "pred_up_probability": "binary classification probability for label_up_5",
            "pred_rank_score": "cross-sectional ranking score; higher means better long candidate",
        },
        "research_long_candidates": json.loads(tradable[prediction_columns].head(10).to_json(orient="records", date_format="iso")),
        "top_long_candidates": json.loads(latest_frame[prediction_columns].head(10).to_json(orient="records", date_format="iso")),
        "avoid_or_short_candidates": json.loads(latest_frame[prediction_columns].tail(10).to_json(orient="records", date_format="iso")),
    }
    SIGNALS_PATH.write_text(json.dumps(signals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {
        "generated_at": now_utc(),
        "ok": True,
        "model_family": "sklearn_hist_gradient_boosting",
        "lightgbm_available": False,
        "note": "LightGBM is not installed in the current Freqtrade container; sklearn HistGradientBoosting is used as a local gradient-boosting fallback.",
        "dataset": {
            "source_path": str(CLEAN_INPUT_PATH if CLEAN_INPUT_PATH.exists() else INPUT_PATH),
            "quality": {
                "available": quality.get("available"),
                "pairs_total": quality.get("pairs_total"),
                "pairs_passed": quality.get("pairs_passed"),
                "pairs_rejected": quality.get("pairs_rejected"),
                "passed_pairs": quality.get("passed_pairs"),
                "rejected_pairs": quality.get("rejected_pairs"),
                "rules": quality.get("rules"),
            },
            "rows": int(len(frame)),
            "pairs": int(frame["pair"].nunique()),
            "start": frame["date"].min().isoformat(),
            "end": frame["date"].max().isoformat(),
            "train_rows": int(len(train_frame)),
            "test_rows": int(len(test_frame)),
            "features": FEATURE_COLUMNS,
            "label": TARGET_RETURN,
        },
        "tasks": task_metrics,
        "auxiliary_tasks": auxiliary_tasks,
        "deployment_gate": gate,
        "artifacts": {
            "model_path": str(MODEL_PATH),
            "training_report": str(REPORT_PATH),
            "predictions_latest": str(PREDICTIONS_PATH),
            "latest_signals": str(SIGNALS_PATH),
        },
    }
    with MODEL_PATH.open("wb") as handle:
        pickle.dump(
            {
                "feature_columns": list(x_train.columns),
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
