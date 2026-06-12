(function () {
  "use strict";

  const API = "/api/v1";

  const els = {
    refresh: document.getElementById("refresh-btn"),
    range: document.getElementById("filter-range"),
    state: document.getElementById("state-banner"),
    syncTime: document.getElementById("sync-time"),
    buildVersion: document.getElementById("build-version"),
    mode: document.getElementById("metric-mode"),
    strategy: document.getElementById("metric-strategy"),
    balance: document.getElementById("metric-balance"),
    balanceNote: document.getElementById("metric-balance-note"),
    profit: document.getElementById("metric-profit"),
    profitRate: document.getElementById("metric-profit-rate"),
    slots: document.getElementById("metric-slots"),
    stake: document.getElementById("metric-stake"),
    dailyBars: document.getElementById("daily-bars"),
    dailySummary: document.getElementById("daily-summary"),
    openTradeCount: document.getElementById("open-trade-count"),
    openTradesBody: document.getElementById("open-trades-body"),
    performanceCount: document.getElementById("performance-count"),
    performanceList: document.getElementById("performance-list"),
    aiGateState: document.getElementById("ai-gate-state"),
    aiMode: document.getElementById("ai-mode"),
    aiUpdated: document.getElementById("ai-updated"),
    aiDataset: document.getElementById("ai-dataset"),
    aiLabel: document.getElementById("ai-label"),
    aiQlibIc: document.getElementById("ai-qlib-ic"),
    aiQlibRankIc: document.getElementById("ai-qlib-rank-ic"),
    aiCandidates: document.getElementById("ai-candidates"),
    aiFailedChecks: document.getElementById("ai-failed-checks"),
    sequenceStatus: document.getElementById("sequence-status"),
    sequenceLookback: document.getElementById("sequence-lookback"),
    sequenceRows: document.getElementById("sequence-rows"),
    sequenceLstm: document.getElementById("sequence-lstm"),
    sequenceTransformer: document.getElementById("sequence-transformer"),
    sequenceCandidates: document.getElementById("sequence-candidates"),
    deepStatus: document.getElementById("deep-status"),
    deepTorch: document.getElementById("deep-torch"),
    deepLstmCorr: document.getElementById("deep-lstm-corr"),
    deepTransformerCorr: document.getElementById("deep-transformer-corr"),
    deepEnsembleRank: document.getElementById("deep-ensemble-rank"),
    deepCandidates: document.getElementById("deep-candidates"),
    autopilotStatus: document.getElementById("autopilot-status"),
    autopilotEnabled: document.getElementById("autopilot-enabled"),
    autopilotActions: document.getElementById("autopilot-actions"),
    autopilotAppliedAt: document.getElementById("autopilot-applied-at"),
    autopilotConfidence: document.getElementById("autopilot-confidence"),
    autopilotParams: document.getElementById("autopilot-params"),
    autopilotBacklog: document.getElementById("autopilot-backlog"),
    riskScore: document.getElementById("risk-score"),
    riskList: document.getElementById("risk-list"),
    pairCount: document.getElementById("pair-count"),
    pairList: document.getElementById("pair-list"),
    configList: document.getElementById("config-list"),
  };

  function setState(message, type) {
    els.state.textContent = message;
    els.state.className = `state-banner ${type || ""}`.trim();
  }

  async function localSnapshot() {
    const response = await fetch("/assets/analysis-data.json", { cache: "no-store" });
    if (!response.ok) throw new Error("LOCAL_SNAPSHOT_UNAVAILABLE");
    const snapshot = await response.json();
    return {
      config: snapshot.config,
      balance: snapshot.balance,
      profit: snapshot.profit,
      count: snapshot.count,
      status: snapshot.status || [],
      performance: snapshot.performance || [],
      whitelist: snapshot.whitelist || { whitelist: [] },
      daily: snapshot.daily || { data: [] },
      ai: snapshot.ai || {},
      autopilot: snapshot.autopilot || {},
      execution: snapshot.execution || {},
      guardian: snapshot.guardian || {},
      source: snapshot.source,
      generated_at: snapshot.generated_at,
    };
  }

  function money(value, unit) {
    const number = Number(value || 0);
    return `${number.toLocaleString("zh-CN", { maximumFractionDigits: 3 })} ${unit || ""}`.trim();
  }

  function percent(value) {
    return `${(Number(value || 0) * 100).toFixed(3)}%`;
  }

  function metric(value, digits) {
    if (value === null || value === undefined || value === "") return "-";
    return Number(value).toFixed(digits ?? 4);
  }

  function text(value, fallback) {
    return value === null || value === undefined || value === "" ? fallback : String(value);
  }

  function renderMetrics(data) {
    const { config, balance, profit, count } = data;
    els.buildVersion.textContent = config.version || "-";
    const virtualMode = config.virtual_mode || (config.dry_run ? "freqtrade_dry_run" : "unsafe_live");
    els.mode.textContent = virtualMode === "okx_sandbox" ? "OKX 模拟盘" : config.dry_run ? "Freqtrade dry-run" : "实盘";
    els.mode.style.color = virtualMode === "okx_sandbox" || config.dry_run ? "var(--success)" : "var(--danger)";
    els.strategy.textContent = `策略 ${text(config.strategy, "DryRunRsiStrategy")}`;
    els.balance.textContent = money(balance.total_bot ?? balance.total, balance.stake);
    els.balanceNote.textContent = `${text(balance.note, "余额")} | 折合 ${money(balance.value_bot ?? balance.value, balance.symbol)}`;
    els.profit.textContent = money(profit.profit_all_coin, config.stake_currency);
    els.profitRate.textContent = percent(profit.profit_all_ratio);
    els.slots.textContent = `${count.current} / ${count.max}`;
    els.stake.textContent = `单笔 ${config.stake_amount} ${config.stake_currency}`;
  }

  function renderDaily(daily) {
    const rows = [...(daily.data || [])].reverse();
    const maxAbs = Math.max(1, ...rows.map((row) => Math.abs(Number(row.abs_profit || 0))));
    const total = rows.reduce((sum, row) => sum + Number(row.abs_profit || 0), 0);
    els.dailySummary.textContent = `${rows.length} 天合计 ${money(total, "USDT")}`;
    els.dailyBars.innerHTML = "";
    if (!rows.length) {
      els.dailyBars.innerHTML = '<div class="empty-row">暂无收益时间序列。</div>';
      return;
    }
    for (const row of rows) {
      const value = Number(row.abs_profit || 0);
      const height = Math.max(24, Math.round((Math.abs(value) / maxAbs) * 150));
      const bar = document.createElement("div");
      bar.className = value === 0 ? "bar zero" : "bar";
      bar.style.height = `${height}px`;
      bar.title = `${row.date}: ${money(value, "USDT")} / ${row.trade_count} 笔`;
      bar.textContent = row.trade_count || "0";
      els.dailyBars.appendChild(bar);
    }
  }

  function renderOpenTrades(status) {
    els.openTradeCount.textContent = `${status.length} 笔`;
    els.openTradesBody.innerHTML = "";
    if (!status.length) {
      els.openTradesBody.innerHTML = '<tr><td class="empty-row" colspan="5">暂无持仓，当前风险暴露为 0。</td></tr>';
      return;
    }
    for (const trade of status) {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${text(trade.pair, "-")}</td>
        <td>${money(trade.stake_amount, trade.stake_currency)}</td>
        <td>${money(trade.open_rate, "")}</td>
        <td>${percent(trade.profit_ratio)}</td>
        <td>${text(trade.open_date_hum, trade.open_date || "-")}</td>
      `;
      els.openTradesBody.appendChild(row);
    }
  }

  function renderPerformance(performance) {
    els.performanceCount.textContent = `${performance.length} 项`;
    els.performanceList.innerHTML = "";
    if (!performance.length) {
      els.performanceList.innerHTML = '<div class="empty-row">暂无已完成交易，表现统计将在交易后生成。</div>';
      return;
    }
    const max = Math.max(1, ...performance.map((item) => Math.abs(Number(item.profit || item.profit_abs || 0))));
    for (const item of performance.slice(0, 8)) {
      const value = Number(item.profit || item.profit_abs || 0);
      const row = document.createElement("div");
      row.className = "perf-row";
      row.innerHTML = `
        <strong>${text(item.pair, "-")}</strong>
        <span class="perf-bar"><span style="width:${Math.max(4, Math.abs(value) / max * 100)}%"></span></span>
        <span>${money(value, "USDT")}</span>
      `;
      els.performanceList.appendChild(row);
    }
  }

  function aiLevel(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "neutral";
    if (Number(value) > 0.05) return "success";
    if (Number(value) > 0) return "warning";
    return "danger";
  }

  function renderLabelText(ai, label) {
    const horizon = text(ai.label_horizon, "");
    if (horizon.includes("candle") || horizon.includes("open")) return horizon;
    return `${text(horizon, "5")} 根K线 | ${text(label.target, "future return")}`;
  }

  function renderAi(ai) {
    const gate = ai.deployment_gate || {};
    const dataset = ai.dataset || {};
    const label = ai.label_definition || {};
    const qlib = (ai.metrics || {}).qlib || {};
    const candidates = ai.research_long_candidates || [];
    const failedChecks = gate.failed_checks || [];
    const passed = Boolean(gate.passed);

    els.aiGateState.textContent = passed ? "已通过" : "研究模式";
    els.aiGateState.className = passed ? "status-pill success" : "status-pill warning";
    els.aiMode.textContent = text(gate.mode, passed ? "trade_ready" : "research_only_do_not_trade");
    els.aiMode.className = passed ? "success-text" : "warning-text";
    els.aiUpdated.textContent = `更新 ${text(ai.latest_timestamp || ai.generated_at, "-")}`;
    els.aiDataset.textContent = `${Number(dataset.rows || 0).toLocaleString("zh-CN")} 行 / ${Number(dataset.pairs || 0)} 币`;
    els.aiLabel.textContent = renderLabelText(ai, label);
    els.aiQlibIc.textContent = metric(qlib.IC, 4);
    els.aiQlibIc.className = `${aiLevel(qlib.IC)}-text`;
    els.aiQlibRankIc.textContent = metric(qlib["Rank IC"], 4);
    els.aiQlibRankIc.className = `${aiLevel(qlib["Rank IC"])}-text`;

    els.aiCandidates.innerHTML = "";
    if (!candidates.length) {
      els.aiCandidates.innerHTML = '<div class="empty-row">暂无 AI 候选信号，请先生成 3 个月训练数据。</div>';
    } else {
      for (const item of candidates.slice(0, 6)) {
        const row = document.createElement("div");
        row.className = "ai-candidate";
        row.innerHTML = `
          <div>
            <strong>${text(item.pair, "-")}</strong>
            <span class="signal-badge">${text(item.pred_signal, "neutral")}</span>
          </div>
          <span>${percent(Number(item.pred_return_5_open_pct || 0) / 100)}</span>
          <span>上涨 ${percent(item.pred_up_probability)}</span>
          <span>排名 ${text(item.rank_position, "-")}</span>
        `;
        els.aiCandidates.appendChild(row);
      }
    }

    els.aiFailedChecks.innerHTML = "";
    if (!failedChecks.length) {
      const chip = document.createElement("span");
      chip.className = "check-chip success";
      chip.textContent = "准入检查全部通过";
      els.aiFailedChecks.appendChild(chip);
    } else {
      for (const check of failedChecks) {
        const chip = document.createElement("span");
        chip.className = "check-chip warning";
        chip.textContent = check;
        els.aiFailedChecks.appendChild(chip);
      }
    }

    renderSequence(ai.sequence || {});
    renderDeepSequence(ai.deep_sequence || {});
  }

  function modelStatus(model) {
    const status = text((model || {}).status, "missing_report");
    if (status.includes("ready")) return { text: "可训练", level: "success" };
    if (status.includes("missing")) return { text: "缺 torch", level: "warning" };
    return { text: status, level: "neutral" };
  }

  function renderSequence(sequence) {
    const dataset = sequence.dataset || {};
    const deep = sequence.deep_learning_models || {};
    const lstm = modelStatus(deep.lstm);
    const transformer = modelStatus(deep.transformer);
    const candidates = sequence.top_sequence_candidates || [];

    els.sequenceStatus.textContent = sequence.ok ? "序列基线已训练" : "等待训练";
    els.sequenceStatus.className = sequence.ok ? "status-pill success" : "status-pill warning";
    els.sequenceLookback.textContent = sequence.lookback_candles ? `${sequence.lookback_candles} 根K线` : "-";
    els.sequenceRows.textContent = dataset.sequence_rows ? `${Number(dataset.sequence_rows).toLocaleString("zh-CN")} 行` : "-";
    els.sequenceLstm.textContent = lstm.text;
    els.sequenceLstm.className = `${lstm.level}-text`;
    els.sequenceTransformer.textContent = transformer.text;
    els.sequenceTransformer.className = `${transformer.level}-text`;
    els.sequenceCandidates.innerHTML = "";
    if (!candidates.length) {
      els.sequenceCandidates.innerHTML = '<div class="empty-row">暂无序列候选，请运行 scripts/train-sequence-models.sh。</div>';
      return;
    }
    for (const item of candidates.slice(0, 4)) {
      const row = document.createElement("div");
      row.className = "ai-candidate";
      row.innerHTML = `
        <div>
          <strong>${text(item.pair, "-")}</strong>
          <span class="signal-badge">${text(item.seq_pred_signal, "neutral")}</span>
        </div>
        <span>${percent(Number(item.seq_pred_return_5_open_pct || 0) / 100)}</span>
        <span>上涨 ${percent(item.seq_pred_up_probability)}</span>
        <span>序列排名 ${text(item.seq_rank_position, "-")}</span>
      `;
      els.sequenceCandidates.appendChild(row);
    }
  }

  function renderDeepSequence(deep) {
    const models = deep.models || {};
    const lstmCorr = (((models.lstm || {}).regression || {}).corr);
    const transformerCorr = (((models.transformer || {}).regression || {}).corr);
    const ensembleRank = ((((models.ensemble || {}).cross_sectional_ranking || {}).spearman_mean_by_timestamp));
    const candidates = deep.top_deep_candidates || [];

    els.deepStatus.textContent = deep.ok ? "深度模型已训练" : "等待 PyTorch 训练";
    els.deepStatus.className = deep.ok ? "status-pill success" : "status-pill warning";
    els.deepTorch.textContent = deep.torch_version ? `${deep.torch_version} / ${text(deep.device, "cpu")}` : "-";
    els.deepLstmCorr.textContent = metric(lstmCorr, 4);
    els.deepLstmCorr.className = `${aiLevel(lstmCorr)}-text`;
    els.deepTransformerCorr.textContent = metric(transformerCorr, 4);
    els.deepTransformerCorr.className = `${aiLevel(transformerCorr)}-text`;
    els.deepEnsembleRank.textContent = metric(ensembleRank, 4);
    els.deepEnsembleRank.className = `${aiLevel(ensembleRank)}-text`;
    els.deepCandidates.innerHTML = "";
    if (!candidates.length) {
      els.deepCandidates.innerHTML = '<div class="empty-row">暂无深度候选，请运行 scripts/train-deep-sequence-models.sh。</div>';
      return;
    }
    for (const item of candidates.slice(0, 4)) {
      const row = document.createElement("div");
      row.className = "ai-candidate";
      row.innerHTML = `
        <div>
          <strong>${text(item.pair, "-")}</strong>
          <span class="signal-badge">${text(item.deep_pred_signal, "neutral")}</span>
        </div>
        <span>LSTM ${percent(Number(item.lstm_pred_return_5_open_pct || 0) / 100)}</span>
        <span>TF ${percent(Number(item.transformer_pred_return_5_open_pct || 0) / 100)}</span>
        <span>深度排名 ${text(item.deep_rank_position, "-")}</span>
      `;
      els.deepCandidates.appendChild(row);
    }
  }

  function renderAutopilot(autopilot) {
    const enabled = Boolean(autopilot.enabled);
    const ok = Boolean(autopilot.ok);
    const overlay = autopilot.overlay || {};
    const parameters = overlay.parameters || {};
    const backlog = autopilot.backlog || [];
    els.autopilotStatus.textContent = ok ? "运行正常" : enabled ? "等待下轮" : "未启用";
    els.autopilotStatus.className = ok ? "status-pill success" : "status-pill warning";
    els.autopilotEnabled.textContent = enabled ? "开启" : "关闭";
    els.autopilotEnabled.className = enabled ? "success-text" : "warning-text";
    els.autopilotActions.textContent = `${autopilot.actions_applied || 0} 应用 / ${autopilot.actions_rejected || 0} 拒绝`;
    els.autopilotAppliedAt.textContent = text(overlay.applied_at || autopilot.checked_at, "-");
    els.autopilotConfidence.textContent = overlay.confidence === undefined ? "-" : metric(overlay.confidence, 2);
    els.autopilotParams.innerHTML = "";
    const entries = Object.entries(parameters);
    if (!entries.length) {
      els.autopilotParams.innerHTML = '<div class="empty-row">暂无自动覆盖参数，使用基础策略流。</div>';
    } else {
      for (const [key, value] of entries) {
        const chip = document.createElement("span");
        chip.className = "check-chip success";
        chip.textContent = `${key}: ${value}`;
        els.autopilotParams.appendChild(chip);
      }
    }
    els.autopilotBacklog.innerHTML = "";
    if (!backlog.length) {
      els.autopilotBacklog.innerHTML = '<div class="empty-row">暂无后台任务。</div>';
    } else {
      for (const item of backlog.slice(0, 6)) {
        const chip = document.createElement("span");
        chip.className = "check-chip warning";
        chip.textContent = `${text(item.priority, "medium")}: ${text(item.item, "-")}`;
        els.autopilotBacklog.appendChild(chip);
      }
    }
  }

  function riskItem(level, title, body) {
    const item = document.createElement("li");
    item.className = `risk-item ${level}`;
    item.innerHTML = `<strong>${title}</strong><br><span>${body}</span>`;
    return item;
  }

  function renderRisks(data) {
    const { config, count, status, profit, execution, guardian } = data;
    const risks = [];
    if (guardian.ok) {
      risks.push(["success", "24 小时守护运行中", "Docker、API、盯盘、Gemini 和防睡眠会话均正常；只会随手动 stop 停止。"]);
    } else {
      risks.push(["warning", "守护状态待恢复", "稳定守护会在连续失败后自动拉起服务。"]);
    }
    if (config.virtual_mode === "okx_sandbox") {
      risks.push(["success", "OKX 模拟盘交易中", "交易请求路由到 OKX Demo 环境，不是正式账户。"]);
    } else {
      risks.push(config.dry_run
        ? ["success", "Freqtrade dry-run 已开启", "当前使用本地虚拟钱包验证策略。"]
        : ["danger", "实盘模式", "实盘前请确认 API 权限、仓位和止损。"]);
    }
    if (execution.last_trade_status === "passed") {
      risks.push(["success", "虚拟开平仓已验证", `${text(execution.last_trade_pair, "-")} / 交易 ID ${text(execution.last_trade_id, "-")}。`]);
    }
    risks.push(Number(count.current) === 0
      ? ["success", "无当前持仓", "当前没有市场风险暴露。"]
      : ["warning", "存在持仓", `当前 ${count.current} 笔持仓需要跟踪。`]);
    risks.push(Number(config.stoploss) < 0
      ? ["success", "止损已配置", `策略止损 ${percent(config.stoploss)}。`]
      : ["warning", "止损异常", "未检测到有效止损。"]);
    risks.push(Number(profit.trade_count || 0) === 0
      ? ["warning", "暂无持续交易样本", "自动盯盘会继续积累样本，强制验收交易不作为策略收益依据。"]
      : ["success", "已有交易样本", `累计 ${profit.trade_count} 笔交易。`]);
    if (status.length >= Number(count.max || 0) && Number(count.max || 0) > 0) {
      risks.push(["warning", "持仓已满", "新信号可能无法开仓。"]);
    }

    els.riskList.innerHTML = "";
    for (const [level, title, body] of risks) {
      els.riskList.appendChild(riskItem(level, title, body));
    }
    const dangerCount = risks.filter(([level]) => level === "danger").length;
    const warningCount = risks.filter(([level]) => level === "warning").length;
    els.riskScore.textContent = dangerCount ? "高风险" : warningCount ? "需观察" : "正常";
    els.riskScore.style.color = dangerCount ? "var(--danger)" : warningCount ? "var(--warning)" : "var(--success)";
  }

  function renderPairs(whitelist) {
    const pairs = whitelist.whitelist || whitelist || [];
    els.pairCount.textContent = `${pairs.length} 个`;
    els.pairList.innerHTML = "";
    if (!pairs.length) {
      els.pairList.innerHTML = '<div class="empty-row">暂无交易对白名单。</div>';
      return;
    }
    for (const pair of pairs) {
      const chip = document.createElement("span");
      chip.className = "pair-chip";
      chip.textContent = pair;
      els.pairList.appendChild(chip);
    }
  }

  function renderConfig(config) {
    const entries = [
      ["交易模式", config.trading_mode],
      ["保证金模式", config.margin_mode || "无"],
      ["计价币种", config.stake_currency],
      ["最大持仓", config.max_open_trades],
      ["单笔金额", config.stake_amount],
      ["时间周期", config.timeframe],
      ["止损", percent(config.stoploss)],
      ["追踪止损", config.trailing_stop ? "开启" : "关闭"],
    ];
    els.configList.innerHTML = "";
    for (const [key, value] of entries) {
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = key;
      dd.textContent = text(value, "-");
      els.configList.append(dt, dd);
    }
  }

  async function loadAll() {
    setState("正在加载本地分析快照...", "");
    try {
      const data = await localSnapshot();
      renderMetrics(data);
      renderDaily(data.daily);
      renderOpenTrades(data.status);
      renderPerformance(data.performance);
      renderAi(data.ai);
      renderAutopilot(data.autopilot);
      renderRisks(data);
      renderPairs(data.whitelist);
      renderConfig(data.config);
      const now = new Date();
      els.syncTime.textContent = now.toLocaleTimeString("zh-CN", { hour12: false });
      const modeText = data.config.virtual_mode === "okx_sandbox"
        ? "OKX 模拟盘自动交易运行中，页面显示本地只读分析快照。"
        : "本地虚拟交易分析快照已加载。";
      setState(modeText, "ok");
    } catch (error) {
      setState(`本地分析快照加载失败：${error.message}`, "error");
    }
  }

  els.refresh.addEventListener("click", loadAll);
  els.range.addEventListener("change", loadAll);

  loadAll();
})();
