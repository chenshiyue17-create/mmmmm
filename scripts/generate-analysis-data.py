#!/usr/bin/env python3
from __future__ import annotations

import json
import ast
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "user_data" / "config.json"
STRATEGY_PATH = ROOT / "user_data" / "strategies" / "DatugouBreakoutStrategy.py"
DB_PATH = ROOT / "user_data" / "tradesv3.sqlite"
OUTPUT_PATH = ROOT / "custom_ui" / "analysis-data.json"
ML_SIGNALS_PATH = ROOT / "output" / "ml_models" / "latest_signals.json"
ML_TRAINING_REPORT_PATH = ROOT / "output" / "ml_models" / "training_report.json"
ML_DATASET_SUMMARY_PATH = ROOT / "output" / "ml_raw_3mo" / "dataset_summary.json"
ML_SEQUENCE_REPORT_PATH = ROOT / "output" / "ml_sequence_models" / "sequence_report.json"
ML_DEEP_SEQUENCE_REPORT_PATH = ROOT / "output" / "ml_deep_sequence_models" / "deep_sequence_report.json"
QLIB_REPORT_PATH = ROOT / "output" / "qlib" / "okx_1h" / "qlib_fusion_report.json"
QLIB_MLRUNS_PATH = ROOT / "output" / "qlib" / "okx_1h" / "mlruns"
GEMINI_STATUS_PATH = ROOT / "output" / "gemini-optimizer-status.json"
GEMINI_CONTRACT_PATH = ROOT / "output" / "gemini-optimizer-contract.json"
GEMINI_BACKLOG_PATH = ROOT / "output" / "gemini-optimizer-backlog.json"
AUTOPILOT_FLOW_PATH = ROOT / "user_data" / "datugou_flow.autopilot.json"
OKX_SANDBOX_REPORT_PATH = ROOT / "output" / "okx-sandbox-api-check.json"
VIRTUAL_TRADE_REPORT_PATH = ROOT / "output" / "dryrun-trade-test.json"
AUTO_WATCH_STATUS_PATH = ROOT / "output" / "auto-watch-status.json"
GUARDIAN_STATUS_PATH = ROOT / "output" / "stability-guardian-status.json"


def read_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def read_strategy_defaults() -> dict[str, Any]:
    if not STRATEGY_PATH.exists():
        return {}
    text = STRATEGY_PATH.read_text(encoding="utf-8")
    defaults: dict[str, Any] = {}
    stoploss = re.search(r"^\s*stoploss\s*=\s*([-0-9.]+)", text, flags=re.MULTILINE)
    if stoploss:
        defaults["stoploss"] = float(stoploss.group(1))
    roi = re.search(r"^\s*minimal_roi\s*=\s*(\{.*?\})", text, flags=re.MULTILINE | re.DOTALL)
    if roi:
        try:
            defaults["minimal_roi"] = ast.literal_eval(roi.group(1))
        except (SyntaxError, ValueError):
            pass
    return defaults


def safe_query(sql: str) -> list[dict[str, Any]]:
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute(sql).fetchall()]
        conn.close()
        return rows
    except sqlite3.Error:
        return []


def read_metric(path: Path) -> float | None:
    if not path.exists():
        return None
    value: float | None = None
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) >= 2:
                value = float(parts[1])
    except (OSError, ValueError):
        return None
    return value


def latest_qlib_run() -> Path | None:
    if not QLIB_MLRUNS_PATH.exists():
        return None
    candidates = [path for path in QLIB_MLRUNS_PATH.glob("*/*") if (path / "artifacts" / "pred.pkl").exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def build_ai_snapshot() -> dict[str, Any]:
    signals = read_json(ML_SIGNALS_PATH, {})
    training = read_json(ML_TRAINING_REPORT_PATH, {})
    dataset = read_json(ML_DATASET_SUMMARY_PATH, {})
    sequence = read_json(ML_SEQUENCE_REPORT_PATH, {})
    deep_sequence = read_json(ML_DEEP_SEQUENCE_REPORT_PATH, {})
    qlib_report = read_json(QLIB_REPORT_PATH, {})
    qlib_run = latest_qlib_run()
    training_tasks = training.get("tasks", {})
    qlib_metrics = {}
    if qlib_run:
        metric_dir = qlib_run / "metrics"
        qlib_metrics = {
            "IC": read_metric(metric_dir / "IC"),
            "ICIR": read_metric(metric_dir / "ICIR"),
            "Rank IC": read_metric(metric_dir / "Rank IC"),
            "Rank ICIR": read_metric(metric_dir / "Rank ICIR"),
            "l2.train": read_metric(metric_dir / "l2.train"),
            "l2.valid": read_metric(metric_dir / "l2.valid"),
        }

    gate = signals.get("deployment_gate") or {}
    candidates = signals.get("research_long_candidates") or []
    return {
        "generated_at": signals.get("generated_at") or training.get("generated_at"),
        "latest_timestamp": signals.get("latest_timestamp"),
        "deployment_gate": gate,
        "label_horizon": signals.get("label_horizon"),
        "label_definition": dataset.get("label_definition", {}),
        "dataset": {
            "rows": training.get("dataset", {}).get("rows") or dataset.get("rows"),
            "pairs": training.get("dataset", {}).get("pairs") or dataset.get("pairs"),
            "start": training.get("dataset", {}).get("start") or dataset.get("start"),
            "end": training.get("dataset", {}).get("end") or dataset.get("end"),
            "features": len(training.get("dataset", {}).get("features", [])),
            "passed_pairs": training.get("dataset", {}).get("quality", {}).get("passed_pairs")
            or read_json(ROOT / "output" / "ml_raw_3mo" / "data_quality_report.json", {}).get("passed_pairs", []),
        },
        "models": {
            "local_model_family": training.get("model_family"),
            "lightgbm_available": training.get("lightgbm_available"),
            "sequence_model_family": sequence.get("model_family"),
            "deep_sequence_model_family": deep_sequence.get("model_family"),
            "qlib_model_family": qlib_report.get("model_family"),
            "qlib_run_path": str(qlib_run.relative_to(ROOT)) if qlib_run else "",
        },
        "metrics": {
            "regression": training_tasks.get("regression", {}),
            "classification": training_tasks.get("binary_classification", {}),
            "ranking": training_tasks.get("cross_sectional_ranking", {}),
            "sequence": sequence.get("tasks", {}),
            "qlib": qlib_metrics,
        },
        "sequence": {
            "ok": sequence.get("ok"),
            "lookback_candles": sequence.get("lookback_candles"),
            "dataset": sequence.get("dataset", {}),
            "dependency_status": sequence.get("dependency_status", {}),
            "deep_learning_models": sequence.get("deep_learning_models", {}),
            "top_sequence_candidates": (sequence.get("top_sequence_candidates") or [])[:6],
            "latest_timestamp": sequence.get("latest_timestamp"),
        },
        "deep_sequence": {
            "ok": deep_sequence.get("ok"),
            "model_family": deep_sequence.get("model_family"),
            "torch_version": deep_sequence.get("torch_version"),
            "device": deep_sequence.get("device"),
            "lookback_candles": deep_sequence.get("lookback_candles"),
            "dataset": deep_sequence.get("dataset", {}),
            "models": deep_sequence.get("models", {}),
            "top_deep_candidates": (deep_sequence.get("top_deep_candidates") or [])[:6],
            "latest_timestamp": deep_sequence.get("latest_timestamp"),
        },
        "research_long_candidates": candidates[:8],
        "summary": {
            "gate_passed": bool(gate.get("passed")),
            "mode": gate.get("mode", "unknown"),
            "failed_checks": gate.get("failed_checks", []),
            "top_pair": candidates[0].get("pair") if candidates else "",
            "top_pred_signal": candidates[0].get("pred_signal") if candidates else "",
            "qlib_rank_ic": qlib_metrics.get("Rank IC"),
            "qlib_ic": qlib_metrics.get("IC"),
        },
    }


def build_autopilot_snapshot() -> dict[str, Any]:
    status = read_json(GEMINI_STATUS_PATH, {})
    contract = read_json(GEMINI_CONTRACT_PATH, {})
    backlog = read_json(GEMINI_BACKLOG_PATH, {})
    overlay = read_json(AUTOPILOT_FLOW_PATH, {})
    return {
        "enabled": status.get("automation_enabled", contract.get("automation_enabled")),
        "ok": status.get("ok"),
        "checked_at": status.get("checked_at"),
        "summary": status.get("summary"),
        "actions_requested": status.get("actions_requested", 0),
        "actions_applied": status.get("actions_applied", 0),
        "actions_rejected": status.get("actions_rejected", 0),
        "report_path": status.get("report_path"),
        "request_path": status.get("request_path"),
        "response_path": status.get("response_path"),
        "action_log_path": status.get("action_log_path"),
        "overlay": {
            "applied_at": overlay.get("applied_at"),
            "reason": overlay.get("reason"),
            "confidence": overlay.get("confidence"),
            "parameters": overlay.get("parameters", {}),
        },
        "backlog": (backlog.get("items") or [])[:6],
        "allowed_parameters": contract.get("allowed_parameters", {}),
    }


def okx_sandbox_runtime(config: dict[str, Any], okx_report: dict[str, Any]) -> bool:
    return (
        config.get("exchange", {}).get("name") == "okx"
        and config.get("dry_run") is False
        and okx_report.get("mode") == "sandbox"
        and bool(okx_report.get("private_balance", {}).get("ok"))
    )


def build_balance_snapshot(
    config: dict[str, Any],
    dry_wallet: float,
    total_stake: float,
    stake_amount: float,
    okx_report: dict[str, Any],
) -> dict[str, Any]:
    stake_currency = config.get("stake_currency", "USDT")
    private = okx_report.get("private_balance", {})
    if okx_sandbox_runtime(config, okx_report):
        total_eq = float(private.get("totalEq") or 0)
        currencies = private.get("currencies") or []
        usdt = next((item for item in currencies if item.get("ccy") == "USDT"), {})
        available = float(usdt.get("availBal") or 0)
        return {
            "currencies": currencies,
            "total": total_eq,
            "total_bot": total_eq,
            "symbol": "USD",
            "value": total_eq,
            "value_bot": total_eq,
            "stake": "USD",
            "note": "OKX 模拟盘账户权益",
            "available_stake": available,
            "starting_capital": total_eq,
            "starting_capital_ratio": 0,
            "checked_at": okx_report.get("checked_at"),
        }
    return {
        "currencies": [
            {
                "currency": stake_currency,
                "free": max(dry_wallet - total_stake, 0),
                "balance": dry_wallet,
                "used": total_stake,
                "bot_owned": dry_wallet - stake_amount * 0.1,
                "est_stake": dry_wallet,
                "est_stake_bot": dry_wallet - stake_amount * 0.1,
                "stake": stake_currency,
            }
        ],
        "total": dry_wallet,
        "total_bot": dry_wallet - stake_amount * 0.1,
        "symbol": "USD",
        "value": dry_wallet,
        "value_bot": dry_wallet - stake_amount * 0.1,
        "stake": stake_currency,
        "note": "本地模拟余额快照",
        "starting_capital": dry_wallet - stake_amount * 0.1,
        "starting_capital_ratio": 0,
    }


def build_daily(days: int = 14) -> dict[str, Any]:
    today = datetime.now(timezone.utc).date()
    data = []
    for offset in range(days):
        date = today - timedelta(days=offset)
        data.append(
            {
                "date": date.isoformat(),
                "abs_profit": 0.0,
                "rel_profit": 0.0,
                "starting_balance": 990.0,
                "fiat_value": 0.0,
                "trade_count": 0,
            }
        )
    return {"data": data}


def main() -> None:
    config = read_config()
    strategy_defaults = read_strategy_defaults()
    trades = safe_query(
        """
        SELECT pair, stake_amount, open_rate, close_rate, profit_ratio,
               open_date, close_date, is_open
        FROM trades
        ORDER BY open_date DESC
        LIMIT 100
        """
    )
    auto_watch = read_json(AUTO_WATCH_STATUS_PATH, {})
    guardian_status = read_json(GUARDIAN_STATUS_PATH, {})
    open_trades = [trade for trade in trades if trade.get("is_open")]
    closed_trades = [trade for trade in trades if not trade.get("is_open")]
    if auto_watch.get("ok") and isinstance(auto_watch.get("open_trades"), list):
        open_trades = auto_watch["open_trades"]
    stake_currency = config.get("stake_currency", "USDT")
    dry_wallet = float(config.get("dry_run_wallet", 1000))
    stake_amount = float(config.get("stake_amount", 100))
    max_open = int(float(config.get("max_open_trades", 3)))
    whitelist = (
        auto_watch.get("dynamic_pairlist")
        if auto_watch.get("ok") and isinstance(auto_watch.get("dynamic_pairlist"), list)
        else config.get("exchange", {}).get("pair_whitelist", [])
    )
    okx_report = read_json(OKX_SANDBOX_REPORT_PATH, {})
    virtual_trade_report = read_json(VIRTUAL_TRADE_REPORT_PATH, {})
    virtual_mode = (
        "okx_sandbox"
        if okx_sandbox_runtime(config, okx_report)
        else "freqtrade_dry_run"
        if bool(config.get("dry_run", True))
        else "unsafe_live"
    )

    total_stake = sum(float(trade.get("stake_amount") or 0) for trade in open_trades)
    profit_all = sum(float(trade.get("profit_ratio") or 0) * float(trade.get("stake_amount") or 0) for trade in trades)

    payload = {
        "source": "local_snapshot",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "version": "local-snapshot",
            "dry_run": bool(config.get("dry_run", True)),
            "trading_mode": config.get("trading_mode", "spot"),
            "margin_mode": config.get("margin_mode", ""),
            "stake_currency": stake_currency,
            "stake_amount": config.get("stake_amount", "100"),
            "max_open_trades": max_open,
            "minimal_roi": config.get("minimal_roi", strategy_defaults.get("minimal_roi", {})),
            "stoploss": config.get("stoploss", strategy_defaults.get("stoploss", 0)),
            "trailing_stop": config.get("trailing_stop", False),
            "timeframe": config.get("timeframe", "1h"),
            "strategy": config.get("strategy", "DatugouBreakoutStrategy"),
            "exchange": config.get("exchange", {}).get("name", "unknown"),
            "virtual_mode": virtual_mode,
            "okx_sandbox": virtual_mode == "okx_sandbox",
        },
        "balance": build_balance_snapshot(config, dry_wallet, total_stake, stake_amount, okx_report),
        "profit": {
            "profit_all_coin": profit_all,
            "profit_all_ratio": float(auto_watch.get("profit_all_percent") or 0) / 100 if auto_watch.get("ok") else 0,
            "trade_count": auto_watch.get("trade_count") if auto_watch.get("ok") else len(trades),
            "closed_trade_count": len(closed_trades),
        },
        "count": {
            "current": auto_watch.get("open_trade_count") if auto_watch.get("ok") else len(open_trades),
            "max": auto_watch.get("max_open_trades") if auto_watch.get("ok") else max_open,
            "total_stake": total_stake,
        },
        "status": open_trades,
        "performance": [],
        "whitelist": {"whitelist": whitelist},
        "daily": build_daily(),
        "ai": build_ai_snapshot(),
        "autopilot": build_autopilot_snapshot(),
        "execution": {
            "virtual_mode": virtual_mode,
            "last_trade_status": virtual_trade_report.get("status"),
            "last_trade_pair": virtual_trade_report.get("pair"),
            "last_trade_id": virtual_trade_report.get("entry", {}).get("trade_id"),
            "last_trade_profit_pct": virtual_trade_report.get("exit", {}).get("profit_pct"),
            "last_trade_checked_at": virtual_trade_report.get("checked_at"),
        },
        "guardian": guardian_status,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
