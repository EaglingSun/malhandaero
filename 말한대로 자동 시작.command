#!/bin/sh
# 더블클릭하면 로그인할 때 말한대로가 알아서 켜지도록 등록한다. 해제는 '말한대로 자동 시작 해제.command'
cd "$(dirname "$0")" || exit 1
.venv/bin/python tools/autostart.py install
echo
echo "이 창은 닫아도 됩니다."
