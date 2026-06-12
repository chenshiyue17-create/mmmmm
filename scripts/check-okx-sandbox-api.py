#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import base64
import hashlib
import hmac
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ccxt


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "output" / "okx-sandbox-api-check.json"
UI_BALANCE_PATH = ROOT / "custom_ui" / "okx-sandbox-balance.js"


@dataclass(frozen=True)
class SecretState:
    api_key: bool
    secret_key: bool
    passphrase: bool

    @property
    def complete(self) -> bool:
        return self.api_key and self.secret_key and self.passphrase


def mask(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}***{value[-4:]}"


def build_exchange() -> ccxt.okx:
    exchange = ccxt.okx(
        {
            "apiKey": os.getenv("OKX_KEY", ""),
            "secret": os.getenv("OKX_SECRET", ""),
            "password": os.getenv("OKX_PASSWORD", ""),
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        }
    )
    exchange.set_sandbox_mode(True)
    return exchange


def public_market_check(exchange: ccxt.okx) -> dict[str, Any]:
    ticker = exchange.fetch_ticker("PEPE/USDT")
    return {
        "ok": True,
        "symbol": ticker.get("symbol"),
        "last": ticker.get("last"),
        "datetime": ticker.get("datetime"),
    }


def private_balance_check(exchange: ccxt.okx, secrets: SecretState) -> dict[str, Any]:
    if not secrets.complete:
        missing = []
        if not secrets.api_key:
            missing.append("OKX_KEY")
        if not secrets.secret_key:
            missing.append("OKX_SECRET")
        if not secrets.passphrase:
            missing.append("OKX_PASSWORD")
        return {
            "ok": False,
            "skipped": True,
            "reason": "missing_private_api_credentials",
            "missing": missing,
        }

    return okx_signed_balance(secrets, simulated=True)


def okx_signed_balance(secrets: SecretState, *, simulated: bool) -> dict[str, Any]:
    if not secrets.complete:
        return {
            "ok": False,
            "skipped": True,
            "reason": "missing_private_api_credentials",
        }

    path = "/api/v5/account/balance"
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    payload = f"{timestamp}GET{path}"
    signature = base64.b64encode(
        hmac.new(os.environ["OKX_SECRET"].encode(), payload.encode(), hashlib.sha256).digest()
    ).decode()
    headers = {
        "OK-ACCESS-KEY": os.environ["OKX_KEY"],
        "OK-ACCESS-SIGN": signature,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": os.environ["OKX_PASSWORD"],
        "Accept": "application/json",
        "User-Agent": "freqtrade-deploy/1.0",
    }
    if simulated:
        headers["x-simulated-trading"] = "1"

    request = urllib.request.Request("https://www.okx.com" + path, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.status
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - operational report should capture failure class.
        return {
            "ok": False,
            "skipped": False,
            "error_type": type(exc).__name__,
            "message": str(exc)[:500],
        }

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "skipped": False,
            "http_status": status,
            "error_type": "InvalidJsonResponse",
            "message": body[:300],
        }

    code = data.get("code")
    msg = data.get("msg", "")
    ok = status == 200 and code == "0"
    reason = None
    if code == "50101" and "environment" in msg.lower():
        reason = "api_key_environment_mismatch"
    elif not ok:
        reason = "okx_auth_failed"

    account = (data.get("data") or [{}])[0] if isinstance(data.get("data"), list) else {}
    details = account.get("details") or []
    currencies = []
    for item in details[:20]:
        currencies.append(
            {
                "ccy": item.get("ccy"),
                "eq": item.get("eq"),
                "availBal": item.get("availBal"),
                "cashBal": item.get("cashBal"),
                "eqUsd": item.get("eqUsd"),
                "frozenBal": item.get("frozenBal"),
            }
        )

    return {
        "ok": ok,
        "skipped": False,
        "http_status": status,
        "code": code,
        "reason": reason,
        "data_len": len(data.get("data") or []),
        "totalEq": account.get("totalEq"),
        "details_count": len(details),
        "currencies": currencies,
    }


def main() -> int:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    secrets = SecretState(
        api_key=bool(os.getenv("OKX_KEY")),
        secret_key=bool(os.getenv("OKX_SECRET")),
        passphrase=bool(os.getenv("OKX_PASSWORD")),
    )
    exchange = build_exchange()
    report: dict[str, Any] = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "exchange": "okx",
        "mode": "sandbox",
        "dry_run_safe": True,
        "ccxt_version": ccxt.__version__,
        "credentials": {
            "api_key": mask(os.getenv("OKX_KEY")),
            "secret_key": "***" if secrets.secret_key else "",
            "passphrase_present": secrets.passphrase,
        },
    }

    try:
        report["public_market"] = public_market_check(exchange)
    except Exception as exc:  # noqa: BLE001 - keep report useful for operations.
        report["public_market"] = {
            "ok": False,
            "error_type": type(exc).__name__,
            "message": str(exc)[:500],
        }

    report["private_balance"] = private_balance_check(exchange, secrets)
    report["live_readonly_balance"] = okx_signed_balance(secrets, simulated=False)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ui_payload = {
        "checked_at": report["checked_at"],
        "ok": bool(report["private_balance"].get("ok")),
        "totalEq": report["private_balance"].get("totalEq"),
        "currencies": report["private_balance"].get("currencies", []),
    }
    if UI_BALANCE_PATH.parent.exists():
        UI_BALANCE_PATH.write_text(
            "window.FT_OKX_SANDBOX_BALANCE = "
            + json.dumps(ui_payload, ensure_ascii=False)
            + ";\n",
            encoding="utf-8",
        )
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if not report["public_market"].get("ok"):
        return 1
    if report["private_balance"].get("skipped"):
        return 2
    return 0 if report["private_balance"].get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
