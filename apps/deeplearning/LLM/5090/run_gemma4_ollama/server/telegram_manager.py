"""Telegram configuration and child-process ownership for the web service."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit


FIELDS = ("TELEGRAM_BOT_TOKEN", "LLM_API_URL", "GEMMA4_USER_ID", "GEMMA4_PASSWORD",
          "ALLOWED_TELEGRAM_USER_IDS", "TELEGRAM_BOT_USERNAMES")
SECRETS = {"TELEGRAM_BOT_TOKEN", "GEMMA4_PASSWORD"}


class TelegramManager:
    def __init__(self, app_dir: Path, log_dir: Path, port: int):
        self.bot_dir = app_dir / "telegram"
        self.config_file = self.bot_dir / "web_config.json"
        self.log_file = log_dir / "telegram-bot.log"
        self.port = port
        self.lock = threading.RLock()
        self.process = None
        self.lock_handle = None
        self.message = "중지됨"
        self.applied = None
        self.legacy = None

    def config(self):
        if self.legacy is None:
            values = {key: os.environ.get(key, "") for key in FIELDS}
            config = Path(os.environ.get("TELEGRAM_CONFIG_FILE", self.bot_dir / "this_conf_keys.sh")).expanduser().resolve()
            if os.environ.get("TELEGRAM_CONFIG_FILE") and not config.is_file():
                raise ValueError(f"Telegram 설정 파일을 찾을 수 없습니다: {config}")
            if config.is_file():
                # This is the existing trusted local shell config, never web input.
                try:
                    result = subprocess.run(
                        ["bash", "-c", 'set -a; source "$1" set >/dev/null && env -0', "telegram-config", str(config)],
                        cwd=config.parent, capture_output=True, timeout=10, check=True,
                    )
                except (OSError, subprocess.SubprocessError) as exc:
                    # Shell stderr can include credentials; report only the path.
                    raise ValueError(f"Telegram 설정 파일 읽기 실패: {config} (bash 실행 환경과 셸 파일 문법을 확인하세요.)") from exc
                exported = dict(item.split(b"=", 1) for item in result.stdout.split(b"\0") if b"=" in item)
                values.update({key: exported[key.encode()].decode() for key in FIELDS if key.encode() in exported})
            values["LLM_API_URL"] = values["LLM_API_URL"] or f"http://127.0.0.1:{self.port}/api/generate"
            values["TELEGRAM_BOT_USERNAMES"] = values["TELEGRAM_BOT_USERNAMES"] or "berepi_gemma_bot,berepi_gemma_model,model_gemma"
            self.legacy = values
        values = dict(self.legacy)
        if self.config_file.exists():
            saved = json.loads(self.config_file.read_text(encoding="utf-8"))
            if not isinstance(saved, dict):
                raise ValueError("Telegram 설정 파일 형식이 잘못되었습니다.")
            values.update({key: saved[key] for key in FIELDS if key in saved})
        return values

    def reload(self):
        """Explicit refresh re-reads shell/environment settings, then web overrides."""
        with self.lock:
            previous = self.legacy
            self.legacy = None
            try:
                return self.status()
            except Exception:
                self.legacy = previous
                raise

    def save(self, changes):
        with self.lock:
            if not isinstance(changes, dict) or set(changes) - set(FIELDS):
                raise ValueError("지원하지 않는 Telegram 설정입니다.")
            values = self.config()
            for key, value in changes.items():
                if not isinstance(value, str) or len(value) > 4096 or "\0" in value or "\n" in value or "\r" in value:
                    raise ValueError(f"잘못된 설정 값: {key}")
                # Empty password fields mean keep the stored secret.
                if key in SECRETS and not value:
                    continue
                values[key] = value if key in SECRETS else value.strip()
            url = urlsplit(values["LLM_API_URL"])
            if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
                raise ValueError("LLM API URL은 인증정보 없는 http/https 주소여야 합니다.")
            if values["ALLOWED_TELEGRAM_USER_IDS"] and not re.fullmatch(r"\d+(\s*,\s*\d+)*", values["ALLOWED_TELEGRAM_USER_IDS"]):
                raise ValueError("허용 사용자 ID는 숫자를 쉼표로 구분해 입력하세요.")
            token = values["TELEGRAM_BOT_TOKEN"]
            if token and not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token):
                raise ValueError("Telegram 봇 토큰 형식이 잘못되었습니다.")
            self.bot_dir.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(dir=self.bot_dir, prefix=".web-config-")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump(values, stream, ensure_ascii=False, indent=2)
                os.replace(name, self.config_file)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
            self.message = "설정을 저장했습니다. 실행 중이면 재시작하세요."
            return self.status()

    def _release(self):
        if self.lock_handle is not None:
            self.lock_handle.close()
            self.lock_handle = None

    def _acquire(self):
        lock_file = self.bot_dir / "logs" / "bot.lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        handle = open(lock_file, "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return None
        return handle

    def status(self):
        with self.lock:
            values = self.config()
            running = self.process is not None and self.process.poll() is None
            if self.process is not None and not running:
                self.message = f"봇 종료 (코드 {self.process.returncode}). 서버 로그를 확인하세요."
                self.process = None
                self._release()
            external = False
            if not running:
                probe = self._acquire()
                external = probe is None
                if probe is not None:
                    probe.close()
            return {
                "running": running, "external_running": external,
                "pid": self.process.pid if running else None,
                "message": self.message,
                "restart_required": running and self.applied != values,
                "config": {key: value for key, value in values.items() if key not in SECRETS},
                "secrets_set": {key: bool(values[key]) for key in SECRETS},
                "config_sources": {
                    "shell": str(Path(os.environ.get("TELEGRAM_CONFIG_FILE", self.bot_dir / "this_conf_keys.sh")).expanduser().resolve()),
                    "web": str(self.config_file.resolve()),
                    "web_exists": self.config_file.is_file(),
                },
            }

    def start(self):
        with self.lock:
            state = self.status()
            if state["running"]:
                return state
            values = self.config()
            if not values["TELEGRAM_BOT_TOKEN"] or values["TELEGRAM_BOT_TOKEN"] == "***":
                raise ValueError("Telegram 봇 토큰을 먼저 저장하세요.")
            self.lock_handle = self._acquire()
            if self.lock_handle is None:
                raise ValueError("다른 서비스가 봇을 실행 중입니다. 해당 서비스에서 먼저 중지하세요.")
            try:
                python = os.environ.get("TELEGRAM_PYTHON")
                if not python:
                    python = next((str(p) for p in (self.bot_dir / ".venv/bin/python", self.bot_dir / "install/bin/python") if p.is_file()), None)
                python = python or shutil.which("python3")
                if not python:
                    raise ValueError("Telegram용 Python을 찾을 수 없습니다.")
                env = dict(os.environ, **values)
                self.log_file.parent.mkdir(parents=True, exist_ok=True)
                with self.log_file.open("ab") as output:
                    kwargs = {"pass_fds": (self.lock_handle.fileno(),)} if os.name != "nt" else {}
                    self.process = subprocess.Popen([python, "-u", str(self.bot_dir / "bot.py")],
                                                    cwd=self.bot_dir, env=env, stdout=output,
                                                    stderr=subprocess.STDOUT, **kwargs)
                self.applied = values
                self.message = "봇 프로세스를 시작했습니다."
                time.sleep(0.3)
                return self.status()
            except Exception:
                self._release()
                raise

    def stop(self):
        with self.lock:
            if self.process is not None:
                if self.process.poll() is None:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=2)
                self.process = None
            self._release()
            self.message = "중지됨"

    def restart(self):
        with self.lock:
            self.stop()
            return self.start()
