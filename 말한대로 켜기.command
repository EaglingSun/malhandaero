#!/bin/sh
# Finder에서 더블클릭하면 터미널이 열리며 실행된다. 켤 때마다 새 판을 받아 설치한 뒤 켠다.
cd "$(dirname "$0")" || exit 1
sh ./run.sh
echo
echo "이 창은 닫아도 됩니다."
