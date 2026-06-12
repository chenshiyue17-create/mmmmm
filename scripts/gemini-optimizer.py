#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "output" / "auto-watch-status.json"
EVIDENCE_PATH = ROOT / "output" / "ml_raw_3mo" / "gemini_evidence_pack.json"
TRAINING_REPORT_PATH = ROOT / "output" / "ml_models" / "training_report.json"
LATEST_SIGNALS_PATH = ROOT / "output" / "ml_models" / "latest_signals.json"
REPORT_PATH = ROOT / "output" / "gemini-optimizer-report.md"
STATE_PATH = ROOT / "output" / "gemini-optimizer-status.json"
REQUEST_PATH = ROOT / "output" / "gemini-optimizer-request.json"
RESPONSE_PATH = ROOT / "output" / "gemini-optimizer-response.json"
ACTION_LOG_PATH = ROOT / "output" / "gemini-optimizer-actions.jsonl"
CONTRACT_PATH = ROOT / "output" / "gemini-optimizer-contract.json"
BACKLOG_PATH = ROOT / "output" / "gemini-optimizer-backlog.json"
LOG_PATH = ROOT / "logs" / "gemini-optimizer.log"
FLOW_PATH = ROOT / "user_data" / "datugou_flow.json"
AUTOPILOT_FLOW_PATH = ROOT / "user_data" / "datugou_flow.autopilot.json"
BACKUP_DIR = ROOT / "output" / "autopilot-backups"

AUTOMATION_ENABLED = os.getenv("GEMINI_AUTOMATION_ENABLED", "1") == "1"

PARAMETER_BOUNDS: dict[str, tuple[float, float, type]] = {
    "breakout_lookback": (12, 72, int),
    "volume_window": (12, 72, int),
    "momentum_window": (3, 24, int),
    "min_volume_ratio": (1.05, 4.0, float),
    "min_momentum_pct": (0.5, 8.0, float),
    "stop_loss_pct": (3.0, 12.0, float),
    "take_profit_pct": (6.0, 45.0, float),
    "trailing_stop_pct": (3.0, 20.0, float),
}

SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "apiKey",
    "secret",
    "secret_key",
    "secretKey",
    "password",
    "token",
    "jwt",
    "authorization",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_log(payload: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def append_action_log(payload: dict[str, Any]) -> None:
    ACTION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ACTION_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_contract() -> None:
    write_json(
        CONTRACT_PATH,
        {
            "schema_version": "gemini-autopilot/v1",
            "automation_enabled": AUTOMATION_ENABLED,
            "input_files": {
                "runtime_snapshot": str(STATUS_PATH),
                "evidence_pack": str(EVIDENCE_PATH),
                "training_report": str(TRAINING_REPORT_PATH),
                "latest_signals": str(LATEST_SIGNALS_PATH),
                "base_flow": str(FLOW_PATH),
                "autopilot_overlay": str(AUTOPILOT_FLOW_PATH),
            },
            "output_files": {
                "request": str(REQUEST_PATH),
                "response": str(RESPONSE_PATH),
                "status": str(STATE_PATH),
                "actions": str(ACTION_LOG_PATH),
                "backlog": str(BACKLOG_PATH),
                "report": str(REPORT_PATH),
            },
            "allowed_action_types": ["update_strategy_flow"],
            "allowed_parameters": {
                key: {"min": bounds[0], "max": bounds[1], "type": bounds[2].__name__}
                for key, bounds in PARAMETER_BOUNDS.items()
            },
            "hard_guards": [
                "no API key or secret changes",
                "no leverage changes",
                "no position-size expansion",
                "no live-mode switching",
                "no strategy source-code edits",
                "only user_data/datugou_flow.autopilot.json may be auto-written",
            ],
        },
    )


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key in SENSITIVE_KEYS or any(word in key.lower() for word in ("secret", "password", "token", "key")):
                cleaned[key] = "[REDACTED]"
            else:
                cleaned[key] = sanitize(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize(item) for item in value[:80]]
    return value


def compact_trade(trade: dict[str, Any]) -> dict[str, Any]:
    orders = trade.get("orders") or []
    return {
        "trade_id": trade.get("trade_id"),
        "pair": trade.get("pair"),
        "is_open": trade.get("is_open"),
        "has_open_orders": trade.get("has_open_orders"),
        "successful_entries": trade.get("nr_of_successful_entries"),
        "amount": trade.get("amount"),
        "stake_amount": trade.get("stake_amount"),
        "open_rate": trade.get("open_rate"),
        "current_rate": trade.get("current_rate"),
        "profit_pct": trade.get("profit_pct"),
        "stoploss_current_dist_pct": trade.get("stoploss_current_dist_pct"),
        "open_date": trade.get("open_date"),
        "orders": [
            {
                "side": order.get("ft_order_side"),
                "type": order.get("order_type"),
                "status": order.get("status"),
                "filled": order.get("filled"),
                "remaining": order.get("remaining"),
                "safe_price": order.get("safe_price"),
            }
            for order in orders[:5]
        ],
    }


def load_snapshot() -> dict[str, Any]:
    if not STATUS_PATH.exists():
        raise FileNotFoundError(f"{STATUS_PATH} does not exist. Start auto-watch first.")
    payload = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    trades = payload.get("open_trades") or []
    return sanitize(
        {
            "checked_at": payload.get("checked_at"),
            "mode": payload.get("mode"),
            "engine": payload.get("engine"),
            "exchange": payload.get("exchange"),
            "strategy": payload.get("strategy"),
            "timeframe": payload.get("timeframe"),
            "runmode": payload.get("runmode"),
            "dry_run": payload.get("dry_run"),
            "stake_amount": payload.get("stake_amount"),
            "open_trade_count": payload.get("open_trade_count"),
            "max_open_trades": payload.get("max_open_trades"),
            "trade_count": payload.get("trade_count"),
            "profit_all_percent": payload.get("profit_all_percent"),
            "dynamic_pairlist_count": len(payload.get("dynamic_pairlist") or []),
            "dynamic_pairlist_sample": (payload.get("dynamic_pairlist") or [])[:30],
            "pairlist_methods": payload.get("pairlist_methods"),
            "open_trades": [compact_trade(trade) for trade in trades[:10]],
        }
    )


def load_evidence_pack() -> dict[str, Any]:
    if not EVIDENCE_PATH.exists():
        return {
            "ok": False,
            "error": "missing_3_month_market_evidence",
            "required_action": "run scripts/accumulate-market-data.sh",
            "path": str(EVIDENCE_PATH),
        }
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    compact = {
        "ok": evidence.get("ok"),
        "generated_at": evidence.get("generated_at"),
        "source": evidence.get("source"),
        "exchange": evidence.get("exchange"),
        "timeframe": evidence.get("timeframe"),
        "lookback_days": evidence.get("lookback_days"),
        "label_definition": evidence.get("label_definition"),
        "task_views": evidence.get("task_views"),
        "rows": evidence.get("rows"),
        "pairs": evidence.get("pairs"),
        "start": evidence.get("start"),
        "end": evidence.get("end"),
        "label_return_5_open_pct": evidence.get("label_return_5_open_pct"),
        "factor_correlations": (evidence.get("factor_correlations") or [])[:20],
        "pair_stats": (evidence.get("pair_stats") or [])[:40],
        "sample_rows": (evidence.get("sample_rows") or [])[-40:],
        "dataset_path": evidence.get("dataset_path"),
    }
    return sanitize(compact)


def load_model_pack() -> dict[str, Any]:
    pack: dict[str, Any] = {
        "ok": False,
        "required_action": "run scripts/train-ml-models.sh",
        "training_report_path": str(TRAINING_REPORT_PATH),
        "latest_signals_path": str(LATEST_SIGNALS_PATH),
    }
    if TRAINING_REPORT_PATH.exists():
        report = json.loads(TRAINING_REPORT_PATH.read_text(encoding="utf-8"))
        pack.update(
            {
                "ok": bool(report.get("ok")),
                "model_family": report.get("model_family"),
                "dataset": report.get("dataset"),
                "tasks": report.get("tasks"),
                "auxiliary_tasks": report.get("auxiliary_tasks"),
                "artifacts": report.get("artifacts"),
            }
        )
    if LATEST_SIGNALS_PATH.exists():
        signals = json.loads(LATEST_SIGNALS_PATH.read_text(encoding="utf-8"))
        pack["latest_signals"] = {
            "generated_at": signals.get("generated_at"),
            "latest_timestamp": signals.get("latest_timestamp"),
            "pred_definition": signals.get("pred_definition"),
            "top_long_candidates": (signals.get("top_long_candidates") or [])[:10],
            "avoid_or_short_candidates": (signals.get("avoid_or_short_candidates") or [])[:10],
        }
    return sanitize(pack)


def load_flow_pack() -> dict[str, Any]:
    base = json.loads(FLOW_PATH.read_text(encoding="utf-8")) if FLOW_PATH.exists() else {}
    overlay = json.loads(AUTOPILOT_FLOW_PATH.read_text(encoding="utf-8")) if AUTOPILOT_FLOW_PATH.exists() else {}
    effective = {**base, **(overlay.get("parameters") or {})}
    return sanitize(
        {
            "base_flow_path": str(FLOW_PATH),
            "autopilot_overlay_path": str(AUTOPILOT_FLOW_PATH),
            "base_parameters": {key: base.get(key) for key in PARAMETER_BOUNDS},
            "overlay_parameters": overlay.get("parameters") or {},
            "effective_parameters": {key: effective.get(key) for key in PARAMETER_BOUNDS},
            "last_applied_at": overlay.get("applied_at"),
            "last_reason": overlay.get("reason"),
        }
    )


def build_prompt(snapshot: dict[str, Any], evidence: dict[str, Any], model_pack: dict[str, Any], flow_pack: dict[str, Any]) -> str:
    return (
        "你是本地量化交易自动优化执行器。不要写泛泛建议，要输出可机器执行的 JSON。\n"
        "你必须基于下面的近3个月 OHLCV 因子/标签证据包、模型训练结果/pred 信号、以及当前脱敏运行快照做分析。\n"
        "目标：把 AI 交易优化建立在“出题(标签) -> 教材(因子) -> 学习(模型任务) -> 上岗(信号)”的数据闭环上。\n"
        "硬性规则：\n"
        "1. 不要求、不中继、不猜测任何 API key、secret、password、token。\n"
        "2. 没有证据包或证据不足时，必须说数据不足，不得补脑。\n"
        "3. 标签必须按 evidence.label_definition 理解：下一根开盘价入场，未来5根K线后的开盘价退出。\n"
        "4. 分别给出回归、二分类、横截面排序三种任务怎么用这些数据，不要混为一谈。\n"
        "5. 如果模型训练包缺失或指标差，必须指出模型未达到上岗标准，不得假装可用。\n"
        "6. 只允许生成 update_strategy_flow 动作，不能改 API、仓位、杠杆、交易模式、源码或任何密钥。\n"
        "7. 参数必须在 allowed_parameters 范围内；不确定就输出空 actions。\n"
        "8. 只输出 JSON，不要 Markdown，不要代码块。\n\n"
        "必须输出这个 JSON 结构：\n"
        "{\n"
        '  "schema_version": "gemini-autopilot/v1",\n'
        '  "summary": "一句中文说明",\n'
        '  "actions": [\n'
        '    {"type": "update_strategy_flow", "confidence": 0.0, "reason": "中文理由", "parameters": {"min_volume_ratio": 1.6}}\n'
        "  ],\n"
        '  "backlog": [{"priority": "low|medium|high", "item": "后续自动任务"}]\n'
        "}\n\n"
        f"allowed_parameters JSON：\n{json.dumps({key: {'min': b[0], 'max': b[1], 'type': b[2].__name__} for key, b in PARAMETER_BOUNDS.items()}, ensure_ascii=False, indent=2)}\n\n"
        f"近3个月证据包 JSON：\n{json.dumps(evidence, ensure_ascii=False, indent=2)}\n\n"
        f"模型训练与 pred 信号 JSON：\n{json.dumps(model_pack, ensure_ascii=False, indent=2)}\n\n"
        f"当前策略参数 JSON：\n{json.dumps(flow_pack, ensure_ascii=False, indent=2)}\n\n"
        f"当前运行快照 JSON：\n{json.dumps(snapshot, ensure_ascii=False, indent=2)}\n"
    )


def run_gemini(prompt: str) -> tuple[int, str, str]:
    command = [
        os.getenv("GEMINI_CLI_BIN", "gemini"),
        "--approval-mode",
        "plan",
        "--output-format",
        "text",
        "--prompt",
        prompt,
    ]
    timeout_seconds = int(os.getenv("GEMINI_OPTIMIZER_TIMEOUT_SECONDS", "120"))
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty Gemini response")
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def coerce_parameter(key: str, value: Any) -> int | float:
    low, high, kind = PARAMETER_BOUNDS[key]
    number = float(value)
    if number < low or number > high:
        raise ValueError(f"{key}={number} outside [{low}, {high}]")
    if kind is int:
        return int(round(number))
    return round(number, 4)


def validate_action(action: dict[str, Any]) -> dict[str, Any]:
    if action.get("type") != "update_strategy_flow":
        raise ValueError(f"unsupported action type: {action.get('type')}")
    confidence = float(action.get("confidence", 0))
    if confidence < float(os.getenv("GEMINI_AUTOMATION_MIN_CONFIDENCE", "0.55")):
        raise ValueError(f"confidence too low: {confidence}")
    parameters = action.get("parameters") or {}
    if not isinstance(parameters, dict) or not parameters:
        raise ValueError("action has no parameters")
    clean: dict[str, int | float] = {}
    for key, value in parameters.items():
        if key not in PARAMETER_BOUNDS:
            raise ValueError(f"unsupported parameter: {key}")
        clean[key] = coerce_parameter(key, value)
    return {
        "type": "update_strategy_flow",
        "confidence": confidence,
        "reason": str(action.get("reason", ""))[:500],
        "parameters": clean,
    }


def apply_strategy_flow(action: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    if not AUTOMATION_ENABLED:
        return {"applied": False, "reason": "GEMINI_AUTOMATION_ENABLED=0"}
    validated = validate_action(action)
    current = json.loads(AUTOPILOT_FLOW_PATH.read_text(encoding="utf-8")) if AUTOPILOT_FLOW_PATH.exists() else {}
    current_parameters = current.get("parameters") or {}
    next_parameters = {**current_parameters, **validated["parameters"]}
    if next_parameters == current_parameters:
        return {"applied": False, "reason": "parameters unchanged", "parameters": next_parameters}

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if AUTOPILOT_FLOW_PATH.exists():
        backup = BACKUP_DIR / f"datugou_flow.autopilot.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        shutil.copy2(AUTOPILOT_FLOW_PATH, backup)
    payload = {
        "schema_version": "datugou-autopilot/v1",
        "applied_at": now_utc(),
        "source": "gemini-autopilot",
        "reason": validated["reason"],
        "confidence": validated["confidence"],
        "parameters": next_parameters,
        "gemini_summary": response.get("summary"),
    }
    write_json(AUTOPILOT_FLOW_PATH, payload)
    result = subprocess.run(["bash", "scripts/validate-config.sh"], cwd=ROOT, capture_output=True, text=True, timeout=180, check=False)
    if result.returncode != 0:
        if AUTOPILOT_FLOW_PATH.exists():
            AUTOPILOT_FLOW_PATH.unlink()
        raise RuntimeError(f"validate-config failed after autopilot apply: {result.stderr[-1000:] or result.stdout[-1000:]}")
    return {"applied": True, "parameters": next_parameters, "path": str(AUTOPILOT_FLOW_PATH)}


def apply_actions(response: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for raw_action in response.get("actions") or []:
        try:
            result = apply_strategy_flow(raw_action, response)
            event = {"checked_at": now_utc(), "ok": True, "action": raw_action, "result": result}
        except Exception as exc:  # noqa: BLE001 - action log must capture rejected actions.
            event = {"checked_at": now_utc(), "ok": False, "action": raw_action, "error": f"{type(exc).__name__}: {exc}"[:1000]}
        append_action_log(event)
        results.append(event)
    return results


def write_report(snapshot: dict[str, Any], evidence: dict[str, Any], model_pack: dict[str, Any], output: str, action_results: list[dict[str, Any]]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Gemini 本地优化报告",
                "",
                f"- 生成时间: {now_utc()}",
                f"- 快照时间: {snapshot.get('checked_at')}",
                f"- 交易所: {snapshot.get('exchange')}",
                f"- 策略: {snapshot.get('strategy')}",
                f"- 持仓记录: {snapshot.get('open_trade_count')} / {snapshot.get('max_open_trades')}",
                f"- 证据包: {evidence.get('rows')} 行 / {evidence.get('pairs')} 个交易对 / {evidence.get('lookback_days')} 天",
                f"- 标签: {((evidence.get('label_definition') or {}).get('name'))}",
                f"- 模型: {model_pack.get('model_family') or 'missing'}",
                f"- 自动应用: {sum(1 for item in action_results if item.get('result', {}).get('applied'))} 项",
                "",
                output or "Gemini CLI 没有返回内容。",
                "",
            ]
        ),
        encoding="utf-8",
    )


def run_once() -> int:
    started_at = now_utc()
    write_contract()
    state: dict[str, Any] = {
        "checked_at": started_at,
        "ok": False,
        "gemini_cli": os.getenv("GEMINI_CLI_BIN", "gemini"),
        "report_path": str(REPORT_PATH),
        "automation_enabled": AUTOMATION_ENABLED,
        "request_path": str(REQUEST_PATH),
        "response_path": str(RESPONSE_PATH),
        "action_log_path": str(ACTION_LOG_PATH),
        "autopilot_flow_path": str(AUTOPILOT_FLOW_PATH),
    }
    try:
        snapshot = load_snapshot()
        evidence = load_evidence_pack()
        if not evidence.get("ok"):
            raise RuntimeError(f"3-month evidence pack unavailable: {evidence}")
        model_pack = load_model_pack()
        flow_pack = load_flow_pack()
        prompt = build_prompt(snapshot, evidence, model_pack, flow_pack)
        request = {
            "schema_version": "gemini-autopilot-request/v1",
            "created_at": started_at,
            "automation_enabled": AUTOMATION_ENABLED,
            "snapshot": snapshot,
            "evidence": evidence,
            "model_pack": model_pack,
            "flow_pack": flow_pack,
            "prompt": prompt,
        }
        write_json(REQUEST_PATH, request)
        code, stdout, stderr = run_gemini(prompt)
        action_results: list[dict[str, Any]] = []
        response: dict[str, Any] = {
            "schema_version": "gemini-autopilot/v1",
            "summary": "",
            "actions": [],
            "backlog": [],
            "raw_stdout": stdout[-4000:],
            "stderr": stderr[-1000:] if stderr else "",
        }
        if code == 0:
            response.update(extract_json(stdout))
            action_results = apply_actions(response)
            write_json(BACKLOG_PATH, {"updated_at": now_utc(), "items": response.get("backlog") or []})
        write_json(RESPONSE_PATH, response)
        state.update(
            {
                "ok": code == 0 and all(item.get("ok") for item in action_results),
                "returncode": code,
                "snapshot_checked_at": snapshot.get("checked_at"),
                "open_trade_count": snapshot.get("open_trade_count"),
                "dynamic_pairlist_count": snapshot.get("dynamic_pairlist_count"),
                "evidence_generated_at": evidence.get("generated_at"),
                "evidence_rows": evidence.get("rows"),
                "evidence_pairs": evidence.get("pairs"),
                "model_pack_ok": model_pack.get("ok"),
                "model_family": model_pack.get("model_family"),
                "actions_requested": len(response.get("actions") or []),
                "actions_applied": sum(1 for item in action_results if item.get("result", {}).get("applied")),
                "actions_rejected": sum(1 for item in action_results if not item.get("ok")),
                "summary": response.get("summary"),
                "stderr": stderr[-1000:] if stderr else "",
            }
        )
        report_body = json.dumps(response, ensure_ascii=False, indent=2) if code == 0 else f"Gemini CLI 返回失败，退出码 {code}。\n\n```text\n{stderr[-2000:]}\n```"
        write_report(snapshot, evidence, model_pack, report_body, action_results)
    except Exception as exc:  # noqa: BLE001 - daemon must report and continue.
        state["error"] = f"{type(exc).__name__}: {exc}"[:1000]
    write_json(STATE_PATH, state)
    append_log(state)
    return 0 if state.get("ok") else 1


def main() -> int:
    once = os.getenv("GEMINI_OPTIMIZER_ONCE", "0") == "1"
    interval = int(os.getenv("GEMINI_OPTIMIZER_INTERVAL_SECONDS", "900"))
    while True:
        code = run_once()
        if once:
            return code
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
