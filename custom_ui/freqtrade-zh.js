(function () {
  "use strict";

  document.documentElement.lang = "zh-CN";
  document.title = "Freqtrade 量化交易面板";

  const exactText = new Map([
    ["FreqtradeUI", "Freqtrade 控制台"],
    ["Welcome to the FreqtradeUI", "欢迎使用 Freqtrade 控制台"],
    ["This page allows you to control your trading bot.", "在这里查看和控制你的量化交易机器人。"],
    ["If you need any help, please refer to the", "如需帮助，请查看"],
    ["Freqtrade Documentation", "Freqtrade 文档"],
    ["Have fun - wishes you the Freqtrade team", "祝使用顺利 - Freqtrade 团队"],
    ["Freqtrade bot Login", "Freqtrade 机器人登录"],
    ["Bot Name", "机器人名称"],
    ["API Url", "API 地址"],
    ["Username", "用户名"],
    ["Password", "密码"],
    ["Reset", "重置"],
    ["Submit", "登录"],
    ["Trades", "交易"],
    ["History", "历史"],
    ["Pairlist", "交易对"],
    ["Balance", "余额"],
    ["Dashboard", "仪表盘"],
    ["Profit over time", "收益趋势"],
    ["Days", "按日"],
    ["Weeks", "按周"],
    ["Months", "按月"],
    ["Abs $", "金额"],
    ["Rel %", "百分比"],
    ["Bot comparison", "机器人对比"],
    ["Bot", "机器人"],
    ["All", "全部"],
    ["Dry", "模拟"],
    ["(dry)", "(模拟)"],
    ["(live)", "(实盘)"],
    ["Summary", "汇总"],
    ["All Trades", "全部交易"],
    ["Open Profit", "持仓收益"],
    ["Closed Profit", "已结收益"],
    ["W/L", "胜/负"],
    ["Open Trades", "当前持仓"],
    ["Closed Trades", "已关闭交易"],
    ["No Trades to show.", "暂无交易。"],
    ["Cumulative Profit", "累计收益"],
    ["Wallet History", "钱包历史"],
    ["No historic wallet data available.", "暂无历史钱包数据。"],
    ["You may need to update your freqtrade version to have historic wallet balance data available.", "如需历史钱包余额数据，可能需要更新 Freqtrade 版本。"],
    ["Profit Distribution", "收益分布"],
    ["Bins", "分组数"],
    ["Trades Log", "交易日志"],
    ["Bot Balance", "机器人余额"],
    ["Simulated balances", "模拟余额"],
    ["Currency", "币种"],
    ["Available", "可用"],
    ["in USDT", "折合 USDT"],
    ["Total", "合计"],
    ["Whitelist Methods", "白名单方法"],
    ["Whitelist", "白名单"],
    ["Blacklist", "黑名单"],
    ["Pair", "交易对"],
    ["Amount", "数量"],
    ["Stake amount", "投入金额"],
    ["Total stake amount", "总投入金额"],
    ["Open rate", "开仓价格"],
    ["Current rate", "当前价格"],
    ["Current profit %", "当前收益 %"],
    ["Open date", "开仓时间"],
    ["Close rate", "平仓价格"],
    ["Profit %", "收益 %"],
    ["Close date", "平仓时间"],
    ["Close Reason", "平仓原因"],
    ["Filter", "筛选"],
    ["First Page", "第一页"],
    ["Previous Page", "上一页"],
    ["Next Page", "下一页"],
    ["Last Page", "最后一页"],
    ["Page 1", "第 1 页"],
    ["Notifications (F8)", "通知 (F8)"],
    ["Available bots", "可用机器人"],
    ["Login info expired!", "登录信息已过期！"],
    ["Add new Bot", "添加机器人"],
    ["Save", "保存"],
    ["Cancel", "取消"],
    ["Edit", "编辑"],
    ["Delete", "删除"],
    ["Reload", "重新加载"],
    ["Refresh", "刷新"],
    ["Start", "启动"],
    ["Stop", "停止"],
    ["Stopbuy", "停止买入"],
    ["Running", "运行中"],
    ["Stopped", "已停止"],
    ["Settings", "设置"],
    ["Logs", "日志"],
    ["Backtesting", "回测"],
    ["Download Data", "下载数据"],
    ["Chart", "图表"],
    ["Trade", "交易"],
    ["ID", "ID"],
  ]);

  const phraseText = [
    ["Open trades of all selected bots. Click on a trade to go to the trade page for that trade/bot.", "所选机器人的当前持仓。点击交易可进入对应交易详情。"],
    ["Closed trades for all selected bots. Click on a trade to go to the trade page for that trade/bot.", "所选机器人的已关闭交易。点击交易可进入对应交易详情。"],
    ["Click to select all bots", "点击选择全部机器人"],
    ["Click to select all dry run bots", "点击选择全部模拟机器人"],
    ["Select pairs to delete pairs from your blacklist.", "选择要从黑名单删除的交易对。"],
    ["Blacklist - Select (followed by a click on '-') to remove pairs", "黑名单 - 选择后点击减号移除交易对"],
    ["Connected to bot, however Login failed, Username or Password wrong.", "已连接机器人，但登录失败，用户名或密码错误。"],
    ["Please verify that the bot is running, the Bot API is enabled and the URL is reachable.", "请确认机器人正在运行、Bot API 已启用且地址可访问。"],
  ];

  const placeholders = new Map([
    ["Freqtrader", "用户名"],
    ["Bot Name", "机器人名称"],
    ["Filter", "筛选"],
  ]);

  function normalize(text) {
    return text.replace(/\s+/g, " ").trim();
  }

  function translateString(value) {
    if (!value) return value;
    const trimmed = normalize(value);
    if (exactText.has(trimmed)) return value.replace(trimmed, exactText.get(trimmed));

    let next = value;
    for (const [source, target] of exactText) {
      if (source.length > 2 && next.includes(source)) next = next.replaceAll(source, target);
    }
    for (const [source, target] of phraseText) {
      if (next.includes(source)) next = next.replaceAll(source, target);
    }
    return next;
  }

  function translateTextNode(node) {
    const translated = translateString(node.nodeValue);
    if (translated !== node.nodeValue) node.nodeValue = translated;
  }

  function translateElement(element) {
    if (!(element instanceof Element)) return;

    for (const attr of ["aria-label", "title"]) {
      const value = element.getAttribute(attr);
      const translated = translateString(value);
      if (translated && translated !== value) element.setAttribute(attr, translated);
    }

    const placeholder = element.getAttribute("placeholder");
    if (placeholder && placeholders.has(placeholder)) {
      element.setAttribute("placeholder", placeholders.get(placeholder));
    }
  }

  function walk(root) {
    if (!root) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let node = walker.currentNode;
    while (node) {
      if (node.nodeType === Node.TEXT_NODE) translateTextNode(node);
      if (node.nodeType === Node.ELEMENT_NODE) translateElement(node);
      node = walker.nextNode();
    }
  }

  function translatePage() {
    document.title = "Freqtrade 量化交易面板";
    walk(document.body);
    forceBrandText();
    ensureOkxBalanceCard();
    if (window.FT_DISABLE_NATIVE_UI === true) blockUnsafeAccess();
  }

  function formatNumber(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return value || "-";
    return new Intl.NumberFormat("zh-CN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(number);
  }

  function ensureOkxBalanceCard() {
    if (location.pathname !== "/balance") return;
    if (document.querySelector("[data-okx-sandbox-balance='true']")) return;
    const main = document.querySelector("main");
    if (!main) return;

    const balance = window.FT_OKX_SANDBOX_BALANCE;
    if (!balance?.ok) return;
    const currencies = Array.isArray(balance.currencies) ? balance.currencies : [];
    const rows = currencies.slice(0, 8).map((item) => `
      <tr>
        <td>${item.ccy || "-"}</td>
        <td>${formatNumber(item.eq)}</td>
        <td>${formatNumber(item.availBal)}</td>
        <td>${formatNumber(item.eqUsd)}</td>
      </tr>
    `).join("");

    const card = document.createElement("section");
    card.dataset.okxSandboxBalance = "true";
    card.style.cssText = `
      margin: 16px 0;
      padding: 16px;
      border: 1px solid rgba(34, 197, 94, .45);
      border-radius: 8px;
      background: rgba(5, 46, 22, .36);
      color: inherit;
    `;
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

  function forceBrandText() {
    Array.from(document.querySelectorAll("body *")).reverse().forEach((element) => {
      if (normalize(element.textContent || "") === "FreqtradeUI") {
        element.textContent = "Freqtrade 控制台";
      }
      for (const node of element.childNodes) {
        if (node.nodeType === Node.TEXT_NODE && normalize(node.nodeValue) === "FreqtradeUI") {
          node.nodeValue = node.nodeValue.replace("FreqtradeUI", "Freqtrade 控制台");
        }
      }
      const label = element.getAttribute("aria-label");
      if (label && label.includes("FreqtradeUI")) {
        element.setAttribute("aria-label", label.replaceAll("FreqtradeUI", "Freqtrade 控制台"));
      }
    });
  }

  function blockUnsafeAccess() {
    const blockedPaths = new Set([
      "/",
      "/dashboard",
      "/balance",
      "/open_trades",
      "/trade_history",
      "/trade",
      "/graph",
      "/logs",
      "/backtest",
      "/settings",
      "/pairlist",
      "/pairlist_config",
      "/download_data",
      "/login",
    ]);
    if (location.pathname === "/analysis.html") return;
    const isBlockedRoute = blockedPaths.has(location.pathname) || location.href.includes("/login?");
    const isLoginRoute = location.pathname === "/login" || location.href.includes("/login?");
    const hasLoginForm = document.querySelector("input[type='password']") && document.body.textContent.includes("Freqtrade");
    if (!isBlockedRoute && !isLoginRoute && !hasLoginForm) return;
    if (document.querySelector("[data-ft-access-disabled='true']")) return;

    const main = document.querySelector("main") || document.body;
    main.innerHTML = `
      <section data-ft-access-disabled="true" style="
        max-width: 680px;
        margin: 48px auto;
        padding: 24px;
        border: 1px solid #ffb347;
        border-radius: 8px;
        background: #1f1a12;
        color: #eef3f7;
        line-height: 1.7;
      ">
        <h1 style="margin: 0 0 12px; font-size: 24px;">交易安全模式</h1>
        <p style="margin: 0 0 16px;">当前显式启用了只读安全模式，不能通过此界面进入交易控制、强制开仓、平仓或修改机器人状态。</p>
        <p style="margin: 0 0 20px; color: #ffcf8a;">如需恢复原生 UI，请不要设置 window.FT_DISABLE_NATIVE_UI。</p>
        <a href="/dashboard" style="
          display: inline-flex;
          min-height: 36px;
          align-items: center;
          padding: 0 14px;
          border: 1px solid #45c2ff;
          border-radius: 6px;
          color: #dff6ff;
          text-decoration: none;
          background: #113140;
        ">返回原生仪表盘</a>
      </section>
    `;
    document.querySelectorAll("footer a, [role='contentinfo'] a").forEach((link) => {
      if (link.getAttribute("href") !== "/dashboard") link.remove();
    });
  }

  function setNativeValue(input, value) {
    const descriptor = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), "value");
    if (descriptor && descriptor.set) {
      descriptor.set.call(input, value);
    } else {
      input.value = value;
    }
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function visibleInputs() {
    return Array.from(document.querySelectorAll("input"))
      .filter((input) => input.type !== "hidden" && !input.disabled && input.offsetParent !== null);
  }

  async function setupLocalAutoLogin() {
    const hasPasswordField = document.querySelector("input[type='password']");
    const isLoginPage = location.pathname === "/login" || location.href.includes("/login?");
    if (!isLoginPage || !hasPasswordField || document.body.dataset.ftAutoLoginDone === "true") return;
    document.body.dataset.ftAutoLoginDone = "true";

    let login;
    try {
      const response = await fetch("/assets/local-login.json", { cache: "no-store" });
      if (!response.ok) return;
      login = await response.json();
    } catch (_) {
      return;
    }
    if (!login || login.enabled !== true || !login.username || !login.password) return;

    const inputs = visibleInputs();
    const password = inputs.find((input) => input.type === "password");
    const textInputs = inputs.filter((input) => input.type !== "password");
    if (!password || textInputs.length < 2) return;

    const botInput = textInputs[0];
    const urlInput = textInputs.find((input) => input.value.startsWith("http")) || textInputs[1];
    const usernameInput = textInputs.find((input) => input !== botInput && input !== urlInput) || textInputs[textInputs.length - 1];

    setNativeValue(botInput, login.botName || "freqtrade");
    setNativeValue(urlInput, login.url || window.location.origin);
    setNativeValue(usernameInput, login.username);
    setNativeValue(password, login.password);

    window.setTimeout(() => {
      const form = password.closest("form");
      const submit = form?.querySelector("button[type='submit']") ||
        Array.from(document.querySelectorAll("button")).find((button) => /登录|Submit/i.test(button.textContent || ""));
      if (form && typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else if (submit) {
        submit.click();
      }
    }, 300);
  }

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node.nodeType === Node.TEXT_NODE) translateTextNode(node);
        if (node.nodeType === Node.ELEMENT_NODE) walk(node);
      }
      if (mutation.type === "characterData") translateTextNode(mutation.target);
      if (mutation.type === "attributes") translateElement(mutation.target);
    }
    setupLocalAutoLogin();
  });

  function start() {
    translatePage();
    setupLocalAutoLogin();
    window.setInterval(translatePage, 1200);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["aria-label", "title", "placeholder"],
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
