#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 - "$APP_DIR" <<'PY'
"""Stop this directory's launcher, which cleans up its own child processes."""
import fcntl
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

app_dir = Path(sys.argv[1]).resolve()
lock_path = app_dir / 'logs/run.lock'
if not lock_path.exists():
    print('Gemma4 Pi server is not running (no run lock).')
    sys.exit(0)

# Keep the same lock inode open while discovering and waiting for the launcher.
with lock_path.open('r') as lock:
    def unlocked():
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        fcntl.flock(lock, fcntl.LOCK_UN)
        return True

    if unlocked():
        print('Gemma4 Pi server is not running.')
        sys.exit(0)

    candidates = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            # Open a stable process handle before inspecting it to avoid PID reuse.
            pidfd = os.pidfd_open(int(proc.name))
        except (ProcessLookupError, PermissionError):
            continue
        try:
            args = (proc / 'cmdline').read_bytes().split(b'\0')
            shell = Path(os.fsdecode(args[0])).name
            cwd = (proc / 'cwd').resolve()
            script_matches = any(
                (cwd / os.fsdecode(arg)).resolve() == app_dir / 'run_service.sh'
                for arg in args[1:] if arg and not arg.startswith(b'-')
            )
            if (shell in {'bash', 'sh'} and script_matches
                    and os.path.samefile(proc / 'fd/9', lock_path)):
                candidates.append((int(proc.name), pidfd, (proc / 'cgroup').read_text()))
                pidfd = None
        except (OSError, ValueError):
            pass
        finally:
            if pidfd is not None:
                os.close(pidfd)

    if len(candidates) != 1:
        for _, pidfd, _ in candidates:
            os.close(pidfd)
        if unlocked():
            print('Gemma4 Pi server has stopped.')
            sys.exit(0)
        sys.exit('Cannot uniquely identify the launcher holding logs/run.lock; no process was stopped.')

    pid, pidfd, cgroup = candidates[0]
    try:
        # Stop systemd's unit so Restart=on-failure does not start it again.
        units = [part for line in cgroup.splitlines() for part in line.split('/')
                 if part.endswith('.service') and not part.startswith('user@')]
        if units:
            unit = units[-1]
            command = ['systemctl']
            if '/user.slice/' in cgroup:
                command.append('--user')
            main_pid = subprocess.check_output(
                command + ['show', unit, '--property=MainPID', '--value'],
                text=True, timeout=10).strip()
            if main_pid != str(pid):
                sys.exit('Launcher belongs to another service; stop it from its owning terminal.')
            command += ['stop', unit]
            result = subprocess.run(command, timeout=40)
            if result.returncode:
                sys.exit('Service stop failed. Run with appropriate privileges: ' + ' '.join(command))
        else:
            try:
                signal.pidfd_send_signal(pidfd, signal.SIGTERM)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if select.select([pidfd], [], [], 0)[0] and unlocked():
                print(f'Stopped Gemma4 Pi launcher {pid} and its managed processes.')
                break
            time.sleep(0.2)
        else:
            sys.exit('Stop did not complete within 20 seconds; inspect server logs and process state.')
    finally:
        os.close(pidfd)
PY
