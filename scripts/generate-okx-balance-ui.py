#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "output" / "okx-sandbox-api-check.json"
TARGET = ROOT / "custom_ui" / "okx-sandbox-balance.js"


def main() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    balance = report.get("private_balance", {})
    payload = {
        "checked_at": report.get("checked_at"),
        "ok": bool(balance.get("ok")),
        "totalEq": balance.get("totalEq"),
        "currencies": balance.get("currencies", []),
    }
    TARGET.write_text(
        """(function () {
  "use strict";
  const balance = __PAYLOAD__;

  function formatNumber(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return value || "-";
    return new Intl.NumberFormat("zh-CN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(number);
  }

  function render() {
    if (location.pathname !== "/balance") return;
    if (!balance.ok || document.querySelector("[data-okx-sandbox-balance='true']")) return;
    const main = document.querySelector("main");
    if (!main) return;
    const rows = (balance.currencies || []).slice(0, 8).map((item) => `
      <tr>
        <td>${item.ccy || "-"}</td>
        <td style="text-align:right;padding:8px;">${formatNumber(item.eq)}</td>
        <td style="text-align:right;padding:8px;">${formatNumber(item.availBal)}</td>
        <td style="text-align:right;padding:8px;">${formatNumber(item.eqUsd)}</td>
      </tr>
    `).join("");
    const card = document.createElement("section");
    card.dataset.okxSandboxBalance = "true";
    card.style.cssText = "margin:16px 0;padding:16px;border:1px solid rgba(34,197,94,.45);border-radius:8px;background:rgba(5,46,22,.36);color:inherit;";
    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap;">
        <div>
          <h2 style="margin:0 0 8px;font-size:18px;">OKX 模拟盘余额</h2>
          <div style="font-size:28px;font-weight:700;line-height:1.2;">${formatNumber(balance.totalEq)} USD</div>
          <p style="margin:8px 0 0;color:#a7f3d0;">这是 OKX 模拟盘账户权益；下方原生表格是 Freqtrade 本地 dry-run 钱包。</p>
        </div>
        <div style="font-size:13px;color:#bbf7d0;">来源：OKX sandbox 私有余额接口</div>
      </div>
      <table style="width:100%;margin-top:16px;border-collapse:collapse;font-size:14px;">
        <thead>
          <tr>
            <th style="text-align:left;padding:8px;border-bottom:1px solid rgba(187,247,208,.25);">币种</th>
            <th style="text-align:right;padding:8px;border-bottom:1px solid rgba(187,247,208,.25);">权益</th>
            <th style="text-align:right;padding:8px;border-bottom:1px solid rgba(187,247,208,.25);">可用</th>
            <th style="text-align:right;padding:8px;border-bottom:1px solid rgba(187,247,208,.25);">折合 USD</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
    main.prepend(card);
  }

  document.addEventListener("DOMContentLoaded", render, { once: true });
  window.setInterval(render, 1000);
})();
""".replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False)),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
