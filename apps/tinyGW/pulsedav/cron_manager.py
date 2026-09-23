"""Replace this installation's selected cron jobs, preserving unrelated entries."""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path


def merge_crontab(existing: str, lines: list[str], app_dir: Path, watchdog: bool) -> str:
    retained = []
    for line in existing.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or re.match(r"^\s*\w+\s*=", line):
            retained.append(line)
            continue
        try:
            tokens = shlex.split(line.replace(r"\%", "%"))
        except ValueError:
            retained.append(line)
            continue
        same_app = str(app_dir) in tokens or str(app_dir / "sender.py") in tokens
        sender = "sender.py" in tokens or str(app_dir / "sender.py") in tokens
        same_kind = ("--gateway-watchdog" in tokens) == watchdog
        if not (same_app and sender and same_kind):
            retained.append(line)
    return "\n".join(retained + lines).rstrip() + "\n"


def install_crontab(lines: list[str], app_dir: Path, watchdog: bool) -> Path:
    import fcntl
    # Serialize registrations from this installation; never clear another user's cron.
    with (app_dir / ".crontab-install.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True,
                                timeout=15, env=dict(os.environ, LC_ALL="C"))
        if result.returncode and not (result.returncode == 1 and "no crontab for" in result.stderr.lower()):
            raise RuntimeError(f"기존 crontab 조회 실패: {result.stderr.strip()}")
        existing = result.stdout if result.returncode == 0 else ""
        updated = merge_crontab(existing, lines, app_dir, watchdog)
        fd, name = tempfile.mkstemp(prefix="crontab-backup-", suffix=".txt", dir=app_dir)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(existing)
        subprocess.run(["crontab", "-"], input=updated, text=True, check=True, timeout=15)
        return Path(name)
