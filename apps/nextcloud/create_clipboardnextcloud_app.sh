#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
TARGET_SCRIPT="$SCRIPT_DIR/clipboardnextcloud.py"
ICON_PNG="$SCRIPT_DIR/resource/clipboard_title_icon.png"
DEFAULT_VENV_PYTHON="/Users/tinyos/devel_opment/venv/bin/python"

if [[ -x "$DEFAULT_VENV_PYTHON" ]]; then
  PYTHON_BIN="${PYTHON_BIN:-$DEFAULT_VENV_PYTHON}"
else
  PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"
fi

PLATFORM="${PLATFORM:-auto}"
OUTPUT_PATH=""

usage() {
  printf 'Usage: %s [win] [--platform macos|windows|auto] [--python /path/to/python] [output_path]\n' "$0" >&2
  printf '  macOS   output default: $HOME/Applications/ClipboardNextcloud.app\n' >&2
  printf '  Windows output default: ./ClipboardNextcloud (launcher folder)\n' >&2
  printf '  win     shorthand for --platform windows\n' >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      if [[ $# -lt 2 ]]; then
        usage
        exit 1
      fi
      PYTHON_BIN="$2"
      shift 2
      ;;
    --platform)
      if [[ $# -lt 2 ]]; then
        usage
        exit 1
      fi
      PLATFORM="$2"
      shift 2
      ;;
    win)
      PLATFORM="windows"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -n "$OUTPUT_PATH" ]]; then
        usage
        exit 1
      fi
      OUTPUT_PATH="$1"
      shift
      ;;
  esac
done

detect_platform() {
  local uname_out
  uname_out="$(uname -s)"

  case "$PLATFORM" in
    macos) echo "macos" ;;
    windows) echo "windows" ;;
    auto)
      if [[ "$uname_out" == "Darwin" ]]; then
        echo "macos"
      elif [[ "$uname_out" =~ (MINGW|MSYS|CYGWIN) ]] || [[ -n "${WINDIR:-}" ]]; then
        echo "windows"
      else
        echo "macos"
      fi
      ;;
    *)
      printf 'Unsupported platform: %s\n' "$PLATFORM" >&2
      usage
      exit 1
      ;;
  esac
}

ensure_python() {
  if [[ -z "${PYTHON_BIN:-}" ]] || [[ ! -x "$PYTHON_BIN" ]]; then
    printf 'Python executable not found or not executable: %s\n' "${PYTHON_BIN:-<empty>}" >&2
    exit 1
  fi

  if ! "$PYTHON_BIN" -c 'import streamlit, webdav3' >/dev/null 2>&1; then
    printf 'Selected Python cannot import required packages: %s\n' "$PYTHON_BIN" >&2
    printf 'Install dependencies in that environment or pass --python with the correct virtualenv interpreter.\n' >&2
    exit 1
  fi
}

create_macos_app() {
  local app_name app_dir contents_dir macos_dir resources_dir iconset_dir icon_file launcher_path plist_path
  app_name="ClipboardNextcloud.app"
  app_dir="${OUTPUT_PATH:-$HOME/Applications/$app_name}"
  contents_dir="$app_dir/Contents"
  macos_dir="$contents_dir/MacOS"
  resources_dir="$contents_dir/Resources"
  iconset_dir="$resources_dir/AppIcon.iconset"
  icon_file="$resources_dir/AppIcon.icns"
  launcher_path="$macos_dir/clipboardnextcloud"
  plist_path="$contents_dir/Info.plist"

  mkdir -p "$macos_dir" "$resources_dir"
  rm -rf "$iconset_dir"

  cat > "$launcher_path" <<EOF
#!/usr/bin/env bash

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

  chmod +x "$launcher_path"

  cat > "$plist_path" <<EOF
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
    mkdir -p "$iconset_dir"
    for size in 16 32 128 256 512; do
      sips --resampleHeightWidth "$size" "$size" "$ICON_PNG" --out "$iconset_dir/icon_${size}x${size}.png" >/dev/null
      retina_size=$((size * 2))
      sips --resampleHeightWidth "$retina_size" "$retina_size" "$ICON_PNG" --out "$iconset_dir/icon_${size}x${size}@2x.png" >/dev/null
    done
    if ! iconutil -c icns "$iconset_dir" -o "$icon_file" 2>/dev/null; then
      printf 'Warning: custom icon generation failed, continuing with default app icon.\n' >&2
    fi
    rm -rf "$iconset_dir"
  fi

  printf 'Created macOS app: %s\n' "$app_dir"
}

create_windows_launcher() {
  local launcher_dir bat_path ps1_path shortcut_path python_escaped target_escaped launcher_dir_windows bat_path_windows shortcut_path_windows
  launcher_dir="${OUTPUT_PATH:-$SCRIPT_DIR/ClipboardNextcloud}"
  bat_path="$launcher_dir/ClipboardNextcloud.bat"
  ps1_path="$launcher_dir/ClipboardNextcloud.ps1"
  shortcut_path="$launcher_dir/ClipboardNextcloud.lnk"

  mkdir -p "$launcher_dir"

  python_escaped=$(printf '%s' "$PYTHON_BIN" | sed "s/'/''/g")
  target_escaped=$(printf '%s' "$TARGET_SCRIPT" | sed "s/'/''/g")
  launcher_dir_windows=$(printf '%s' "$launcher_dir" | sed 's#/#\\#g')
  bat_path_windows=$(printf '%s' "$bat_path" | sed 's#/#\\#g')
  shortcut_path_windows=$(printf '%s' "$shortcut_path" | sed 's#/#\\#g')

  cat > "$ps1_path" <<EOF
\$ErrorActionPreference = "Stop"

\$configuredPythonBin = '$python_escaped'
\$targetScript = '$target_escaped'
\$port = 8517
\$url = "http://localhost:\$port"
\$logDir = Join-Path \$env:LOCALAPPDATA "ClipboardNextcloud\\Logs"
\$pidFile = Join-Path \$logDir "streamlit.pid"
\$logFile = Join-Path \$logDir "streamlit.log"
\$scriptDir = Split-Path -Parent \$MyInvocation.MyCommand.Path
\$targetScriptFull = [System.IO.Path]::GetFullPath((Join-Path \$scriptDir \$targetScript))
\$pythonCandidates = @()

if (\$configuredPythonBin) {
  \$pythonCandidates += \$configuredPythonBin
}
\$pythonCandidates += @("python", "py")

function Resolve-PythonPath {
  param([string[]]\$Candidates)

  foreach (\$candidate in \$Candidates) {
    if (-not \$candidate) {
      continue
    }

    if (Test-Path -LiteralPath \$candidate) {
      return (Resolve-Path -LiteralPath \$candidate).Path
    }

    try {
      \$resolved = Get-Command \$candidate -ErrorAction Stop
      if (\$resolved -and \$resolved.Source) {
        return \$resolved.Source
      }
    } catch {
    }
  }

  return \$null
}

New-Item -ItemType Directory -Force -Path \$logDir | Out-Null

if (-not (Test-Path -LiteralPath \$targetScriptFull)) {
  Write-Host "Target script not found: \$targetScriptFull"
  Write-Host "Please regenerate launcher with the correct script path."
  exit 1
}

\$pythonBin = Resolve-PythonPath -Candidates \$pythonCandidates
if (-not \$pythonBin) {
  Write-Host "Python executable not found."
  Write-Host "Checked configured path: \$configuredPythonBin"
  Write-Host "Also tried command names: python, py"
  exit 1
}

if (Test-Path \$pidFile) {
  \$existingPid = (Get-Content \$pidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
  if (\$existingPid) {
    \$existingProcess = Get-Process -Id \$existingPid -ErrorAction SilentlyContinue
    if (\$existingProcess) {
      Start-Process \$url
      exit 0
    }
  }
  Remove-Item \$pidFile -ErrorAction SilentlyContinue
}

\$streamlitProcess = Start-Process -FilePath \$pythonBin `
  -ArgumentList "-m", "streamlit", "run", \$targetScriptFull, "--server.port", "\$port", "--server.address", "localhost", "--server.headless", "true", "--browser.gatherUsageStats", "false" `
  -RedirectStandardOutput \$logFile -RedirectStandardError \$logFile -PassThru

\$streamlitProcess.Id | Set-Content -Path \$pidFile

for (\$i = 0; \$i -lt 30; \$i++) {
  try {
    Invoke-WebRequest -UseBasicParsing -Uri \$url -TimeoutSec 1 | Out-Null
    Start-Process \$url
    exit 0
  } catch {
    Start-Sleep -Seconds 1
  }
}

Start-Process \$url
exit 0
EOF

  cat > "$bat_path" <<EOF
@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%ClipboardNextcloud.ps1"
EOF

  if command -v powershell >/dev/null 2>&1; then
    powershell -NoProfile -ExecutionPolicy Bypass -Command "
      \$shell = New-Object -ComObject WScript.Shell;
      \$shortcut = \$shell.CreateShortcut('$shortcut_path_windows');
      \$shortcut.TargetPath = '$bat_path_windows';
      \$shortcut.WorkingDirectory = '$launcher_dir_windows';
      \$shortcut.Description = 'Launch ClipboardNextcloud';
      \$shortcut.Save();
    " >/dev/null 2>&1 || printf 'Warning: Windows shortcut creation failed, launcher files were still generated.\n' >&2
  else
    printf 'Warning: powershell command not found, skipped .lnk shortcut creation.\n' >&2
  fi

  printf 'Created Windows launcher directory: %s\n' "$launcher_dir"
  printf 'Run this file on Windows: %s\n' "$bat_path"
  if [[ -f "$shortcut_path" ]]; then
    printf 'Created Windows shortcut: %s\n' "$shortcut_path"
  fi
}

TARGET_PLATFORM="$(detect_platform)"
ensure_python

case "$TARGET_PLATFORM" in
  macos) create_macos_app ;;
  windows) create_windows_launcher ;;
esac

printf 'Target script: %s\n' "$TARGET_SCRIPT"
printf 'Python executable: %s\n' "$PYTHON_BIN"
printf '(파이썬 경로를 변경하려면) 아래 PYTHON_BIN 변수를 변경하세요.\n'
printf 'PYTHON_BIN=%s\n' "$PYTHON_BIN"
printf 'Repository root: %s\n' "$REPO_ROOT"
