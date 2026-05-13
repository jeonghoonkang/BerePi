#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_ZERO_NATIVE_PATH="${SCRIPT_DIR}/third_party/zero-native"
ZERO_NATIVE_PATH_VALUE="${ZERO_NATIVE_PATH:-${DEFAULT_ZERO_NATIVE_PATH}}"
ZERO_NATIVE_ROOT_FILE="${ZERO_NATIVE_PATH_VALUE}/src/root.zig"

cd "${SCRIPT_DIR}"

if ! command -v zig >/dev/null 2>&1; then
  echo "zig is not installed or not in PATH." >&2
  echo "Install it first, then run this script again." >&2
  echo "macOS example: brew install zig" >&2
  exit 1
fi

if [[ ! -f "${ZERO_NATIVE_ROOT_FILE}" ]]; then
  echo "zero-native framework source was not found." >&2
  echo "Expected file: ${ZERO_NATIVE_ROOT_FILE}" >&2
  echo >&2
  echo "Fix one of these ways:" >&2
  echo "1. Clone the framework into the default path:" >&2
  echo "   git clone https://github.com/vercel-labs/zero-native.git \"${DEFAULT_ZERO_NATIVE_PATH}\"" >&2
  echo "2. Or point to an existing checkout:" >&2
  echo "   ZERO_NATIVE_PATH=/absolute/path/to/zero-native bash run_zero_native.sh" >&2
  echo "3. Or run zig directly with an override:" >&2
  echo "   zig build run -Dzero-native-path=/absolute/path/to/zero-native" >&2
  exit 1
fi

zig build run -Dzero-native-path="${ZERO_NATIVE_PATH_VALUE}" "$@"
