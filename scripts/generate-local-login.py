#!/usr/bin/env python3
"""Generate local UI auto-login settings from .env."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
OUTPUT = ROOT / "custom_ui/local-login.json"


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    env = parse_env(ENV_FILE)
    enabled = env.get("AUTO_LOGIN_ENABLED", "1") not in {"0", "false", "False", "no", "NO"}
    port = env.get("FREQTRADE_UI_PORT", "8080")
    payload = {
        "enabled": enabled,
        "botName": env.get("FT_BOT_NAME", "freqtrade"),
        "url": env.get("FT_API_URL", f"http://localhost:{port}"),
        "username": env.get("FT_API_USERNAME", "freqtrade"),
        "password": env.get("FT_API_PASSWORD", ""),
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    OUTPUT.chmod(0o600)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
