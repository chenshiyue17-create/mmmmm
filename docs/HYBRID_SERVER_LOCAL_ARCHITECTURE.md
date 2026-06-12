# Hybrid Server/Local Architecture

目标：

- 服务器只负责 24 小时交易执行。
- 本地只负责数据积累、训练、Qlib/Gemini 研究和参数生成。
- 本地断网、关机、重启，不影响服务器继续交易。

## 分层

### Server Execution Node

运行位置：阿里云服务器。

职责：

- Docker/Freqtrade 交易主进程。
- OKX sandbox/demo 或后续人工审核后的交易环境。
- auto-watch 实时状态。
- stability guardian 永久守护。
- systemd 开机自启。
- 本地服务器 `.env` 保存交易所 API。

服务器默认关闭研究计算：

```text
GEMINI_OPTIMIZER_ENABLED=0
GEMINI_AUTOMATION_ENABLED=0
ML_SIGNAL_FILTER_ENABLED=0
```

这保证交易不依赖本地机器，也不依赖 Gemini/Qlib 是否在线。

### Local Research Node

运行位置：本地 Mac / 移动硬盘项目目录。

职责：

- 下载和清洗市场数据。
- 训练 ML / sequence / deep sequence / Qlib。
- 调用本地 Gemini CLI 生成候选优化。
- 只输出有限、可验证、可回滚的策略覆盖参数。

本地可同步到服务器的小文件：

```text
user_data/datugou_flow.json
user_data/datugou_flow.autopilot.json
user_data/strategies/DatugouBreakoutStrategy.py
user_data/config.json
```

不同步：

```text
.env
OKX keys
logs/
output/
SQLite databases
raw market datasets
cookies
browser/session data
```

## 同步方式

从本地运行：

```bash
cd /Volumes/NINJAV/Codex_Projects/freqtrade-deploy
SERVER_HOST=YOUR_SERVER_IP SERVER_USER=root scripts/sync-research-to-server.sh
```

默认不重启服务器交易进程，只同步文件和刷新分析快照。

需要让策略源码或配置立即重载时才运行：

```bash
SERVER_HOST=YOUR_SERVER_IP SERVER_USER=root RESTART_AFTER_SYNC=1 scripts/sync-research-to-server.sh
```

## 24 小时交易保证边界

服务器可以自动恢复：

- Freqtrade 容器退出。
- Docker/Colima-like runtime 短暂不可用。
- auto-watch 中断。
- stability guardian 检查失败。
- 服务器重启后 systemd 拉起服务。

服务器不依赖：

- 本地 Mac 在线。
- 本地 SSH 会话保持。
- 本地数据训练完成。
- 本地 Gemini CLI 在线。

无法由软件完全保证：

- 服务器断电。
- 云厂商宿主机故障。
- OKX 网络或 API 大面积不可用。
- 账户/API 权限被交易所撤销。

## 操作原则

1. 交易在服务器跑。
2. 研究在本地跑。
3. 本地只同步小文件参数，不同步密钥和数据湖。
4. 服务器的 `.env` 永远只在服务器本机维护。
5. 切正式实盘前，单独做人工审核。
