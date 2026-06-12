#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "output" / "qlib" / "okx_1h" / "qlib_fusion_report.json"
MANIFEST_PATH = ROOT / "output" / "qlib" / "okx_1h" / "manifest.json"
CSV_DIR = ROOT / "output" / "qlib" / "okx_1h" / "csv"
CONFIG_PATH = ROOT / "output" / "qlib" / "okx_1h" / "qlib_okx_lgbm_config.yaml"
QLIB_VENDOR = ROOT / "vendor" / "qlib"


def fail(message: str) -> int:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False, indent=2))
    return 1


def main() -> int:
    if not QLIB_VENDOR.exists():
        return fail("vendor/qlib is missing. Run: git clone https://github.com/microsoft/qlib.git vendor/qlib")
    if not (QLIB_VENDOR / "qlib").is_dir():
        return fail("vendor/qlib does not contain the qlib python package")
    if not REPORT_PATH.exists():
        return fail("Qlib fusion report is missing. Run scripts/prepare-qlib-data.sh first.")
    if not MANIFEST_PATH.exists():
        return fail("Qlib manifest is missing. Run scripts/prepare-qlib-data.sh first.")
    if not CONFIG_PATH.exists():
        return fail("Qlib workflow config is missing. Run scripts/prepare-qlib-data.sh first.")

    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    csv_files = sorted(path for path in CSV_DIR.glob("*.csv") if not path.name.startswith("._"))
    if report.get("rows", 0) < 1000:
        return fail("Qlib fusion report has too few rows")
    if report.get("symbols", 0) < 3:
        return fail("Qlib fusion report has too few symbols")
    if len(csv_files) != report.get("symbols"):
        return fail(f"CSV file count {len(csv_files)} does not match symbols {report.get('symbols')}")

    sample = pd.read_csv(csv_files[0])
    required_columns = {"date", "symbol", "open", "high", "low", "close", "volume", "return_6", "label_return_5_open_pct"}
    missing = sorted(required_columns - set(sample.columns))
    if missing:
        return fail(f"Qlib CSV sample is missing columns: {missing}")

    config_text = CONFIG_PATH.read_text(encoding="utf-8")
    for needle in ["LGBModel", "TopkDropoutStrategy", "DataHandlerLP", "$label_return_5_open_pct", "$return_6"]:
        if needle not in config_text:
            return fail(f"Qlib config missing {needle}")

    qlib_available = importlib.util.find_spec("qlib") is not None
    result = {
        "ok": True,
        "vendor_qlib": str(QLIB_VENDOR),
        "qlib_import_available": qlib_available,
        "rows": report.get("rows"),
        "symbols": report.get("symbols"),
        "csv_files": len(csv_files),
        "segments": manifest.get("segments"),
        "config_path": str(CONFIG_PATH),
        "dump_command": manifest.get("dump_command"),
        "qrun_command": manifest.get("qrun_command"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
