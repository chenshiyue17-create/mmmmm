#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "output" / "dryrun-trade-test.json"
TAG_PREFIX = "codex_simulation_test"


class ApiError(RuntimeError):
    pass


def request_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    basic: tuple[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if basic:
        raw = f"{basic[0]}:{basic[1]}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ApiError(f"{method} {url} failed with HTTP {exc.code}: {body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"{method} {url} failed: {exc}") from exc
    return json.loads(body) if body else {}


def wait_for(predicate, timeout: float = 30.0, interval: float = 1.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    return last


def dynamic_default_pair() -> str:
    status_path = ROOT / "output" / "auto-watch-status.json"
    if status_path.exists():
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
            pairlist = status.get("dynamic_pairlist")
            if isinstance(pairlist, list) and pairlist:
                first = str(pairlist[0]).strip()
                if first:
                    return first
        except (OSError, json.JSONDecodeError):
            pass
    return "PEPE/USDT"


def okx_sandbox_mode_enabled(show_config: dict[str, Any]) -> bool:
    exchange = str(show_config.get("exchange", "")).lower()
    return (
        exchange == "okx"
        and show_config.get("dry_run") is False
        and os.getenv("OKX_SANDBOX_MODE", "0") == "1"
    )


def main() -> int:
    api_url = os.getenv("FT_API_URL", "http://localhost:8080").rstrip("/")
    username = os.getenv("FT_API_USERNAME", "")
    password = os.getenv("FT_API_PASSWORD", "")
    pair = os.getenv("SIMULATION_TEST_PAIR") or dynamic_default_pair()
    stake = float(os.getenv("SIMULATION_TEST_STAKE", "25"))

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "failed",
        "api_url": api_url,
        "pair": pair,
        "stake": stake,
        "entry": {},
        "exit": {},
    }

    try:
        if not username or not password:
            raise ApiError("FT_API_USERNAME/FT_API_PASSWORD are required.")
        login = request_json(
            "POST",
            f"{api_url}/api/v1/token/login",
            basic=(username, password),
        )
        token = login["access_token"]
        show_config = request_json("GET", f"{api_url}/api/v1/show_config", token=token)
        report["freqtrade"] = {
            "dry_run": show_config.get("dry_run"),
            "runmode": show_config.get("runmode"),
            "exchange": show_config.get("exchange"),
            "strategy": show_config.get("strategy"),
            "force_entry_enable": show_config.get("force_entry_enable"),
        }
        is_dry_run = show_config.get("dry_run") is True
        is_okx_sandbox = okx_sandbox_mode_enabled(show_config)
        report["freqtrade"]["virtual_mode"] = (
            "freqtrade_dry_run" if is_dry_run else "okx_sandbox" if is_okx_sandbox else "unsafe"
        )
        if not (is_dry_run or is_okx_sandbox):
            raise ApiError(
                "Refusing virtual trade test because Freqtrade is neither dry_run=true "
                "nor OKX sandbox mode with OKX_SANDBOX_MODE=1."
            )
        if show_config.get("force_entry_enable") is not True:
            raise ApiError("Refusing dry-run trade test because force_entry_enable is not true.")

        tag = f"{TAG_PREFIX}_{int(time.time())}"
        entry = request_json(
            "POST",
            f"{api_url}/api/v1/forceenter",
            token=token,
            payload={
                "pair": pair,
                "ordertype": "market",
                "stakeamount": stake,
                "entry_tag": tag,
            },
        )
        trade_id = entry.get("trade_id")
        report["entry"] = {
            "ok": bool(trade_id),
            "trade_id": trade_id,
            "pair": entry.get("pair"),
            "exchange": entry.get("exchange"),
            "is_open": entry.get("is_open"),
            "entry_tag": entry.get("enter_tag"),
            "open_rate": entry.get("open_rate"),
            "stake_amount": entry.get("stake_amount"),
        }
        if not trade_id:
            raise ApiError(f"Force entry did not return a trade_id: {entry}")

        def open_trade() -> dict[str, Any] | None:
            status = request_json("GET", f"{api_url}/api/v1/status", token=token)
            for trade in status:
                if trade.get("trade_id") == trade_id and trade.get("is_open") is True:
                    return trade
            return None

        opened = wait_for(open_trade)
        if not opened:
            raise ApiError(f"Trade {trade_id} did not appear in open status.")

        exit_result = request_json(
            "POST",
            f"{api_url}/api/v1/forceexit",
            token=token,
            payload={"tradeid": str(trade_id), "ordertype": "market"},
        )
        report["exit"]["request"] = exit_result

        def closed_trade() -> dict[str, Any] | None:
            trades = request_json(
                "GET",
                f"{api_url}/api/v1/trades?limit=20&offset=0",
                token=token,
            )
            for trade in trades.get("trades", []):
                if trade.get("trade_id") == trade_id and trade.get("is_open") is False:
                    return trade
            return None

        closed = wait_for(closed_trade, timeout=45.0)
        if not closed:
            raise ApiError(f"Trade {trade_id} did not close within timeout.")

        report["exit"].update(
            {
                "ok": True,
                "trade_id": trade_id,
                "exit_reason": closed.get("exit_reason"),
                "close_rate": closed.get("close_rate"),
                "profit_pct": closed.get("profit_pct"),
                "profit_abs": closed.get("profit_abs"),
                "nr_of_successful_entries": closed.get("nr_of_successful_entries"),
                "nr_of_successful_exits": closed.get("nr_of_successful_exits"),
                "orders": [
                    {
                        "side": order.get("ft_order_side"),
                        "type": order.get("order_type"),
                        "status": order.get("status"),
                    }
                    for order in closed.get("orders", [])
                ],
            }
        )
        report["status"] = "passed"
        return_code = 0
    except Exception as exc:  # noqa: BLE001 - operational report should capture the failure.
        report["status"] = "failed"
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        return_code = 1

    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return return_code


if __name__ == "__main__":
    sys.exit(main())
