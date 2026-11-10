#!/bin/sh
# 말한대로 실행 (macOS/Linux). 켤 때마다 업데이트를 받아 설치한 뒤 켠다.
#   Tailscale 주소 안 열기: tools/run.sh --local      업데이트 안 받기: tools/run.sh --no-update
cd "$(dirname "$0")/.." || exit 1
PY=python3; command -v python3 >/dev/null 2>&1 || PY=python
"$PY" tools/update.py "$@" || exit 1
[ -x .venv/bin/python ] || { echo "먼저 「setup-mac.command」를 실행해 주세요."; exit 1; }
# Mac은 켜 두는 동안 잠들지 않게 한다 (덮개를 닫으면 잠듭니다)
if command -v caffeinate >/dev/null 2>&1; then
  exec caffeinate -i .venv/bin/python tools/run.py "$@"
fi
exec .venv/bin/python tools/run.py "$@"
