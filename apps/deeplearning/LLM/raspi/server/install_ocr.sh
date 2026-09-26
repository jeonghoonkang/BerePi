#!/usr/bin/env bash
# Install a private Debian/Ubuntu OCR runtime without root access.
set -euo pipefail
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
OCR_DIR="$APP_DIR/.ocr-runtime"
command -v apt-get >/dev/null
command -v dpkg-deb >/dev/null
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
cd "$staging"
apt-get download tesseract-ocr libtesseract5 liblept5 tesseract-ocr-eng tesseract-ocr-kor tesseract-ocr-osd
mkdir -p "$OCR_DIR"
for package in ./*.deb; do
  dpkg-deb -x "$package" "$OCR_DIR"
done
export LD_LIBRARY_PATH="$OCR_DIR/usr/lib/$(dpkg-architecture -qDEB_HOST_MULTIARCH)${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export TESSDATA_PREFIX="$OCR_DIR/usr/share/tesseract-ocr/5/tessdata"
"$OCR_DIR/usr/bin/tesseract" --list-langs
printf 'OCR runtime installed in %s\n' "$OCR_DIR"
