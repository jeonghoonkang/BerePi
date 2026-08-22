#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! REPO_DIR="$(git -C "${APP_DIR}" rev-parse --show-toplevel 2>/dev/null)"; then
  echo "Git repository를 찾을 수 없어 LLM Routing을 시작하지 않습니다." >&2
  exit 1
fi

BRANCH="$(git -C "${REPO_DIR}" branch --show-current)"
if [[ -z "${BRANCH}" ]]; then
  echo "현재 Git HEAD가 브랜치에 연결되어 있지 않아 pull할 수 없습니다." >&2
  echo "LLM Routing을 시작하지 않습니다." >&2
  exit 1
fi

echo "Git pull을 시작합니다: ${REPO_DIR} (${BRANCH})"
if ! git -C "${REPO_DIR}" pull --ff-only; then
  echo "Git pull에 실패하여 LLM Routing을 시작하지 않습니다." >&2
  exit 1
fi

echo "Git pull이 성공적으로 완료되었습니다. LLM Routing을 시작합니다."
exec bash "${APP_DIR}/start.sh" "$@"
