#!/usr/bin/env python3
"""Create or repair the trusted, owner-controlled Bash configuration."""
import os
from pathlib import Path
import secrets
import subprocess
import tempfile


def ensure_config(app_dir):
    app_dir = Path(app_dir).resolve()
    config = app_dir / 'config.env'
    if config.is_symlink():
        raise ValueError('config.env must be a regular file, not a symbolic link')
    existed = config.exists()
    text = config.read_text() if existed else (app_dir / 'config.env.sample').read_text()
    if existed:
        # Use the same Bash evaluation as run_service.sh, including quoted values
        # and export assignments. Never expose the key or source diagnostics.
        result = subprocess.run(
            ['bash', '-c', 'set -e; unset GEMMA4_API_KEY; source "$1" >/dev/null; '
             'printf "%s" "${GEMMA4_API_KEY-}"', 'init-config', str(config)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode:
            raise ValueError('Cannot read config.env as Bash; fix its syntax before retrying')
        if len(result.stdout) >= 24:
            config.chmod(0o600)
            print('Keeping existing config.env and valid API key (mode 0600)')
            return False
    # A final assignment overrides empty/short earlier assignments while keeping
    # all user settings and comments intact. Future runs preserve this new key.
    text = text.rstrip('\n') + '\n\nGEMMA4_API_KEY=' + secrets.token_hex(32) + '\n'
    fd, name = tempfile.mkstemp(prefix='.config.env-', dir=app_dir)
    try:
        with os.fdopen(fd, 'w') as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, config)
    finally:
        Path(name).unlink(missing_ok=True)
    print(('Repaired' if existed else 'Created') + ' config.env with a random API key (mode 0600)')
    return True


if __name__ == '__main__':
    try:
        ensure_config(Path(__file__).resolve().parent)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(f'Configuration setup failed: {exc}')
