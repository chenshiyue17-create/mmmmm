#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "output" / "security-leak-check.json"
SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
}
SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".sqlite",
    ".db",
    ".pyc",
}


@dataclass(frozen=True)
class Secret:
    name: str
    value: str

    @property
    def safe_to_scan(self) -> bool:
        return len(self.value) >= 6


def load_secrets() -> list[Secret]:
    names = [
        "OKX_KEY",
        "OKX_SECRET",
        "OKX_PASSWORD",
        "BINANCE_KEY",
        "BINANCE_SECRET",
    ]
    secrets = [Secret(name, os.getenv(name, "")) for name in names if os.getenv(name, "")]
    extra = os.getenv("EXTRA_SECRET", "")
    if extra:
        secrets.append(Secret("EXTRA_SECRET", extra))
    return [secret for secret in secrets if secret.safe_to_scan]


def should_scan(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in SKIP_DIRS for part in rel.parts):
        return False
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    if path.name.startswith("._"):
        return False
    return path.is_file()


def scan_file(path: Path, secrets: list[Secret]) -> list[dict[str, str]]:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    findings: list[dict[str, str]] = []
    for secret in secrets:
        if secret.value in content:
            findings.append(
                {
                    "file": str(path.relative_to(ROOT)),
                    "secret_name": secret.name,
                    "severity": "high",
                }
            )
    return findings


def main() -> int:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    secrets = load_secrets()
    findings: list[dict[str, str]] = []
    scanned = 0
    for path in ROOT.rglob("*"):
        if not should_scan(path):
            continue
        scanned += 1
        findings.extend(scan_file(path, secrets))

    report = {
        "status": "passed" if not findings else "failed",
        "scanned_files": scanned,
        "secret_names_checked": [secret.name for secret in secrets],
        "findings": findings,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main())
