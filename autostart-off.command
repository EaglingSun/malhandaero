#!/bin/sh
cd "$(dirname "$0")" || exit 1
.venv/bin/python tools/autostart.py remove
echo
echo "이 창은 닫아도 됩니다."
