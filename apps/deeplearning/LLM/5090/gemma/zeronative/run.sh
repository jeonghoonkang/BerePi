#!/usr/bin/env bash

set -euo pipefail

export OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-gemma3:4b}"

python3 -m streamlit run app.py --server.address 0.0.0.0 --server.port 2280
