#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESEARCH_FLOW = Path("/Users/cc/Documents/量化/strategies/datugou_profit_flow.yaml")
OUTPUT_PATH = ROOT / "user_data" / "datugou_flow.json"


def _condition_value(flow: dict[str, Any], left: str, right: str) -> float:
    for condition in flow.get("entry", {}).get("conditions", []):
        if condition.get("left") == left and condition.get("right") == right:
            return float(condition["right_value"] if "right_value" in condition else condition["right"])
    raise ValueError(f"Missing entry condition {left} -> {right}")


def convert(flow_path: Path) -> dict[str, Any]:
    import yaml

    raw = yaml.safe_load(flow_path.read_text(encoding="utf-8"))
    flow = raw.get("strategy_flow")
    if not isinstance(flow, dict):
        raise ValueError("strategy_flow object is required")
    indicators = flow.get("indicators", {})
    rules = flow.get("position_rules", {})
    params = {
        "source": str(flow_path),
        "schema_version": flow.get("schema_version"),
        "name": flow.get("name"),
        "version": str(flow.get("version")),
        "min_rows": int(flow.get("min_rows", 80)),
        "breakout_lookback": int(indicators.get("breakout_lookback", 24)),
        "volume_window": int(indicators.get("volume_window", 24)),
        "momentum_window": int(indicators.get("momentum_window", 6)),
        "min_volume_ratio": _condition_value(flow, "volume_ratio", 1.6),
        "min_momentum_pct": _condition_value(flow, "momentum_pct", 2.5),
        "stop_loss_pct": float(rules.get("stop_loss_pct", 7.0)),
        "take_profit_pct": float(rules.get("take_profit_pct", 30.0)),
        "trailing_stop_pct": float(rules.get("trailing_stop_pct", 10.0)),
    }
    if params["schema_version"] != "strategy-flow/v1":
        raise ValueError("Only strategy-flow/v1 is supported")
    if params["breakout_lookback"] <= 1 or params["volume_window"] <= 1:
        raise ValueError("breakout_lookback and volume_window must be greater than 1")
    if params["momentum_window"] <= 0:
        raise ValueError("momentum_window must be positive")
    if not 0 < params["stop_loss_pct"] < params["take_profit_pct"]:
        raise ValueError("stop_loss_pct must be positive and below take_profit_pct")
    return params


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Import research datugou strategy flow into Freqtrade.")
    parser.add_argument("--flow", default=str(DEFAULT_RESEARCH_FLOW), help="Path to strategy-flow YAML")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output JSON consumed by Freqtrade")
    args = parser.parse_args()

    flow_path = Path(args.flow)
    if not flow_path.exists():
        output = Path(args.output)
        if output.exists():
            json.loads(output.read_text(encoding="utf-8"))
            print(f"Research strategy flow not found, reusing existing {output}")
            return 0
        raise FileNotFoundError(f"Research strategy flow not found and no existing output is available: {flow_path}")
    params = convert(flow_path)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(params, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Imported {flow_path} -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
