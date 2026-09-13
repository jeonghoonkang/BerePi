#!/usr/bin/env python3
"""Idempotently install this user's ten-minute and boot health checks."""
from pathlib import Path
import shlex
import subprocess

base = Path(__file__).resolve().parent
command = f'/usr/bin/python3 {shlex.quote(str(base / "time_check.py"))}'
# Cron treats percent specially, even inside shell quotes.
command = command.replace('%', r'\%')
start, end = '# BEGIN BerePi time_check', '# END BerePi time_check'
result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
if result.returncode and 'no crontab for' not in result.stderr:
    raise SystemExit(result.stderr)
old = result.stdout
if (start in old) != (end in old):
    raise SystemExit('Incomplete time_check marker; inspect crontab manually.')
if start in old:
    prefix, rest = old.split(start, 1)
    _, suffix = rest.split(end, 1)
    old = prefix + suffix.lstrip('\n')
block = f'{start}\n*/10 * * * * {command}\n@reboot /bin/sleep 30 && {command}\n{end}\n'
subprocess.run(['crontab', '-'], input=old.rstrip() + '\n\n' + block, text=True, check=True)
print('Installed: every 10 minutes and 30 seconds after boot.')
