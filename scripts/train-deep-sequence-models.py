#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, mean_absolute_error, mean_squared_error, precision_score, recall_score
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


ROOT = Path(os.getenv("FT_PROJECT_ROOT", "/workspace"))
INPUT_PATH = ROOT / "output" / "ml_raw_3mo" / "features_labels_1h_clean.csv"
MODEL_DIR = ROOT / "output" / "ml_deep_sequence_models"
REPORT_PATH = MODEL_DIR / "deep_sequence_report.json"
PREDICTIONS_PATH = MODEL_DIR / "deep_sequence_predictions_latest.csv"
LSTM_MODEL_PATH = MODEL_DIR / "lstm_regressor.pt"
TRANSFORMER_MODEL_PATH = MODEL_DIR / "transformer_regressor.pt"

LOOKBACK = int(os.getenv("ML_DEEP_LOOKBACK_CANDLES", "24"))
TEST_FRACTION = float(os.getenv("ML_DEEP_TEST_FRACTION", "0.20"))
EPOCHS = int(os.getenv("ML_DEEP_EPOCHS", "6"))
BATCH_SIZE = int(os.getenv("ML_DEEP_BATCH_SIZE", "256"))
LEARNING_RATE = float(os.getenv("ML_DEEP_LEARNING_RATE", "0.001"))
HIDDEN_SIZE = int(os.getenv("ML_DEEP_HIDDEN_SIZE", "32"))
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

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


def seed_everything(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(int(os.getenv("DEEP_RESEARCH_THREADS", "2")))


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


def load_dataset() -> pd.DataFrame:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Missing clean ML dataset: {INPUT_PATH}")
    frame = pd.read_csv(INPUT_PATH)
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    required = ["date", "pair", TARGET_RETURN, TARGET_UP, TARGET_RANK, *FEATURE_COLUMNS]
    frame = frame.dropna(subset=required).sort_values(["pair", "date"]).reset_index(drop=True)
    if frame.empty:
        raise ValueError("Clean ML dataset has no usable rows for deep sequence training.")
    return frame


def build_sequences(frame: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
    xs: list[np.ndarray] = []
    rows: list[dict[str, Any]] = []
    for pair, group in frame.groupby("pair", sort=True):
        group = group.sort_values("date").reset_index(drop=True)
        values = group[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=np.float32)
        for index in range(LOOKBACK - 1, len(group)):
            xs.append(values[index - LOOKBACK + 1 : index + 1])
            rows.append(
                {
                    "date": group.loc[index, "date"],
                    "pair": pair,
                    "close": group.loc[index, "close"] if "close" in group else None,
                    TARGET_RETURN: float(group.loc[index, TARGET_RETURN]),
                    TARGET_UP: int(group.loc[index, TARGET_UP]),
                    TARGET_RANK: float(group.loc[index, TARGET_RANK]),
                }
            )
    if not xs:
        raise ValueError(f"Not enough rows to build {LOOKBACK}-candle deep sequences.")
    return np.stack(xs), pd.DataFrame(rows).sort_values(["date", "pair"]).reset_index(drop=True)


def split_by_time(meta: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    unique_dates = meta["date"].drop_duplicates().sort_values()
    if len(unique_dates) < 20:
        raise ValueError("Deep sequence dataset does not have enough timestamps for a time split.")
    split_index = max(1, min(len(unique_dates) - 1, int(len(unique_dates) * (1 - TEST_FRACTION))))
    split_date = unique_dates.iloc[split_index]
    train_idx = meta.index[meta["date"] < split_date].to_numpy()
    test_idx = meta.index[meta["date"] >= split_date].to_numpy()
    if len(train_idx) == 0 or len(test_idx) == 0:
        raise ValueError("Deep sequence time split produced empty train or test set.")
    return train_idx, test_idx


class LSTMRegressor(nn.Module):
    def __init__(self, input_size: int, hidden_size: int) -> None:
        super().__init__()
        self.lstm = nn.LSTM(input_size=input_size, hidden_size=hidden_size, batch_first=True)
        self.head = nn.Sequential(nn.LayerNorm(hidden_size), nn.Linear(hidden_size, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, (hidden, _) = self.lstm(x)
        return self.head(hidden[-1]).squeeze(-1)


class TransformerRegressor(nn.Module):
    def __init__(self, input_size: int, hidden_size: int) -> None:
        super().__init__()
        self.input_projection = nn.Linear(input_size, hidden_size)
        self.position = nn.Parameter(torch.zeros(1, LOOKBACK, hidden_size))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_size,
            nhead=4,
            dim_feedforward=hidden_size * 2,
            dropout=0.05,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=2)
        self.head = nn.Sequential(nn.LayerNorm(hidden_size), nn.Linear(hidden_size, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        encoded = self.input_projection(x) + self.position[:, : x.shape[1], :]
        encoded = self.encoder(encoded)
        return self.head(encoded[:, -1, :]).squeeze(-1)


@dataclass
class TrainResult:
    model: nn.Module
    train_loss: list[float]
    test_pred: np.ndarray
    latest_pred: np.ndarray


def standardize_sequences(x_train: np.ndarray, x_test: np.ndarray, x_latest: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, StandardScaler]:
    scaler = StandardScaler()
    flat_train = x_train.reshape(-1, x_train.shape[-1])
    scaler.fit(flat_train)

    def transform(values: np.ndarray) -> np.ndarray:
        shape = values.shape
        return scaler.transform(values.reshape(-1, shape[-1])).reshape(shape).astype(np.float32)

    return transform(x_train), transform(x_test), transform(x_latest), scaler


def train_model(model: nn.Module, x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray, x_latest: np.ndarray) -> TrainResult:
    model = model.to(DEVICE)
    dataset = TensorDataset(torch.tensor(x_train, dtype=torch.float32), torch.tensor(y_train, dtype=torch.float32))
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=0.01)
    loss_fn = nn.SmoothL1Loss()
    losses: list[float] = []
    for _ in range(EPOCHS):
        model.train()
        total = 0.0
        seen = 0
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(DEVICE)
            batch_y = batch_y.to(DEVICE)
            optimizer.zero_grad(set_to_none=True)
            pred = model(batch_x)
            loss = loss_fn(pred, batch_y)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total += float(loss.item()) * len(batch_x)
            seen += len(batch_x)
        losses.append(total / max(seen, 1))
    model.eval()
    with torch.no_grad():
        test_pred = model(torch.tensor(x_test, dtype=torch.float32, device=DEVICE)).detach().cpu().numpy()
        latest_pred = model(torch.tensor(x_latest, dtype=torch.float32, device=DEVICE)).detach().cpu().numpy()
    return TrainResult(model=model.cpu(), train_loss=losses, test_pred=test_pred, latest_pred=latest_pred)


def regression_metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, Any]:
    corr = pd.Series(y_pred).corr(pd.Series(y_true).reset_index(drop=True))
    return {
        "mae": scalar(mean_absolute_error(y_true, y_pred)),
        "rmse": scalar(math.sqrt(mean_squared_error(y_true, y_pred))),
        "corr": scalar(corr),
        "pred_mean": scalar(np.mean(y_pred)),
    }


def derived_classification_metrics(y_true: pd.Series, y_pred_return: np.ndarray) -> dict[str, Any]:
    pred = (y_pred_return > 0).astype(int)
    return {
        "threshold": 0.0,
        "accuracy": scalar(accuracy_score(y_true, pred)),
        "precision": scalar(precision_score(y_true, pred, zero_division=0)),
        "recall": scalar(recall_score(y_true, pred, zero_division=0)),
        "positive_rate": scalar(np.mean(pred)),
    }


def ranking_metrics(test_meta: pd.DataFrame, scores: np.ndarray) -> dict[str, Any]:
    scored = test_meta[["date", TARGET_RANK, TARGET_RETURN]].copy()
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


def model_report(name: str, test_meta: pd.DataFrame, pred: np.ndarray, losses: list[float]) -> dict[str, Any]:
    return {
        "status": "trained",
        "epochs": EPOCHS,
        "final_train_loss": scalar(losses[-1] if losses else None),
        "train_loss": [scalar(value) for value in losses],
        "regression": regression_metrics(test_meta[TARGET_RETURN], pred),
        "derived_binary_classification": derived_classification_metrics(test_meta[TARGET_UP].astype(int), pred),
        "cross_sectional_ranking": ranking_metrics(test_meta, pred),
        "pred_definition": f"{name} regression pred for 5-candle open-to-open return; positive means bullish",
    }


def train() -> dict[str, Any]:
    seed_everything()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    raw = load_dataset()
    x_all, meta = build_sequences(raw)
    train_idx, test_idx = split_by_time(meta)
    latest_date = meta["date"].max()
    latest_idx = meta.index[meta["date"] == latest_date].to_numpy()

    x_train_raw = x_all[train_idx]
    x_test_raw = x_all[test_idx]
    x_latest_raw = x_all[latest_idx]
    x_train, x_test, x_latest, scaler = standardize_sequences(x_train_raw, x_test_raw, x_latest_raw)
    y_train = meta.iloc[train_idx][TARGET_RETURN].to_numpy(dtype=np.float32)
    test_meta = meta.iloc[test_idx].reset_index(drop=True)
    latest_meta = meta.iloc[latest_idx].copy().reset_index(drop=True)

    lstm_result = train_model(LSTMRegressor(len(FEATURE_COLUMNS), HIDDEN_SIZE), x_train, y_train, x_test, x_latest)
    transformer_result = train_model(TransformerRegressor(len(FEATURE_COLUMNS), HIDDEN_SIZE), x_train, y_train, x_test, x_latest)

    latest_meta["lstm_pred_return_5_open_pct"] = lstm_result.latest_pred
    latest_meta["transformer_pred_return_5_open_pct"] = transformer_result.latest_pred
    latest_meta["deep_ensemble_pred_return_5_open_pct"] = (
        latest_meta["lstm_pred_return_5_open_pct"] + latest_meta["transformer_pred_return_5_open_pct"]
    ) / 2
    latest_meta["deep_rank_position"] = latest_meta["deep_ensemble_pred_return_5_open_pct"].rank(ascending=False, method="first").astype(int)
    latest_meta["deep_pred_signal"] = np.where(latest_meta["deep_ensemble_pred_return_5_open_pct"] > 0, "bullish", "bearish")
    latest_meta = latest_meta.sort_values(["deep_rank_position", "pair"])
    prediction_columns = [
        "date",
        "pair",
        "close",
        "lstm_pred_return_5_open_pct",
        "transformer_pred_return_5_open_pct",
        "deep_ensemble_pred_return_5_open_pct",
        "deep_rank_position",
        "deep_pred_signal",
    ]
    latest_meta[prediction_columns].to_csv(PREDICTIONS_PATH, index=False)

    torch.save({"model_state": lstm_result.model.state_dict(), "feature_columns": FEATURE_COLUMNS, "scaler": scaler}, LSTM_MODEL_PATH)
    torch.save({"model_state": transformer_result.model.state_dict(), "feature_columns": FEATURE_COLUMNS, "scaler": scaler}, TRANSFORMER_MODEL_PATH)

    ensemble_test_pred = (lstm_result.test_pred + transformer_result.test_pred) / 2
    report = {
        "generated_at": now_utc(),
        "ok": True,
        "model_family": "pytorch_lstm_transformer_sequence",
        "torch_version": torch.__version__,
        "device": str(DEVICE),
        "lookback_candles": LOOKBACK,
        "target": TARGET_RETURN,
        "input_path": str(INPUT_PATH),
        "dataset": {
            "raw_rows": int(len(raw)),
            "sequence_rows": int(len(meta)),
            "pairs": int(meta["pair"].nunique()),
            "start": meta["date"].min().isoformat(),
            "end": meta["date"].max().isoformat(),
            "train_rows": int(len(train_idx)),
            "test_rows": int(len(test_idx)),
            "features_per_step": len(FEATURE_COLUMNS),
        },
        "models": {
            "lstm": model_report("LSTM", test_meta, lstm_result.test_pred, lstm_result.train_loss),
            "transformer": model_report("Transformer", test_meta, transformer_result.test_pred, transformer_result.train_loss),
            "ensemble": {
                "status": "trained",
                "regression": regression_metrics(test_meta[TARGET_RETURN], ensemble_test_pred),
                "derived_binary_classification": derived_classification_metrics(test_meta[TARGET_UP].astype(int), ensemble_test_pred),
                "cross_sectional_ranking": ranking_metrics(test_meta, ensemble_test_pred),
            },
        },
        "signal_contract": {
            "lstm_pred_return_5_open_pct": "LSTM short-memory regression pred; positive means bullish",
            "transformer_pred_return_5_open_pct": "Transformer attention regression pred; positive means bullish",
            "deep_ensemble_pred_return_5_open_pct": "average of LSTM and Transformer pred values",
            "deep_rank_position": "1 is strongest deep sequence candidate at the latest timestamp",
        },
        "latest_timestamp": latest_date.isoformat(),
        "top_deep_candidates": json.loads(latest_meta[prediction_columns].head(10).to_json(orient="records", date_format="iso")),
        "bottom_deep_candidates": json.loads(latest_meta[prediction_columns].tail(10).to_json(orient="records", date_format="iso")),
        "artifacts": {
            "lstm_model": str(LSTM_MODEL_PATH),
            "transformer_model": str(TRANSFORMER_MODEL_PATH),
            "deep_sequence_report": str(REPORT_PATH),
            "deep_sequence_predictions_latest": str(PREDICTIONS_PATH),
        },
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    report = train()
    print(json.dumps({"ok": report["ok"], "model_family": report["model_family"], "artifacts": report["artifacts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
