#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "gemini-optimizer.py"
OVERLAY_PATH = ROOT / "user_data" / "datugou_flow.autopilot.json"


def load_optimizer():
    spec = importlib.util.spec_from_file_location("gemini_optimizer", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load gemini-optimizer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    os.environ["GEMINI_AUTOMATION_ENABLED"] = "1"
    optimizer = load_optimizer()
    action = {
        "type": "update_strategy_flow",
        "confidence": 0.91,
        "reason": "smoke test bounded autopilot update",
        "parameters": {
            "min_volume_ratio": 1.7,
            "min_momentum_pct": 2.2,
        },
    }
    response = {
        "schema_version": "gemini-autopilot/v1",
        "summary": "smoke",
        "actions": [action],
        "backlog": [],
    }
    result = optimizer.apply_strategy_flow(action, response)
    payload = json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))
    assert result["applied"] is True or payload["parameters"]["min_volume_ratio"] == 1.7
    assert payload["schema_version"] == "datugou-autopilot/v1"
    assert payload["parameters"]["min_volume_ratio"] == 1.7
    assert payload["parameters"]["min_momentum_pct"] == 2.2
    print(json.dumps({"ok": True, "overlay": str(OVERLAY_PATH), "parameters": payload["parameters"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
