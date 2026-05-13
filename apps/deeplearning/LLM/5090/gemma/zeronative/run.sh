#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}"

if [[ -z "${VIRTUAL_ENV:-}" && -f "${SCRIPT_DIR}/.venv/bin/activate" ]]; then
  # Prefer the local project virtualenv when the caller did not activate one.
  # shellcheck disable=SC1091
  source "${SCRIPT_DIR}/.venv/bin/activate"
fi

export OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-gemma3:4b}"
export STREAMLIT_ADDRESS="${STREAMLIT_ADDRESS:-0.0.0.0}"
export STREAMLIT_PORT="${STREAMLIT_PORT:-2280}"

if ! python3 - <<'PY' >/dev/null 2>&1
required = ["streamlit", "requests", "pandas", "openpyxl", "PIL", "pypdf"]
for module in required:
    __import__(module)
PY
then
  echo "Python dependencies for app.py are missing." >&2
  echo "Expected modules: streamlit, requests, pandas, openpyxl, Pillow, pypdf" >&2
  echo >&2
  if [[ -f "${SCRIPT_DIR}/.venv/bin/activate" ]]; then
    echo "Try this:" >&2
    echo "  cd \"${SCRIPT_DIR}\"" >&2
    echo "  source .venv/bin/activate" >&2
    echo "  pip install -r requirements.txt" >&2
  else
    echo "Try this:" >&2
    echo "  cd \"${SCRIPT_DIR}\"" >&2
    echo "  python3 -m venv .venv" >&2
    echo "  source .venv/bin/activate" >&2
    echo "  pip install -r requirements.txt" >&2
  fi
  exit 1
fi

python3 -m streamlit run app.py --server.address "${STREAMLIT_ADDRESS}" --server.port "${STREAMLIT_PORT}"
