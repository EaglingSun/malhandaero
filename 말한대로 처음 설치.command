#!/bin/sh
# 처음 한 번: 이 파일만 받아 더블클릭하면 저장소를 받고 설치한 뒤 켠다.
# 이미 받은 폴더 안에서 실행하면 그 폴더를 최신 판으로 맞추고 켠다.
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
chmod +x ./*.sh ./*.command 2>/dev/null
[ -x .venv/bin/python ] || sh ./install.sh
sh ./run.sh "$@"
echo
echo "이 창은 닫아도 됩니다."
