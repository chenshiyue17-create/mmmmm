#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import urllib.request
from base64 import b64encode
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "user_data" / "config.json"
WATCH_STATUS_PATH = ROOT / "output" / "auto-watch-status.json"
WATCH_EVENTS_PATH = ROOT / "output" / "auto-watch-events.jsonl"
PAIRS_PATH = ROOT / "output" / "ml_raw_3mo" / "relevant-pairs.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def api_whitelist() -> list[str]:
    load_env_file()
    base_url = os.getenv("FT_API_URL", "http://127.0.0.1:8080").rstrip("/")
    username = os.getenv("FT_API_USERNAME", "freqtrade")
    password = os.getenv("FT_API_PASSWORD", "")
    request = urllib.request.Request(f"{base_url}/api/v1/whitelist")
    token = b64encode(f"{username}:{password}".encode()).decode()
    request.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return [pair for pair in payload.get("whitelist", []) if isinstance(pair, str)]
    except Exception:
        return []


def event_pair_history(max_lines: int = 3000) -> list[str]:
    if not WATCH_EVENTS_PATH.exists():
        return []
    lines = WATCH_EVENTS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()[-max_lines:]
    pairs: list[str] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        for pair in payload.get("dynamic_pairlist") or []:
            if isinstance(pair, str):
                pairs.append(pair)
        for trade in payload.get("open_trades") or []:
            pair = trade.get("pair") if isinstance(trade, dict) else None
            if isinstance(pair, str):
                pairs.append(pair)
    return pairs


def concrete_pair(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9]+/[A-Z0-9]+", value))


def collect_pairs() -> list[str]:
    config = load_json(CONFIG_PATH)
    watch = load_json(WATCH_STATUS_PATH)
    pairs: set[str] = set()

    for pair in api_whitelist():
        if concrete_pair(pair):
            pairs.add(pair)
    for pair in event_pair_history():
        if concrete_pair(pair):
            pairs.add(pair)
    for pair in watch.get("dynamic_pairlist") or []:
        if concrete_pair(pair):
            pairs.add(pair)
    for trade in watch.get("open_trades") or []:
        pair = trade.get("pair")
        if isinstance(pair, str) and concrete_pair(pair):
            pairs.add(pair)
    for pair in (config.get("exchange") or {}).get("pair_whitelist") or []:
        if concrete_pair(pair):
            pairs.add(pair)

    blacklist = set((config.get("exchange") or {}).get("pair_blacklist") or [])
    pairs = {pair for pair in pairs if pair not in blacklist}
    return sorted(pairs)


def main() -> int:
    pairs = collect_pairs()
    PAIRS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAIRS_PATH.write_text(json.dumps(pairs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pairs": pairs, "pairs_file": str(PAIRS_PATH)}, ensure_ascii=False, indent=2))
    return 0 if pairs else 1


if __name__ == "__main__":
    raise SystemExit(main())
