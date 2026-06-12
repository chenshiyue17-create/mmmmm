import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_required_files_exist() -> None:
    required = [
        "README.md",
        "docs/AI_ML_TRADING_FRAMEWORK.md",
        "pytest.ini",
        ".env.example",
        "docker-compose.yml",
        "custom_ui/index.html",
        "scripts/generate-local-login.py",
        "scripts/freqtrade.sh",
        "scripts/read_only_proxy.py",
        "scripts/switch-exchange.py",
        "custom_ui/freqtrade-zh.js",
        "custom_ui/okx-sandbox-balance.js",
        "custom_ui/BotBalance-CfdHVrDj.js",
        "runtime/sitecustomize.py",
        "user_data/config.json",
        "user_data/strategies/DryRunRsiStrategy.py",
        "user_data/strategies/DatugouBreakoutStrategy.py",
        "scripts/start-dev.sh",
        "scripts/stop-dev.sh",
        "scripts/dev-status.sh",
        "scripts/install-runtime.sh",
        "scripts/validate-config.sh",
        "scripts/verify-runtime.sh",
        "scripts/check-api-scope.sh",
        "scripts/set-okx-keychain.sh",
        "scripts/export-keychain-secrets.sh",
        "scripts/check-okx-private-api.sh",
        "scripts/check-okx-sandbox-api.py",
        "scripts/check-okx-sandbox-api.sh",
        "scripts/run-dryrun-trade-test.py",
        "scripts/run-dryrun-trade-test.sh",
        "scripts/run-simulation-test.sh",
        "scripts/security-leak-check.py",
        "scripts/security-leak-check.sh",
        "scripts/generate-okx-balance-ui.py",
        "scripts/open-analysis.sh",
        "scripts/open-ui.sh",
        "scripts/desktop-launch.sh",
        "scripts/auto-watch.py",
        "scripts/start-auto-watch.sh",
        "scripts/stop-auto-watch.sh",
        "scripts/import-research-flow.py",
        "scripts/accumulate-market-data.py",
        "scripts/accumulate-market-data.sh",
        "scripts/build-ml-dataset.py",
        "scripts/train-ml-models.py",
        "scripts/train-ml-models.sh",
        "scripts/train-sequence-models.py",
        "scripts/train-sequence-models.sh",
        "scripts/train-deep-sequence-models.py",
        "scripts/train-deep-sequence-models.sh",
        "docker/deep-research.Dockerfile",
        "scripts/prepare-qlib-data.py",
        "scripts/prepare-qlib-data.sh",
        "scripts/run-qlib-smoke.py",
        "scripts/run-qlib-smoke.sh",
        "scripts/build-qlib-research-image.sh",
        "scripts/run-qlib-dump.sh",
        "scripts/run-qlib-qrun.sh",
        "docker/qlib-research.Dockerfile",
        "scripts/gemini-optimizer.py",
        "scripts/gemini-autopilot-smoke.py",
        "scripts/start-gemini-optimizer.sh",
        "scripts/stop-gemini-optimizer.sh",
        "scripts/stability-guardian.py",
        "scripts/start-stability-guardian.sh",
        "scripts/stop-stability-guardian.sh",
        "scripts/start-okx-sandbox-trade.py",
        "scripts/start-okx-sandbox-trade.sh",
        "deploy/aliyun/bootstrap.sh",
        "deploy/aliyun/install-systemd.sh",
        "deploy/aliyun/README.md",
        "docs/HYBRID_SERVER_LOCAL_ARCHITECTURE.md",
        ".env.server.example",
        ".dockerignore",
        "scripts/sync-research-to-server.sh",
    ]
    for rel in required:
        assert (ROOT / rel).exists(), rel


def test_config_is_safe_dry_run() -> None:
    config = json.loads((ROOT / "user_data/config.json").read_text())
    if config["exchange"]["name"] == "okx":
        assert config["dry_run"] is False
        assert "OKX_SANDBOX_MODE=1" in (ROOT / ".env").read_text()
    else:
        assert config["dry_run"] is True
    assert config["api_server"]["enabled"] is True
    assert config["api_server"]["enable_openapi"] is False
    assert config["telegram"]["enabled"] is False
    assert "webhook" not in config
    assert config["exchange"]["name"] in {"binance", "okx"}
    assert config["exchange"]["key"] == ""
    assert config["exchange"]["enable_ws"] is False
    assert ".*/USDT" in config["exchange"]["pair_whitelist"]
    assert "BTC/USDT" in config["exchange"]["pair_blacklist"]
    assert config["pairlists"][0]["method"] == "PercentChangePairList"
    assert config["pairlists"][0]["refresh_period"] <= 900
    assert config["strategy"] == "DatugouBreakoutStrategy"
    assert config["force_entry_enable"] is True
    assert "FREQTRADE_RUN_MODE=trade" in (ROOT / ".env.example").read_text()
    assert "ML_SIGNAL_FILTER_ENABLED=0" in (ROOT / ".env.example").read_text()


def test_okx_template_does_not_contain_real_secret() -> None:
    template = json.loads((ROOT / "config_templates/config.okx.json").read_text())
    exchange = template["exchange"]
    assert exchange["name"] == "okx"
    assert exchange["key"] == "${OKX_KEY}"
    assert exchange["secret"] == "${OKX_SECRET}"


def test_binance_template_does_not_contain_real_secret() -> None:
    template = json.loads((ROOT / "config_templates/config.binance.json").read_text())
    exchange = template["exchange"]
    assert exchange["name"] == "binance"
    assert exchange["key"] == "${BINANCE_KEY}"
    assert exchange["secret"] == "${BINANCE_SECRET}"


def test_output_and_logs_dirs_exist() -> None:
    assert (ROOT / "output").is_dir()
    assert (ROOT / "logs").is_dir()


def test_chinese_ui_overlay_is_enabled() -> None:
    index = (ROOT / "custom_ui/index.html").read_text()
    script = (ROOT / "custom_ui/freqtrade-zh.js").read_text()
    balance_chunk = (ROOT / "custom_ui/BotBalance-CfdHVrDj.js").read_text()
    compose = (ROOT / "docker-compose.yml").read_text()
    assert 'lang="zh-CN"' in index
    assert "freqtrade-zh.js" in index
    assert "okx-sandbox-balance.js" in index
    assert "OKX 模拟盘余额" in script
    assert "Freqtrade 本地 dry-run 钱包" in script
    assert "欢迎使用 Freqtrade 控制台" in script
    assert "blockUnsafeAccess" in script
    assert "window.FT_DISABLE_NATIVE_UI === true" in script
    assert "setupLocalAutoLogin" in script
    assert "/assets/local-login.json" in script
    assert "ensureAnalysisLink();" not in script
    assert "分析工作台" not in script
    assert "text:`余额`" in balance_chunk
    assert "./custom_ui/index.html" in compose
    assert "./custom_ui/analysis.html" in compose
    assert "./custom_ui/analysis.css" in compose
    assert "./custom_ui/analysis.js" in compose
    assert "./custom_ui/analysis-data.json" in compose
    assert "./custom_ui/local-login.json" in compose
    assert "./custom_ui/okx-sandbox-balance.js" in compose
    assert "./output/okx-sandbox-api-check.json" in compose
    assert "${FREQTRADE_BACKEND_PORT:-18080}:8080" in compose
    assert "${FREQTRADE_UI_PORT:-8080}:8080" not in compose


def test_native_ui_is_default_and_readonly_proxy_is_optional() -> None:
    proxy = (ROOT / "scripts/read_only_proxy.py").read_text()
    verify = (ROOT / "scripts/verify-runtime.sh").read_text()
    status = (ROOT / "scripts/dev-status.sh").read_text()
    auto_watch = (ROOT / "scripts/auto-watch.py").read_text()
    opener = (ROOT / "scripts/open-analysis.sh").read_text()
    native_opener = (ROOT / "scripts/open-ui.sh").read_text()
    desktop = (ROOT / "scripts/desktop-launch.sh").read_text()
    env_example = (ROOT / ".env.example").read_text()
    starter = (ROOT / "scripts/start-dev.sh").read_text()
    assert '"/api/"' in proxy
    assert '"/openapi.json"' in proxy
    assert 'HTTPStatus.FORBIDDEN' in proxy
    assert '"/analysis.html"' in proxy
    assert "READONLY_PROXY_ENABLED=0" in env_example
    assert "FREQTRADE_START_PATH=/dashboard" in env_example
    assert "AUTO_LOGIN_ENABLED=1" in env_example
    assert "FREQTRADE_BACKEND_PORT" in verify
    assert "READONLY_PROXY_ENABLED" in verify
    assert "analysis-data.json" not in verify
    assert "generate-analysis-data.py" in starter
    assert "proxy: disabled" in status
    assert "/analysis.html" in opener
    assert "scripts/start-dev.sh" in native_opener
    assert "FREQTRADE_START_PATH" in native_opener
    assert "scripts/start-dev.sh" in desktop
    assert "desktop-launch.log" in desktop
    assert "FREQTRADE_START_PATH" in desktop
    assert "auto-watch: running" in status
    assert "auto-watch-status.json" in auto_watch
    assert "api/v1/show_config" in auto_watch or "show_config" in auto_watch
    assert "freqtrade-gemini-optimizer" in starter
    assert "freqtrade-stability-guardian" in starter
    assert "gemini-optimizer: running" in status
    assert "stability-guardian: running" in status


def test_gemini_optimizer_is_advisory_and_redacted() -> None:
    optimizer = (ROOT / "scripts/gemini-optimizer.py").read_text()
    guardian = (ROOT / "scripts/stability-guardian.py").read_text()
    accumulator = (ROOT / "scripts/accumulate-market-data.sh").read_text()
    dataset = (ROOT / "scripts/build-ml-dataset.py").read_text()
    trainer = (ROOT / "scripts/train-ml-models.py").read_text()
    sequence_trainer = (ROOT / "scripts/train-sequence-models.py").read_text()
    sequence_shell = (ROOT / "scripts/train-sequence-models.sh").read_text()
    deep_trainer = (ROOT / "scripts/train-deep-sequence-models.py").read_text()
    deep_shell = (ROOT / "scripts/train-deep-sequence-models.sh").read_text()
    deep_dockerfile = (ROOT / "docker/deep-research.Dockerfile").read_text()
    compose = (ROOT / "docker-compose.yml").read_text()
    analysis_html = (ROOT / "custom_ui/analysis.html").read_text()
    analysis_js = (ROOT / "custom_ui/analysis.js").read_text()
    assert "--approval-mode" in optimizer
    assert '"plan"' in optimizer
    assert "SENSITIVE_KEYS" in optimizer
    assert "[REDACTED]" in optimizer
    assert "不中继、不猜测任何 API key" in optimizer
    assert "近3个月证据包" in optimizer
    assert "missing_3_month_market_evidence" in optimizer
    assert "只允许生成 update_strategy_flow 动作" in optimizer
    assert "only user_data/datugou_flow.autopilot.json may be auto-written" in optimizer
    assert "gemini-optimizer-report.md" in optimizer
    assert "gemini-optimizer-contract.json" in optimizer
    assert "gemini-optimizer-request.json" in optimizer
    assert "gemini-optimizer-response.json" in optimizer
    assert "gemini-optimizer-actions.jsonl" in optimizer
    assert "gemini-optimizer-backlog.json" in optimizer
    assert "datugou_flow.autopilot.json" in optimizer
    assert "update_strategy_flow" in optimizer
    assert "PARAMETER_BOUNDS" in optimizer
    assert "apply_strategy_flow" in optimizer
    assert "GEMINI_AUTOMATION_ENABLED" in optimizer
    assert "GEMINI_AUTOMATION_MIN_CONFIDENCE" in optimizer
    assert "gemini_evidence_pack.json" in optimizer
    assert "training_report.json" in optimizer
    assert "latest_signals.json" in optimizer
    assert "pred 信号" in optimizer
    assert "download-data" in accumulator
    assert "--days" in accumulator
    assert "ML_LOOKBACK_DAYS:-90" in accumulator
    assert "label_return_5_open_pct" in dataset
    assert "label_return_12_open_pct" in dataset
    assert "label_barrier_long_12" in dataset
    assert "ML_BARRIER_TAKE_PROFIT_PCT" in dataset
    assert "future_entry_open" in dataset
    assert "open.shift(-1)" in dataset
    assert "rank_label_return_5" in dataset
    assert "features_labels_1h_clean.csv" in dataset
    assert "data_quality_report.json" in dataset
    assert "zero_volume_rate" in dataset
    assert "min_volume_ratio_24_median" in dataset
    assert "return_6_excess" in dataset
    assert "cs_rank_return_6" in dataset
    assert "cs_rank_volume_ratio_24" in dataset
    assert "atr_14_pct" in dataset
    assert "label_return_5_atr" in dataset
    assert "label_triclass_5_atr" in dataset
    assert "ML_TRICLASS_UP_ATR" in dataset
    assert "ML_MIN_ATR_PCT_FOR_LABEL" in dataset
    assert "finite_series" in dataset
    assert "atr_normalized_regression" in dataset
    assert "triclass_classification" in dataset
    assert "HistGradientBoostingRegressor" in trainer
    assert "HistGradientBoostingClassifier" in trainer
    assert "balanced_accuracy_score" in trainer
    assert "CLEAN_INPUT_PATH" in trainer
    assert "data_quality_report.json" in trainer
    assert "return_6_excess" in trainer
    assert "cs_rank_return_6" in trainer
    assert "atr_14_pct" in trainer
    assert "TARGET_RETURN_ATR" in trainer
    assert "TARGET_TRICLASS" in trainer
    assert "atr_normalized_5_regression" in trainer
    assert "atr_triclass_5_classification" in trainer
    assert "pred_return_5_open_pct" in trainer
    assert "pred_up_probability" in trainer
    assert "pred_rank_score" in trainer
    assert "long_horizon_12_regression" in trainer
    assert "barrier_long_12_classification" in trainer
    assert "top_long_candidates" in trainer
    assert "deployment_gate" in trainer
    assert "research_only_do_not_trade" in trainer
    assert "regression_corr_at_least_0_10" in trainer
    framework = (ROOT / "docs/AI_ML_TRADING_FRAMEWORK.md").read_text()
    assert "出题(define labels) -> 教材(build factors) -> 学习(train models) -> 上岗(output gated signals)" in framework
    assert "label_return_5_open_pct = open.shift(-6) / open.shift(-1) - 1" in framework
    assert "Regression: predict exact return" in framework
    assert "Binary classification: predict up/down" in framework
    assert "Cross-sectional ranking: compare pairs" in framework
    assert "LSTM: short-term sequence memory" in framework
    assert "Transformer: attention over longer feature windows" in framework
    assert "deployment_gate.passed == true" in framework
    assert "标签定目标，因子给信息，模型学映射，pred 出信号" in framework
    assert "sequence_window_gradient_boosting_baseline" in sequence_trainer
    assert "ML_SEQUENCE_LOOKBACK_CANDLES" in sequence_trainer
    assert "seq_pred_return_5_open_pct" in sequence_trainer
    assert "seq_pred_up_probability" in sequence_trainer
    assert "seq_pred_rank_score" in sequence_trainer
    assert "skipped_missing_torch" in sequence_trainer
    assert '"lstm"' in sequence_trainer
    assert '"transformer"' in sequence_trainer
    assert "sequence_report.json" in sequence_shell
    assert "deep-research" in compose
    assert "docker/deep-research.Dockerfile" in compose
    assert "FREQTRADE__EXCHANGE__KEY" not in compose.split("deep-research:", 1)[1].split("qlib-research:", 1)[0]
    assert "torch --index-url https://download.pytorch.org/whl/cpu" in deep_dockerfile
    assert "LSTMRegressor" in deep_trainer
    assert "TransformerRegressor" in deep_trainer
    assert "pytorch_lstm_transformer_sequence" in deep_trainer
    assert "deep_ensemble_pred_return_5_open_pct" in deep_trainer
    assert "cross_sectional_ranking" in deep_trainer
    assert "deep_sequence_report.json" in deep_shell
    assert "时序模型层" in analysis_html
    assert "LSTM / Transformer" in analysis_html
    assert "sequence-candidates" in analysis_html
    assert "deep-candidates" in analysis_html
    assert "renderSequence" in analysis_js
    assert "renderDeepSequence" in analysis_js
    assert "Gemini 自动优化" in analysis_html
    assert "autopilot-params" in analysis_html
    assert "renderAutopilot" in analysis_js
    assert "缺 torch" in analysis_js
    qlib_prepare = (ROOT / "scripts/prepare-qlib-data.py").read_text()
    qlib_smoke = (ROOT / "scripts/run-qlib-smoke.py").read_text()
    qlib_prepare_shell = (ROOT / "scripts/prepare-qlib-data.sh").read_text()
    qlib_dockerfile = (ROOT / "docker/qlib-research.Dockerfile").read_text()
    qlib_build_shell = (ROOT / "scripts/build-qlib-research-image.sh").read_text()
    qlib_dump_shell = (ROOT / "scripts/run-qlib-dump.sh").read_text()
    qlib_qrun_shell = (ROOT / "scripts/run-qlib-qrun.sh").read_text()
    assert "vendor/qlib" in qlib_smoke
    assert "qlib_fusion_report.json" in qlib_prepare
    assert "qlib_okx_lgbm_config.yaml" in qlib_prepare
    assert "QLIB_RUNTIME_ROOT" in qlib_prepare
    assert "runtime_path" in qlib_prepare
    assert "LGBModel" in qlib_prepare
    assert "TopkDropoutStrategy" in qlib_prepare
    assert "DataHandlerLP" in qlib_prepare
    assert "label_return_5_open_pct" in qlib_prepare
    assert "Freqtrade remains the only trading engine" in qlib_prepare
    assert "dump_bin.py dump_all" in qlib_prepare
    assert "scripts/run-qlib-dump.sh" in qlib_prepare_shell
    assert "codex-primary-runtime" in qlib_prepare_shell
    assert "QLIB_RUNTIME_ROOT=/workspace" in qlib_prepare_shell
    assert "qlib_import_available" in qlib_smoke
    assert "codex-primary-runtime" in (ROOT / "scripts/run-qlib-smoke.sh").read_text()
    assert "pyqlib" in qlib_dockerfile or "pip install /workspace/vendor/qlib" in qlib_dockerfile
    assert "lightgbm" in qlib_dockerfile
    assert "pip install /workspace/vendor/qlib" in qlib_dockerfile
    assert "docker build -f docker/qlib-research.Dockerfile" in qlib_build_shell
    assert "docker run --rm freqtrade-deploy-qlib-research:local" in qlib_build_shell
    assert "docker create --name" in qlib_dump_shell
    assert "docker cp output/qlib/okx_1h/csv" in qlib_dump_shell
    assert "docker cp \"$CONTAINER\":/workspace/output/qlib/okx_1h/qlib_bin" in qlib_dump_shell
    assert "dump_bin.py dump_all" in qlib_dump_shell
    assert "qrun" in qlib_qrun_shell
    assert "docker cp output/qlib/okx_1h" in qlib_qrun_shell
    assert "qlib-qrun.log" in qlib_qrun_shell
    assert "GUARDIAN_RUNTIME_HOURS" in guardian
    assert "GUARDIAN_FAILURE_THRESHOLD" in guardian
    assert "docker compose up -d" in guardian
    assert 'os.getenv("GUARDIAN_RUNTIME_HOURS", "0")' in guardian
    assert "ensure_docker_runtime" in guardian
    assert "freqtrade-caffeinate" in guardian
    assert "start-auto-watch.sh" in guardian


def test_aliyun_pull_deployment_is_server_safe() -> None:
    bootstrap = (ROOT / "deploy/aliyun/bootstrap.sh").read_text()
    systemd = (ROOT / "deploy/aliyun/install-systemd.sh").read_text()
    docs = (ROOT / "deploy/aliyun/README.md").read_text()
    env = (ROOT / ".env.server.example").read_text()
    ignore = (ROOT / ".gitignore").read_text()
    dockerignore = (ROOT / ".dockerignore").read_text()
    compose = (ROOT / "docker-compose.yml").read_text()

    assert "https://github.com/chenshiyue17-create/mmmmm.git" in bootstrap
    assert "OKX_SANDBOX_MODE=1" in bootstrap
    assert "scripts/security-leak-check.sh" in bootstrap
    assert "systemctl enable freqtrade-deploy" in systemd
    assert "ExecStart=/usr/bin/env bash" in systemd
    assert "ssh -L 8080:127.0.0.1:8080" in docs
    assert "OKX_SANDBOX_MODE=1" in env
    assert "GEMINI_OPTIMIZER_ENABLED=0" in env
    assert "GEMINI_AUTOMATION_ENABLED=0" in env
    assert "!.env.server.example" in ignore
    assert "output/" in dockerignore
    assert "profiles:" in compose
    assert "research" in compose


def test_hybrid_server_local_split_keeps_trading_independent() -> None:
    docs = (ROOT / "docs/HYBRID_SERVER_LOCAL_ARCHITECTURE.md").read_text()
    sync = (ROOT / "scripts/sync-research-to-server.sh").read_text()
    server_env = (ROOT / ".env.server.example").read_text()

    assert "服务器只负责 24 小时交易执行" in docs
    assert "本地断网、关机、重启，不影响服务器继续交易" in docs
    assert "GEMINI_OPTIMIZER_ENABLED=0" in server_env
    assert "GEMINI_AUTOMATION_ENABLED=0" in server_env
    assert "ML_SIGNAL_FILTER_ENABLED=0" in server_env
    assert "security-leak-check.sh" in sync
    assert "user_data/datugou_flow.autopilot.json" in sync
    assert "secrets_synced\": false" in sync
    assert ".env" not in sync.split("FILES=", 1)[1].split(")", 1)[0]


def test_import_research_flow_reuses_existing_output_when_source_missing(tmp_path: Path) -> None:
    import subprocess

    existing = tmp_path / "datugou_flow.json"
    existing.write_text(
        json.dumps(
            {
                "schema_version": "strategy-flow/v1",
                "name": "datugou_profit_flow",
                "version": "server-cache",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            "scripts/import-research-flow.py",
            "--flow",
            str(tmp_path / "missing.yaml"),
            "--output",
            str(existing),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "reusing existing" in result.stdout


def test_local_auto_login_file_is_generated() -> None:
    import json
    import subprocess

    subprocess.run(
        ["python3", "scripts/generate-local-login.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads((ROOT / "custom_ui/local-login.json").read_text())
    assert payload["enabled"] is True
    assert payload["url"].startswith("http://localhost:")
    assert payload["username"] == "freqtrade"
    assert payload["password"]


def test_exchange_switcher_supports_okx_and_binance() -> None:
    switcher = (ROOT / "scripts/switch-exchange.py").read_text()
    compose = (ROOT / "docker-compose.yml").read_text()
    assert '"okx"' in switcher
    assert '"binance"' in switcher
    assert "BINANCE_KEY" in compose
    assert "OKX_KEY" in compose
    assert "enable_ws" in switcher
    compose = (ROOT / "docker-compose.yml").read_text()
    patch = (ROOT / "runtime/sitecustomize.py").read_text()
    assert "PYTHONPATH: /freqtrade/runtime" in compose
    assert "qlib-research:" in compose
    assert "docker/qlib-research.Dockerfile" in compose
    assert "./vendor:/workspace/vendor:ro" in compose
    assert "FREQTRADE__EXCHANGE__KEY" not in compose.split("qlib-research:", 1)[1].split("freqtrade:", 1)[0]
    assert "OKX_SANDBOX_MODE" in compose
    assert "ML_SIGNAL_FILTER_ENABLED" in compose
    assert "ML_SIGNAL_PATH" in compose
    assert "set_sandbox_mode(True)" in patch


def test_strategy_has_guarded_ml_signal_hook() -> None:
    strategy = (ROOT / "user_data/strategies/DatugouBreakoutStrategy.py").read_text()
    assert "ML_SIGNAL_FILTER_ENABLED" in strategy
    assert "ML_SIGNAL_PATH" in strategy
    assert "latest_signals.json" in strategy
    assert "deployment_gate" in strategy
    assert "gate.get(\"passed\")" in strategy
    assert "research_long_candidates" in strategy
    assert "top_long_candidates" in strategy
    assert "pred_signal" in strategy
    assert "datugou_breakout_ml_gate" in strategy
    assert "self._ml_pair_allowed(pair)" in strategy


def test_okx_secrets_use_keychain_helpers() -> None:
    setter = (ROOT / "scripts/set-okx-keychain.sh").read_text()
    exporter = (ROOT / "scripts/export-keychain-secrets.sh").read_text()
    checker = (ROOT / "scripts/check-okx-private-api.sh").read_text()
    gitignore = (ROOT / ".gitignore").read_text()
    assert "security add-generic-password" in setter
    assert "security find-generic-password" in exporter
    assert "OKX_PASSWORD" in setter
    assert "--prompt-password" in setter
    assert "read -r -s OKX_PASSWORD" in setter
    assert "test-pairlist" in checker
    assert "secrets/" in gitignore


def test_okx_sandbox_check_does_not_persist_secrets() -> None:
    checker = (ROOT / "scripts/check-okx-sandbox-api.py").read_text()
    wrapper = (ROOT / "scripts/check-okx-sandbox-api.sh").read_text()
    assert "set_sandbox_mode(True)" in checker
    assert "x-simulated-trading" in checker
    assert "live_readonly_balance" in checker
    assert "api_key_environment_mismatch" in checker
    assert "okx-sandbox-api-check.json" in checker
    generator = (ROOT / "scripts/generate-okx-balance-ui.py").read_text()
    assert "okx-sandbox-balance.js" in generator
    assert "data-okx-sandbox-balance" in generator
    assert "OKX 模拟盘余额" in generator
    assert "OKX_KEY" in wrapper
    assert "99399" not in checker
    assert "7a947" not in checker


def test_simulation_test_runner_generates_reports() -> None:
    runner = (ROOT / "scripts/run-simulation-test.sh").read_text()
    dryrun = (ROOT / "scripts/run-dryrun-trade-test.py").read_text()
    compose = (ROOT / "docker-compose.yml").read_text()
    assert "simulation-test-report.json" in runner
    assert "simulation-test-report.md" in runner
    assert "check-okx-sandbox-api.sh" in runner
    assert "run-dryrun-trade-test.sh" in runner
    assert "forceenter" in dryrun
    assert "forceexit" in dryrun
    assert "OKX_SANDBOX_MODE=1" in dryrun
    assert "virtual_runtime_ok" in runner
    assert "OKX sandbox" in runner
    assert "./output:/freqtrade/output" in compose


def test_security_leak_check_redacts_secret_values() -> None:
    checker = (ROOT / "scripts/security-leak-check.py").read_text()
    wrapper = (ROOT / "scripts/security-leak-check.sh").read_text()
    assert "EXTRA_SECRET" in checker
    assert "secret_name" in checker
    assert "secret.value" in checker
    assert "findings.append" in checker
    assert "eval \"$(scripts/export-keychain-secrets.sh)\"" in wrapper


def test_only_exchange_api_scope_is_allowed() -> None:
    import subprocess

    result = subprocess.run(
        ["scripts/check-api-scope.sh"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "only exchange APIs are enabled" in result.stdout


def test_official_freqtrade_commands_are_wired() -> None:
    freqtrade = (ROOT / "scripts/freqtrade.sh").read_text()
    validate = (ROOT / "scripts/validate-config.sh").read_text()
    download = (ROOT / "scripts/download-data.sh").read_text()
    backtest = (ROOT / "scripts/backtest.sh").read_text()
    assert 'docker compose run --rm freqtrade "$@"' in freqtrade
    assert "show-config" in validate
    assert 'config["strategy"] == "DatugouBreakoutStrategy"' in validate
    assert "DatugouBreakoutStrategy" in validate
    assert "download-data" in download
    assert "backtesting" in backtest
    assert "--strategy DatugouBreakoutStrategy" in backtest
