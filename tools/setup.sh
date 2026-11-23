#!/usr/bin/env bash
# 準備：ffmpeg・日本語フォント・Pillow を入れる（クラウドの Ubuntu 用。1〜2分）
set -e
if command -v ffmpeg >/dev/null && python3 -c "import PIL" 2>/dev/null && fc-list 2>/dev/null | grep -q "Noto Sans CJK"; then
  echo "もう入っています"; python3 tools/make.py --check; exit 0
fi
SUDO=""; [ "$(id -u)" != "0" ] && command -v sudo >/dev/null && SUDO="sudo"
if command -v apt-get >/dev/null; then
  $SUDO apt-get update -qq
  DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq ffmpeg fonts-noto-cjk fonts-noto-cjk-extra python3-pil >/dev/null || \
  DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq ffmpeg fonts-noto-cjk python3-pil >/dev/null
elif command -v brew >/dev/null; then
  brew install ffmpeg
fi
python3 -c "import PIL" 2>/dev/null || pip install -q pillow || pip install -q --break-system-packages pillow
python3 tools/make.py --check
