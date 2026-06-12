#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "output" / "auto-watch-status.json"
EVENTS_PATH = ROOT / "output" / "auto-watch-events.jsonl"
LOG_PATH = ROOT / "logs" / "auto-watch.log"


def load_env_file() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def api_get(path: str, username: str, password: str, base_url: str) -> dict[str, Any] | list[Any]:
    request = urllib.request.Request(f"{base_url.rstrip('/')}/api/v1/{path.lstrip('/')}")
    token = b64encode(f"{username}:{password}".encode()).decode()
    request.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def write_line(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def snapshot() -> dict[str, Any]:
    load_env_file()
    base_url = os.getenv("FT_API_URL", "http://127.0.0.1:8080")
    username = os.getenv("FT_API_USERNAME", "freqtrade")
    password = os.getenv("FT_API_PASSWORD", "")
    checked_at = datetime.now(timezone.utc).isoformat()
    result: dict[str, Any] = {
        "checked_at": checked_at,
        "ok": False,
        "engine": "freqtrade",
        "mode": "okx_sandbox",
    }
    try:
        config = api_get("show_config", username, password, base_url)
        count = api_get("count", username, password, base_url)
        status = api_get("status", username, password, base_url)
        profit = api_get("profit", username, password, base_url)
        whitelist = api_get("whitelist", username, password, base_url)
        result.update(
            {
                "ok": True,
                "strategy": config.get("strategy") if isinstance(config, dict) else None,
                "exchange": config.get("exchange") if isinstance(config, dict) else None,
                "timeframe": config.get("timeframe") if isinstance(config, dict) else None,
                "runmode": config.get("runmode") if isinstance(config, dict) else None,
                "dry_run": config.get("dry_run") if isinstance(config, dict) else None,
                "stake_amount": config.get("stake_amount") if isinstance(config, dict) else None,
                "open_trade_count": count.get("current") if isinstance(count, dict) else None,
                "max_open_trades": count.get("max") if isinstance(count, dict) else None,
                "open_trades": status if isinstance(status, list) else [],
                "trade_count": profit.get("trade_count") if isinstance(profit, dict) else None,
                "profit_all_percent": profit.get("profit_all_percent") if isinstance(profit, dict) else None,
                "dynamic_pairlist": whitelist.get("whitelist", []) if isinstance(whitelist, dict) else [],
                "pairlist_methods": whitelist.get("method", []) if isinstance(whitelist, dict) else [],
            }
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"[:300]
    return result


def main() -> int:
    interval = int(os.getenv("AUTO_WATCH_INTERVAL_SECONDS", "30"))
    once = os.getenv("AUTO_WATCH_ONCE", "0") == "1"
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    while True:
        current = snapshot()
        OUTPUT_PATH.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        write_line(EVENTS_PATH, current)
        write_line(LOG_PATH, current)
        if once:
            return 0 if current.get("ok") else 1
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
