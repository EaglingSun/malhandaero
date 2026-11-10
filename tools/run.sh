#!/bin/sh
# 말한대로 실행 (macOS/Linux). 켤 때마다 새 판을 받아 설치한 뒤 켠다.
#   집 밖 주소 끄기: tools/run.sh --local      새 판 받지 않기: tools/run.sh --no-update
cd "$(dirname "$0")/.." || exit 1
PY=python3; command -v python3 >/dev/null 2>&1 || PY=python
"$PY" tools/update.py "$@" || exit 1
[ -x .venv/bin/python ] || { echo "먼저 「말한대로 처음 설치.command」를 실행해 주세요."; exit 1; }
# Mac은 켜 두는 동안 잠들지 않게 한다 (덮개를 닫으면 잠듭니다)
if command -v caffeinate >/dev/null 2>&1; then
  exec caffeinate -i .venv/bin/python tools/run.py "$@"
fi
exec .venv/bin/python tools/run.py "$@"
