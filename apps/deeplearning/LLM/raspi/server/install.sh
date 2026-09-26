#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == --config-only && $# == 1 ]]; then
  python3 "$APP_DIR/init_config.py"
  exit 0
fi
if (( $# != 0 )); then
  echo 'Usage: bash install.sh [--config-only]' >&2
  exit 1
fi
if [[ "$(uname -s)" != Linux || "$(uname -m)" != aarch64 ]]; then
  echo '64-bit ARM Linux (Raspberry Pi OS / Ubuntu aarch64) is required.' >&2
  exit 1
fi
if (( EUID == 0 )); then
  echo 'Run as your normal user; sudo is requested only for package installation.' >&2
  exit 1
fi
sudo apt-get update
sudo apt-get install -y ca-certificates curl python3 python3-pil zstd util-linux tesseract-ocr tesseract-ocr-kor
if ! command -v ollama >/dev/null 2>&1; then
  installer="$(mktemp)"
  trap 'rm -f "$installer"' EXIT
  curl --fail --show-error --location --proto '=https' https://ollama.com/install.sh -o "$installer"
  sh "$installer"
fi
cd "$APP_DIR"
python3 "$APP_DIR/init_config.py"
echo 'Installation complete. Run: bash run_service.sh'
echo 'The model is downloaded on first start; config.env contains the API key.'
