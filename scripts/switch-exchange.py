#!/usr/bin/env python3
"""Switch Freqtrade between supported exchange templates."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "user_data/config.json"
TEMPLATES = {
    "okx": ROOT / "config_templates/config.okx.json",
    "binance": ROOT / "config_templates/config.binance.json",
}


def clean_template_exchange(exchange: dict) -> dict:
    cleaned = dict(exchange)
    for field in ("key", "secret", "password"):
        if field in cleaned:
            cleaned[field] = ""
    cleaned["enable_ws"] = False
    return cleaned


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in TEMPLATES:
        names = ", ".join(sorted(TEMPLATES))
        print(f"Usage: scripts/switch-exchange.py <{names}>", file=sys.stderr)
        return 2

    name = argv[1]
    config = json.loads(CONFIG.read_text())
    template = json.loads(TEMPLATES[name].read_text())
    config["exchange"] = clean_template_exchange(template["exchange"])
    config["bot_name"] = f"freqtrade-{name}-dryrun"
    CONFIG.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    print(f"Switched exchange to {name}. Keep dry_run=true and restart with scripts/start-dev.sh.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
