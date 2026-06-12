#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "output" / "stability-guardian-status.json"
EVENTS_PATH = ROOT / "output" / "stability-guardian-events.jsonl"
LOG_PATH = ROOT / "logs" / "stability-guardian.log"
AUTO_WATCH_STATUS = ROOT / "output" / "auto-watch-status.json"
FREQTRADE_LOG_SESSION = "freqtrade-deploy"
AUTO_WATCH_SESSION = "freqtrade-auto-watch"
GEMINI_SESSION = "freqtrade-gemini-optimizer"
CAFFEINATE_SESSION = "freqtrade-caffeinate"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env_file() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def export_keychain_secrets() -> None:
    script = ROOT / "scripts" / "export-keychain-secrets.sh"
    if not script.exists():
        return
    result = run(["bash", str(script)], timeout=20)
    if result.returncode != 0:
        return
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line.startswith("export ") or "=" not in line:
            continue
        key, value = line[len("export ") :].split("=", 1)
        os.environ[key] = value.strip().strip("'\"")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_event(payload: dict[str, Any]) -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def run(command: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True, timeout=timeout)


def run_shell(command: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", "-lc", command], cwd=ROOT, check=False, capture_output=True, text=True, timeout=timeout)


def api_ping() -> tuple[bool, str]:
    base_url = os.getenv("FT_API_URL", "http://127.0.0.1:8080").rstrip("/")
    username = os.getenv("FT_API_USERNAME", "freqtrade")
    password = os.getenv("FT_API_PASSWORD", "")
    request = urllib.request.Request(f"{base_url}/api/v1/ping")
    token = b64encode(f"{username}:{password}".encode()).decode()
    request.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
        return '"pong"' in body or "pong" in body, body[:200]
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"{type(exc).__name__}: {exc}"[:300]


def screen_has(name: str) -> bool:
    result = run(["screen", "-list"], timeout=10)
    return f".{name}" in result.stdout


def docker_running() -> bool:
    result = run(["docker", "compose", "ps", "--status", "running"], timeout=30)
    return result.returncode == 0 and "freqtrade-dryrun" in result.stdout


def ensure_docker_runtime() -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    docker_info = run(["docker", "info"], timeout=20)
    if docker_info.returncode == 0:
        return {"ok": True, "actions": actions}
    if run(["bash", "-lc", "command -v colima"], timeout=10).returncode == 0:
        colima_start = run(["colima", "start", "--cpu", "4", "--memory", "8", "--disk", "60", "--mount", "/Volumes/NINJAV:w"], timeout=240)
        actions.append({"action": "colima start", "returncode": colima_start.returncode})
        context = run(["docker", "context", "use", "colima"], timeout=20)
        actions.append({"action": "docker context use colima", "returncode": context.returncode})
    docker_info_after = run(["docker", "info"], timeout=20)
    actions.append({"action": "docker info", "returncode": docker_info_after.returncode})
    return {"ok": docker_info_after.returncode == 0, "actions": actions}


def start_screen_if_missing(name: str, command: str, timeout: int = 30) -> dict[str, Any]:
    if screen_has(name):
        return {"action": f"{name} already running", "returncode": 0}
    result = run_shell(f"screen -dmS {name} bash -lc {json.dumps(command)}", timeout=timeout)
    return {"action": f"start {name}", "returncode": result.returncode}


def start_caffeinate_if_available() -> dict[str, Any]:
    if run(["bash", "-lc", "command -v caffeinate"], timeout=10).returncode != 0:
        return {"action": "caffeinate unavailable", "returncode": 0}
    return start_screen_if_missing(CAFFEINATE_SESSION, "caffeinate -dimsu", timeout=10)


def auto_watch_fresh(max_age_seconds: int) -> tuple[bool, str]:
    if not AUTO_WATCH_STATUS.exists():
        return False, "auto-watch status file missing"
    try:
        payload = json.loads(AUTO_WATCH_STATUS.read_text(encoding="utf-8"))
        checked_at = payload.get("checked_at")
        if not checked_at:
            return False, "auto-watch checked_at missing"
        checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - checked).total_seconds()
        return age <= max_age_seconds and bool(payload.get("ok")), f"age={age:.1f}s ok={payload.get('ok')}"
    except Exception as exc:  # noqa: BLE001 - daemon must report and recover.
        return False, f"{type(exc).__name__}: {exc}"[:300]


def recover(reason: str) -> dict[str, Any]:
    started_at = now_utc()
    actions: list[dict[str, Any]] = []
    runtime = ensure_docker_runtime()
    actions.append({"action": "ensure docker runtime", "ok": runtime["ok"], "details": runtime["actions"]})
    export_keychain_secrets()
    compose = run(["docker", "compose", "up", "-d"], timeout=180)
    actions.append({"action": "docker compose up -d", "returncode": compose.returncode})
    actions.append(
        start_screen_if_missing(
            FREQTRADE_LOG_SESSION,
            f"cd {json.dumps(str(ROOT))} && docker compose logs -f freqtrade 2>&1 | tee -a logs/freqtrade-compose.log",
            timeout=20,
        )
    )
    watch = run(["bash", "scripts/start-auto-watch.sh"], timeout=120)
    actions.append({"action": "start-auto-watch", "returncode": watch.returncode})
    if os.getenv("GEMINI_OPTIMIZER_ENABLED", "1") == "1":
        gemini = run(["bash", "scripts/start-gemini-optimizer.sh"], timeout=30)
        actions.append({"action": "start-gemini-optimizer", "returncode": gemini.returncode})
    actions.append(start_caffeinate_if_available())
    analysis = run(["python3", "scripts/generate-analysis-data.py"], timeout=60)
    actions.append({"action": "generate-analysis-data", "returncode": analysis.returncode})
    return {"recovered_at": started_at, "reason": reason, "actions": actions}


def snapshot(consecutive_failures: int) -> dict[str, Any]:
    max_status_age = int(os.getenv("GUARDIAN_MAX_AUTO_WATCH_AGE_SECONDS", "180"))
    ping_ok, ping_detail = api_ping()
    docker_ok = docker_running()
    log_screen_ok = screen_has(FREQTRADE_LOG_SESSION)
    watch_screen_ok = screen_has(AUTO_WATCH_SESSION)
    gemini_required = os.getenv("GEMINI_OPTIMIZER_ENABLED", "1") == "1"
    gemini_screen_ok = screen_has(GEMINI_SESSION)
    caffeinate_required = run(["bash", "-lc", "command -v caffeinate"], timeout=10).returncode == 0
    caffeinate_screen_ok = screen_has(CAFFEINATE_SESSION)
    watch_fresh, watch_detail = auto_watch_fresh(max_status_age)
    ok = (
        ping_ok
        and docker_ok
        and log_screen_ok
        and watch_screen_ok
        and watch_fresh
        and (gemini_screen_ok or not gemini_required)
        and (caffeinate_screen_ok or not caffeinate_required)
    )
    return {
        "checked_at": now_utc(),
        "ok": ok,
        "mode": "okx_sandbox_guardian",
        "api_ping": ping_ok,
        "api_detail": ping_detail,
        "docker_running": docker_ok,
        "freqtrade_log_screen": log_screen_ok,
        "auto_watch_screen": watch_screen_ok,
        "auto_watch_fresh": watch_fresh,
        "auto_watch_detail": watch_detail,
        "gemini_optimizer_required": gemini_required,
        "gemini_optimizer_screen": gemini_screen_ok,
        "caffeinate_required": caffeinate_required,
        "caffeinate_screen": caffeinate_screen_ok,
        "consecutive_failures": consecutive_failures,
    }


def main() -> int:
    load_env_file()
    export_keychain_secrets()
    once = os.getenv("GUARDIAN_ONCE", "0") == "1"
    interval = int(os.getenv("GUARDIAN_INTERVAL_SECONDS", "30"))
    failure_threshold = int(os.getenv("GUARDIAN_FAILURE_THRESHOLD", "3"))
    runtime_hours = float(os.getenv("GUARDIAN_RUNTIME_HOURS", "0"))
    deadline = time.monotonic() + runtime_hours * 3600 if runtime_hours > 0 else None
    consecutive_failures = 0

    while True:
        current = snapshot(consecutive_failures)
        if current["ok"]:
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            current["consecutive_failures"] = consecutive_failures
            if consecutive_failures >= failure_threshold:
                current["recovery"] = recover(json.dumps(current, ensure_ascii=False))
                consecutive_failures = 0
        write_json(STATE_PATH, current)
        append_event(current)
        if once:
            return 0 if current["ok"] else 1
        if deadline is not None and time.monotonic() >= deadline:
            final_state = {"checked_at": now_utc(), "ok": True, "event": "guardian_runtime_completed", "runtime_hours": runtime_hours}
            write_json(STATE_PATH, final_state)
            append_event(final_state)
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
