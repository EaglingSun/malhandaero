#!/bin/sh
# 처음 한 번: 이 파일만 받아 더블클릭하면 저장소를 받고 설치한 뒤 켠다.
# 이미 받은 폴더 안에서 실행하면 다시 설치(음성 인식 등 빠진 것 채움)하고 켠다.
REPO="https://github.com/EaglingSun/malhandaero.git"
cd "$(dirname "$0")" || exit 1
if [ -d .git ] && [ -f tools/run.py ]; then
  DIR="."
elif [ -d malhandaero/.git ]; then
  DIR="malhandaero"
else
  command -v git >/dev/null 2>&1 || { echo "git이 필요해요. 터미널에서 git 을 한 번 입력해 설치 안내를 따른 뒤 다시 실행해 주세요."; read -r _; exit 1; }
  echo "저장소를 받습니다: $REPO"
  git clone "$REPO" malhandaero || { echo "받지 못했어요. 저장소 접근 권한이 있는 GitHub 계정으로 로그인되어 있는지 확인해 주세요."; read -r _; exit 1; }
  DIR="malhandaero"
fi
cd "$DIR" || exit 1
if ! command -v claude >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/claude" ]; then
  echo "Claude Code를 설치합니다 (AI 연결용)…"
  curl -fsSL https://claude.ai/install.sh | bash || echo "Claude Code 설치는 못 했어요. 나중에 claude.com/claude-code 를 참고해 설치하면 돼요."
  echo "설치 뒤 터미널에서 claude 를 한 번 실행해 로그인하고 앱을 다시 켜면 AI가 연결돼요."
  echo
fi
chmod +x ./*.command tools/*.sh 2>/dev/null
sh tools/install.sh || { read -r _; exit 1; }
sh tools/run.sh "$@"
echo
echo "이 창은 닫아도 됩니다."
