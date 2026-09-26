#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(uname -s)" != Linux || "$(uname -m)" != aarch64 ]]; then
  echo '64-bit ARM Linux (Raspberry Pi OS / Ubuntu aarch64) is required.' >&2
  exit 1
fi
if (( EUID == 0 )); then
  echo 'Run as your normal user; sudo is requested only for package installation.' >&2
  exit 1
fi
sudo apt-get update
sudo apt-get install -y ca-certificates curl python3 python3-pil zstd util-linux
if ! command -v ollama >/dev/null 2>&1; then
  installer="$(mktemp)"
  trap 'rm -f "$installer"' EXIT
  curl --fail --show-error --location --proto '=https' https://ollama.com/install.sh -o "$installer"
  sh "$installer"
fi
cd "$APP_DIR"
python3 - <<'PY'
import os
import secrets
from pathlib import Path

config = Path('config.env')
try:
    fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    print('Keeping existing config.env')
else:
    with os.fdopen(fd, 'w') as output:
        output.write(Path('config.env.sample').read_text())
        output.write('\nGEMMA4_API_KEY=' + secrets.token_hex(32) + '\n')
    print('Created config.env with a random API key (mode 0600)')
PY
echo 'Installation complete. Run: bash run_service.sh'
echo 'The model is downloaded on first start; config.env contains the API key.'
