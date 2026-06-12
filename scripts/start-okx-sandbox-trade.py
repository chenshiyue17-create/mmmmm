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
REPORT_PATH = ROOT / "output" / "okx-sandbox-start-trade.json"
STATUS_PATH = ROOT / "output" / "auto-watch-status.json"
TAG_PREFIX = "codex_okx_sandbox_start"


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


def read_dynamic_pair() -> str:
    explicit = os.getenv("START_TRADE_PAIR", "").strip()
    if explicit:
        return explicit
    if STATUS_PATH.exists():
        try:
            status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
            pairlist = status.get("dynamic_pairlist") or []
            if pairlist:
                return str(pairlist[0])
        except (OSError, json.JSONDecodeError):
            pass
    return os.getenv("SIMULATION_TEST_PAIR", "KMNO/USDT")


def is_okx_sandbox(show_config: dict[str, Any]) -> bool:
    return (
        str(show_config.get("exchange", "")).lower() == "okx"
        and show_config.get("dry_run") is False
        and os.getenv("OKX_SANDBOX_MODE", "0") == "1"
    )


def wait_for_open_trade(api_url: str, token: str, trade_id: int, timeout: float = 45.0) -> dict[str, Any] | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = request_json("GET", f"{api_url}/api/v1/status", token=token)
        for trade in status:
            if trade.get("trade_id") == trade_id and trade.get("is_open") is True:
                return trade
        time.sleep(1)
    return None


def main() -> int:
    api_url = os.getenv("FT_API_URL", "http://localhost:8080").rstrip("/")
    username = os.getenv("FT_API_USERNAME", "")
    password = os.getenv("FT_API_PASSWORD", "")
    pair = read_dynamic_pair()
    stake = float(os.getenv("START_TRADE_STAKE", os.getenv("SIMULATION_TEST_STAKE", "25")))
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "failed",
        "api_url": api_url,
        "pair": pair,
        "stake": stake,
        "entry": {},
    }
    try:
        if not username or not password:
            raise ApiError("FT_API_USERNAME/FT_API_PASSWORD are required.")
        login = request_json("POST", f"{api_url}/api/v1/token/login", basic=(username, password))
        token = login["access_token"]
        show_config = request_json("GET", f"{api_url}/api/v1/show_config", token=token)
        report["freqtrade"] = {
            "dry_run": show_config.get("dry_run"),
            "runmode": show_config.get("runmode"),
            "exchange": show_config.get("exchange"),
            "strategy": show_config.get("strategy"),
            "force_entry_enable": show_config.get("force_entry_enable"),
            "virtual_mode": "okx_sandbox" if is_okx_sandbox(show_config) else "unsafe",
        }
        if not is_okx_sandbox(show_config):
            raise ApiError("Refusing to start trade outside OKX sandbox mode.")
        if show_config.get("force_entry_enable") is not True:
            raise ApiError("Refusing to start trade because force_entry_enable is not true.")

        open_status = request_json("GET", f"{api_url}/api/v1/status", token=token)
        if open_status:
            report["status"] = "already_open"
            report["open_trades"] = open_status
            return 0

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
        if not trade_id:
            raise ApiError(f"Force entry did not return a trade_id: {entry}")
        opened = wait_for_open_trade(api_url, token, int(trade_id))
        if not opened:
            raise ApiError(f"Trade {trade_id} did not appear in open status.")
        report["status"] = "started"
        report["entry"] = {
            "trade_id": trade_id,
            "pair": entry.get("pair"),
            "exchange": entry.get("exchange"),
            "is_open": entry.get("is_open"),
            "entry_tag": entry.get("enter_tag"),
            "open_rate": entry.get("open_rate"),
            "stake_amount": entry.get("stake_amount"),
        }
        report["open_trade"] = opened
        return 0
    except Exception as exc:  # noqa: BLE001 - this is an operational report.
        report["status"] = "failed"
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        return 1
    finally:
        REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
