#!/bin/zsh

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
TARGET_SCRIPT="$SCRIPT_DIR/clipboardnextcloud.py"
ICON_PNG="$SCRIPT_DIR/resource/clipboard_title_icon.png"
DEFAULT_VENV_PYTHON="/Users/tinyos/devel_opment/venv/bin/python"

if [[ -x "$DEFAULT_VENV_PYTHON" ]]; then
  PYTHON_BIN="${PYTHON_BIN:-$DEFAULT_VENV_PYTHON}"
else
  PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
fi

if [[ "${1:-}" == "--python" ]]; then
  if [[ $# -lt 2 ]]; then
    printf 'Usage: %s [--python /path/to/python] [output_app_path]\n' "$0" >&2
    exit 1
  fi
  PYTHON_BIN="$2"
  shift 2
fi

APP_NAME="ClipboardNextcloud.app"
APP_DIR="${1:-$HOME/Applications/$APP_NAME}"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
ICONSET_DIR="$RESOURCES_DIR/AppIcon.iconset"
ICON_FILE="$RESOURCES_DIR/AppIcon.icns"
LAUNCHER_PATH="$MACOS_DIR/clipboardnextcloud"
PLIST_PATH="$CONTENTS_DIR/Info.plist"

mkdir -p "$MACOS_DIR" "$RESOURCES_DIR"
rm -rf "$ICONSET_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
  printf 'Python executable not found or not executable: %s\n' "$PYTHON_BIN" >&2
  exit 1
fi

if ! "$PYTHON_BIN" -c 'import streamlit, webdav3' >/dev/null 2>&1; then
  printf 'Selected Python cannot import required packages: %s\n' "$PYTHON_BIN" >&2
  printf 'Install dependencies in that environment or pass --python with the correct virtualenv interpreter.\n' >&2
  exit 1
fi

cat > "$LAUNCHER_PATH" <<EOF
#!/bin/zsh

set -euo pipefail

TARGET_SCRIPT="$TARGET_SCRIPT"
PYTHON_BIN="$PYTHON_BIN"
LOG_DIR="\$HOME/Library/Logs/ClipboardNextcloud"
LOG_FILE="\$LOG_DIR/streamlit.log"
PID_FILE="\$LOG_DIR/streamlit.pid"
PORT=8517
HOST="localhost"
URL="http://\${HOST}:\$PORT"
FALLBACK_URL="http://127.0.0.1:\$PORT"

mkdir -p "\$LOG_DIR"

if [[ -f "\$PID_FILE" ]]; then
  EXISTING_PID=\$(cat "\$PID_FILE" 2>/dev/null || true)
  if [[ -n "\${EXISTING_PID}" ]] && kill -0 "\$EXISTING_PID" >/dev/null 2>&1; then
    open "\$URL"
    exit 0
  fi
  rm -f "\$PID_FILE"
fi

nohup "\$PYTHON_BIN" -m streamlit run "\$TARGET_SCRIPT" \
  --server.port "\$PORT" \
  --server.address "\$HOST" \
  --server.headless true \
  --browser.gatherUsageStats false \
  >>"\$LOG_FILE" 2>&1 &

echo \$! > "\$PID_FILE"

for _ in {1..30}; do
  if curl -fsS "\$URL" >/dev/null 2>&1; then
    open "\$URL"
    exit 0
  fi
  if curl -fsS "\$FALLBACK_URL" >/dev/null 2>&1; then
    open "\$FALLBACK_URL"
    exit 0
  fi
  sleep 1
done

open "\$URL"
exit 0
EOF

chmod +x "$LAUNCHER_PATH"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>clipboardnextcloud</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleIdentifier</key>
  <string>com.berepi.nextcloud.clipboard</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>ClipboardNextcloud</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF

if [[ -f "$ICON_PNG" ]] && command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
  mkdir -p "$ICONSET_DIR"
  for size in 16 32 128 256 512; do
    sips --resampleHeightWidth "$size" "$size" "$ICON_PNG" --out "$ICONSET_DIR/icon_${size}x${size}.png" >/dev/null
    retina_size=$((size * 2))
    sips --resampleHeightWidth "$retina_size" "$retina_size" "$ICON_PNG" --out "$ICONSET_DIR/icon_${size}x${size}@2x.png" >/dev/null
  done
  if ! iconutil -c icns "$ICONSET_DIR" -o "$ICON_FILE" 2>/dev/null; then
    printf 'Warning: custom icon generation failed, continuing with default app icon.\n' >&2
  fi
  rm -rf "$ICONSET_DIR"
fi

printf 'Created %s\n' "$APP_DIR"
printf 'Target script: %s\n' "$TARGET_SCRIPT"
printf 'Python executable: %s\n' "$PYTHON_BIN"
printf '(파이썬 경로를 변경하려면) 아래 PYTHON_BIN 변수를 변경하세요.\n'
printf 'PYTHON_BIN=%s\n' "$PYTHON_BIN"
printf 'Repository root: %s\n' "$REPO_ROOT"
