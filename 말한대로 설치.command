#!/bin/sh
# Finder에서 더블클릭하면 터미널이 열리며 실행된다
cd "$(dirname "$0")" || exit 1
sh ./install.sh
echo
echo "이 창은 닫아도 됩니다."
