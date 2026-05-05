#!/usr/bin/env bash
set -eu

cd "$(dirname "$0")"
exec streamlit run app.py --server.address 0.0.0.0 --server.port 2297
