"""말한대로 설치: 가상 환경을 만들고, 필요한 것을 내려받고, 설정 파일(.env)을 만든다.

실행: install.bat (Windows) 또는 ./install.sh (macOS/Linux). 여러 번 실행해도 안전하다.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def step(msg: str) -> None:
    print(f"\n▶ {msg}", flush=True)


def main() -> int:
    if sys.version_info < (3, 10):
        print(f"Python 3.10 이상이 필요해요. 지금은 {sys.version.split()[0]}입니다.\nhttps://www.python.org/downloads/ 에서 새 버전을 설치해 주세요.")
        return 1

    step("1/3 가상 환경 만들기 (.venv)")
    if not PY.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    print("   준비됨")

    step("2/4 필요한 것 내려받기 (1~2분)")
    subprocess.check_call([str(PY), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "-r", str(ROOT / "requirements.txt")])
    print("   준비됨")

    step("3/4 녹음 파일을 글로 바꾸는 음성 인식 (한 번만, 2~5분)")
    if os.environ.get("MALHAN_STT", "1") == "0" or "--no-stt" in sys.argv:
        print("   건너뜀 (MALHAN_STT=0). 글·사진·말하기는 그대로 됩니다.")
    else:
        try:
            subprocess.check_call([str(PY), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "-r", str(ROOT / "requirements-stt.txt")])
            print("   음성 인식 모델을 미리 받아 둡니다 (약 500MB, 처음 한 번)…")
            r = subprocess.run([str(PY), "-c", "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"],
                               capture_output=True, text=True, timeout=1800)
            print("   준비됨" if r.returncode == 0 else "   모델은 처음 녹음을 넣을 때 받습니다 (지금은 못 받았어요).")
        except Exception:
            print("   음성 인식은 설치하지 못했어요. 녹음 파일 말고 글·사진·말하기는 다 됩니다. 나중에 다시 설치하면 켜집니다.")

    step("4/4 설정 파일 만들기 (.env)")
    env = ROOT / ".env"
    if env.exists():
        print("   이미 있어서 그대로 둡니다.")
    else:
        try:
            code = input("   들어올 때 쓸 가족 코드를 정해 주세요 (그냥 Enter = 1234): ").strip() or "1234"
        except EOFError:
            code = "1234"
        env.write_text(
            "# 말한대로 설정. 바꾼 뒤에는 서버를 껐다 켜 주세요.\n"
            f"MALHAN_FAMILY_CODE={code}\n\n"
            "# AI 연결: 비워 두면 이 PC의 Claude Code 로그인을 씁니다 (API 결제 없음).\n"
            "# API 키로 쓰려면 아래 줄의 #을 지우고 키를 넣으세요.\n"
            "# ANTHROPIC_API_KEY=\n",
            encoding="utf-8",
        )
        print(f"   만들었어요. 가족 코드: {code}")

    print("\n설치가 끝났어요.")
    if shutil.which("claude"):
        print("· Claude Code를 찾았어요. 로그인되어 있으면 바로 쓸 수 있습니다.")
        print("  (로그인 확인: 터미널에서 claude auth status)")
    else:
        print("· 이 PC에서 Claude Code를 찾지 못했어요. 둘 중 하나를 해 주세요.")
        print("  1) Claude Code를 설치하고 로그인한다  2) .env에 ANTHROPIC_API_KEY를 넣는다")
        print("  아무것도 없이 화면만 보려면 .env에 MALHAN_AI=fake 를 넣으세요.")
    print("· 이제 " + ("run.bat" if os.name == "nt" else "./run.sh") + " 을 실행하세요.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as e:
        print(f"\n설치 중에 멈췄어요 (단계 실패: {e.cmd[0] if e.cmd else ''}). 인터넷 연결을 확인하고 다시 실행해 주세요.")
        sys.exit(1)
