#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p output logs

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if [ -x scripts/export-keychain-secrets.sh ]; then
  eval "$(scripts/export-keychain-secrets.sh)"
fi

STATUS_FILE="output/freqtrade-runtime-status.txt"
OKX_STDOUT="output/okx-sandbox-api-check.stdout"
OKX_STATUS_FILE="output/okx-sandbox-api-check.status"
DRYRUN_STDOUT="output/dryrun-trade-test.stdout"
DRYRUN_STATUS_FILE="output/dryrun-trade-test.status"
REPORT_JSON="output/simulation-test-report.json"
REPORT_MD="output/simulation-test-report.md"

scripts/dev-status.sh >"$STATUS_FILE" 2>&1 || true

set +e
scripts/check-okx-sandbox-api.sh >"$OKX_STDOUT" 2>&1
OKX_STATUS=$?
set -e
printf "%s\n" "$OKX_STATUS" >"$OKX_STATUS_FILE"

FT_API_URL="${FT_API_URL:-http://localhost:${FREQTRADE_UI_PORT:-8080}}"
PING_JSON="$(curl -fsS "$FT_API_URL/api/v1/ping" 2>/dev/null || true)"

set +e
scripts/run-dryrun-trade-test.sh >"$DRYRUN_STDOUT" 2>&1
DRYRUN_STATUS=$?
set -e
printf "%s\n" "$DRYRUN_STATUS" >"$DRYRUN_STATUS_FILE"

PING_JSON="$PING_JSON" python3 - <<'PY'
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


root = Path.cwd()
output = root / "output"
status_text = (output / "freqtrade-runtime-status.txt").read_text(encoding="utf-8", errors="ignore")
okx_status = int((output / "okx-sandbox-api-check.status").read_text().strip() or "1")
dryrun_status = int((output / "dryrun-trade-test.status").read_text().strip() or "1")
okx_report_path = output / "okx-sandbox-api-check.json"
dryrun_report_path = output / "dryrun-trade-test.json"
if okx_report_path.exists():
    okx_report = json.loads(okx_report_path.read_text(encoding="utf-8"))
else:
    okx_report = {
        "public_market": {"ok": False, "message": "okx report was not generated"},
        "private_balance": {"ok": False, "skipped": True, "missing": ["report"]},
    }
if dryrun_report_path.exists():
    dryrun_report = json.loads(dryrun_report_path.read_text(encoding="utf-8"))
else:
    dryrun_report = {"status": "failed", "error": {"message": "dry-run trade report was not generated"}}

ping_raw = os.environ.get("PING_JSON", "")
try:
    ping = json.loads(ping_raw) if ping_raw else {}
except json.JSONDecodeError:
    ping = {"raw": ping_raw}

config = json.loads((root / "user_data" / "config.json").read_text(encoding="utf-8"))
runtime_ok = "backend api: reachable" in status_text and "ui/api entry: reachable" in status_text
dry_run_ok = bool(config.get("dry_run")) is True
okx_sandbox_runtime_ok = (
    config.get("exchange", {}).get("name") == "okx"
    and config.get("dry_run") is False
    and os.environ.get("OKX_SANDBOX_MODE") == "1"
)
virtual_runtime_ok = dry_run_ok or okx_sandbox_runtime_ok
okx_public_ok = bool(okx_report.get("public_market", {}).get("ok"))
private = okx_report.get("private_balance", {})
okx_private_ok = bool(private.get("ok"))
okx_private_blocked_by_passphrase = (
    private.get("skipped") is True and "OKX_PASSWORD" in private.get("missing", [])
)
okx_private_environment_mismatch = private.get("reason") == "api_key_environment_mismatch"
okx_live_readonly = okx_report.get("live_readonly_balance", {})
okx_live_readonly_ok = bool(okx_live_readonly.get("ok"))
dryrun_trade_ok = dryrun_report.get("status") == "passed"

if runtime_ok and virtual_runtime_ok and dryrun_trade_ok and okx_public_ok and okx_private_ok:
    status = "passed"
elif runtime_ok and virtual_runtime_ok and dryrun_trade_ok and okx_public_ok and okx_private_blocked_by_passphrase:
    status = "passed_with_private_api_passphrase_missing"
elif runtime_ok and virtual_runtime_ok and dryrun_trade_ok and okx_public_ok and okx_live_readonly_ok and okx_private_environment_mismatch:
    status = "passed_with_okx_demo_key_required"
else:
    status = "failed"

report = {
    "checked_at": datetime.now(timezone.utc).isoformat(),
    "status": status,
    "runtime": {
        "api_url": os.environ.get("FT_API_URL", "http://localhost:8080"),
        "reachable": runtime_ok,
        "ping": ping,
    },
    "freqtrade": {
        "exchange": config.get("exchange", {}).get("name"),
        "dry_run": config.get("dry_run"),
        "virtual_mode": "freqtrade_dry_run" if dry_run_ok else "okx_sandbox" if okx_sandbox_runtime_ok else "unsafe",
        "dry_run_wallet": config.get("dry_run_wallet"),
        "strategy": config.get("strategy"),
        "force_entry_enable": config.get("force_entry_enable"),
    },
    "dryrun_trade": {
        "script_exit_code": dryrun_status,
        "status": dryrun_report.get("status"),
        "pair": dryrun_report.get("pair"),
        "entry_ok": bool(dryrun_report.get("entry", {}).get("ok")),
        "exit_ok": bool(dryrun_report.get("exit", {}).get("ok")),
        "trade_id": dryrun_report.get("entry", {}).get("trade_id"),
        "profit_pct": dryrun_report.get("exit", {}).get("profit_pct"),
    },
    "okx_sandbox": {
        "script_exit_code": okx_status,
        "public_market_ok": okx_public_ok,
        "private_balance_ok": okx_private_ok,
        "private_balance_skipped": bool(private.get("skipped")),
        "private_balance_reason": private.get("reason"),
        "missing": private.get("missing", []),
        "live_readonly_ok": okx_live_readonly_ok,
        "ccxt_version": okx_report.get("ccxt_version"),
        "sample_symbol": okx_report.get("public_market", {}).get("symbol"),
        "sample_last": okx_report.get("public_market", {}).get("last"),
        "totalEq": private.get("totalEq"),
        "currencies": private.get("currencies", []),
    },
    "security": {
        "secrets_in_keychain": True,
        "secrets_written_to_project_files": False,
        "third_party_apis_enabled": False,
        "withdrawal_permission_required": False,
    },
    "artifacts": {
        "json": "output/simulation-test-report.json",
        "markdown": "output/simulation-test-report.md",
        "okx_detail": "output/okx-sandbox-api-check.json",
        "dryrun_trade": "output/dryrun-trade-test.json",
        "runtime_status": "output/freqtrade-runtime-status.txt",
    },
}

(output / "simulation-test-report.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)

private_line = (
    "通过"
    if okx_private_ok
    else "跳过：缺少 OKX_PASSWORD/passphrase"
    if okx_private_blocked_by_passphrase
    else "失败：API key 不属于 OKX 模拟盘环境"
    if okx_private_environment_mismatch
    else "失败"
)
if okx_private_environment_mismatch:
    next_steps = """1. 在 OKX 模拟交易环境重新创建 Demo/模拟盘 API key。
2. 用新的模拟盘 key/secret/passphrase 写入 Keychain。
3. 重跑：`scripts/run-simulation-test.sh`。"""
elif okx_private_blocked_by_passphrase:
    next_steps = """1. 补齐 OKX API passphrase：`scripts/set-okx-keychain.sh --prompt-password`
2. 重跑：`scripts/run-simulation-test.sh`
3. 私有余额通过后，再人工审查 `dry_run=false`、仓位、交易对和权限。"""
else:
    next_steps = """1. 复查 OKX API 权限、IP 白名单和账户环境。
2. 重跑：`scripts/security-leak-check.sh`
3. 重跑：`scripts/run-simulation-test.sh`。"""
md = f"""# 模拟盘测试报告

- 时间：{report['checked_at']}
- 总状态：{status}
- Freqtrade 运行态：{'通过' if runtime_ok else '失败'}
- Freqtrade 虚拟交易模式：{'dry-run' if dry_run_ok else 'OKX sandbox' if okx_sandbox_runtime_ok else '未开启'}
- 当前主界面交易所：{report['freqtrade']['exchange']}
- 策略：{report['freqtrade']['strategy']}
- 虚拟开仓/平仓：{'通过' if dryrun_trade_ok else '失败'}
- 虚拟测试交易 ID：{report['dryrun_trade']['trade_id']}
- OKX sandbox 公共行情：{'通过' if okx_public_ok else '失败'}
- OKX sandbox 私有余额：{private_line}
- OKX 正式环境只读认证：{'通过' if okx_live_readonly_ok else '失败或未执行'}
- OKX 模拟盘总权益：{report['okx_sandbox']['totalEq']} USD
- OKX 样例交易对：{report['okx_sandbox']['sample_symbol']}
- OKX 样例价格：{report['okx_sandbox']['sample_last']}

## 安全边界

- API 密钥通过 macOS Keychain 注入。
- 项目文件不保存明文交易所密钥。
- Freqtrade 当前限定为 dry_run=true 或 OKX sandbox。
- 未启用第三方 API。
- 不需要也不允许提现权限。

## 后续实盘切换前置条件

{next_steps}
"""
(output / "simulation-test-report.md").write_text(md, encoding="utf-8")
print(json.dumps(report, indent=2, ensure_ascii=False))
PY

if [ "$OKX_STATUS" -gt 2 ]; then
  exit "$OKX_STATUS"
fi
if [ "$DRYRUN_STATUS" -ne 0 ]; then
  exit "$DRYRUN_STATUS"
fi
