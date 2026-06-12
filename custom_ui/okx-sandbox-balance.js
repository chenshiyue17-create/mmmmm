(function () {
  "use strict";
  const balance = {"checked_at": "2026-06-12T12:02:27.098098+00:00", "ok": true, "totalEq": "11733.94774976728", "currencies": [{"ccy": "OKB", "eq": "100", "availBal": "100", "cashBal": "100", "eqUsd": "7249.299999999999", "frozenBal": "0"}, {"ccy": "USDT", "eq": "1895.8012092843117", "availBal": "1895.8012092843117", "cashBal": "1895.8012092843117", "eqUsd": "1893.5641638573563", "frozenBal": "0"}, {"ccy": "ETH", "eq": "1.0610671072", "availBal": "1.0610671072", "cashBal": "1.0610671072", "eqUsd": "1771.759244931488", "frozenBal": "0"}, {"ccy": "ONT", "eq": "4126.794406212", "availBal": "4126.794406212", "cashBal": "4126.794406212", "eqUsd": "196.84809317631237", "frozenBal": "0"}, {"ccy": "CETUS", "eq": "10863.95717576", "availBal": "10863.95717576", "cashBal": "10863.95717576", "eqUsd": "194.5734730178616", "frozenBal": "0"}, {"ccy": "APT", "eq": "154.4358524", "availBal": "154.4358524", "cashBal": "154.4358524", "eqUsd": "101.57246012347998", "frozenBal": "0"}, {"ccy": "IMX", "eq": "687.2077026728", "availBal": "687.2077026728", "cashBal": "687.2077026728", "eqUsd": "97.99581840114128", "frozenBal": "0"}, {"ccy": "MAGIC", "eq": "2113.8142576696", "availBal": "2113.8142576696", "cashBal": "2113.8142576696", "eqUsd": "97.23545585280159", "frozenBal": "0"}, {"ccy": "WCT", "eq": "2047.54095576", "availBal": "2047.54095576", "cashBal": "2047.54095576", "eqUsd": "96.52989327079999", "frozenBal": "0"}, {"ccy": "HYPE", "eq": "1.72891576", "availBal": "1.72891576", "cashBal": "1.72891576", "eqUsd": "34.568979054896", "frozenBal": "0"}, {"ccy": "BTC", "eq": "0.00000000264", "availBal": "0.00000000264", "cashBal": "0.00000000264", "eqUsd": "0.000168081144", "frozenBal": "0"}]};

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
