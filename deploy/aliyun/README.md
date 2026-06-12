# Aliyun Server Deployment

This deployment keeps Freqtrade bound to `127.0.0.1:8080` on the server. Do not open the Freqtrade port to the public internet. Use an Aliyun remote session or an SSH tunnel from your computer.

## Server Pull Deployment

Run on the Aliyun server:

```bash
export REPO_URL=https://github.com/chenshiyue17-create/mmmmm.git
export BRANCH=main
export APP_DIR=/opt/freqtrade-deploy
bash -lc "$(curl -fsSL https://raw.githubusercontent.com/chenshiyue17-create/mmmmm/main/deploy/aliyun/bootstrap.sh)"
```

The first run creates:

```text
/opt/freqtrade-deploy/.env
```

Edit it on the server:

```bash
nano /opt/freqtrade-deploy/.env
```

Fill only server-local secrets:

```text
FT_API_PASSWORD
FT_JWT_SECRET_KEY
FT_WS_TOKEN
OKX_KEY
OKX_SECRET
OKX_PASSWORD
```

Keep this for the first server run:

```text
OKX_SANDBOX_MODE=1
```

Then start:

```bash
sudo systemctl start freqtrade-deploy
sudo systemctl status freqtrade-deploy --no-pager
cd /opt/freqtrade-deploy
scripts/dev-status.sh
```

## Open UI From Your Computer

Use SSH tunnel:

```bash
ssh -L 8080:127.0.0.1:8080 root@YOUR_SERVER_IP
```

Then open:

```text
http://localhost:8080/analysis.html
```

## Manual Stop Only

The guardian runs until manual stop:

```bash
sudo systemctl stop freqtrade-deploy
```

Manual restart:

```bash
sudo systemctl restart freqtrade-deploy
```

## Upgrade From GitHub

Run on the server:

```bash
cd /opt/freqtrade-deploy
git pull --ff-only
sudo systemctl restart freqtrade-deploy
```

## Safety Rules

- Do not commit `.env`.
- Do not commit OKX keys, cookies, logs, SQLite databases, or `output/`.
- Do not expose port `8080` publicly in the Aliyun security group.
- Keep OKX withdrawal permission disabled.
- Start with OKX sandbox before any live review.
