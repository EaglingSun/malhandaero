"""말한대로 설치: 가상 환경을 만들고, 필요한 것을 내려받고, 설정 파일(.env)을 만든다.

실행: tools/install.bat (Windows) 또는 tools/install.sh (macOS/Linux). setup-windows.bat / setup-mac.command가 부른다. 여러 번 실행해도 안전하다.
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


def _win_shortcuts() -> None:
    """바탕 화면에 「말한대로 켜기」「말한대로 자동 시작」 바로가기를 둔다. 폴더를 열 일이 없게."""
    ps = r"""
$sh = New-Object -ComObject WScript.Shell
$desk = [Environment]::GetFolderPath('Desktop')
foreach ($pair in @(@('말한대로 켜기', 'tools\run.bat'), @('말한대로 자동 시작', 'tools\autostart.bat'))) {
  $lnk = $sh.CreateShortcut((Join-Path $desk ($pair[0] + '.lnk')))
  $lnk.TargetPath = Join-Path '%s' $pair[1]
  $lnk.WorkingDirectory = '%s'
  $lnk.IconLocation = (Join-Path '%s' 'web\icon.ico') + ',0'
  $lnk.Save()
}
""" % ((str(ROOT).replace("'", "''"),) * 3)
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], check=True, capture_output=True, timeout=60)
        print("· 바탕 화면에 「말한대로 켜기」「말한대로 자동 시작」 바로가기를 만들었어요.")
    except Exception:
        print("· 바탕 화면 바로가기는 만들지 못했어요. 폴더의 tools\run.bat / tools\autostart.bat을 쓰면 돼요.")


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
        code = ""
        while not code:
            try:
                code = input("   로그인할 때 사용할 코드를 정해 주세요 (예: 1234): ").strip()
            except EOFError:
                code = "1234"
                break
        env.write_text(
            "# 말한대로 설정. 바꾼 뒤에는 서버를 껐다 켜 주세요.\n"
            f"MALHAN_FAMILY_CODE={code}\n\n"
            "# AI 연결 — 줄 앞의 #은 '꺼 둔 줄'. 쓰려면 #을 지우세요. 더 많은 설정은 .env.example 참고.\n"
            "# [1] Claude 구독이 있으면: 아무것도 안 적어도 이 PC의 Claude Code를 씁니다 (API 결제 없음).\n"
            "# [2] 없으면: 아래 두 줄의 #을 지우고 키를 넣으세요 (aistudio.google.com/apikey, 무료). 녹음 파일도 Gemini가 들어요.\n"
            "# MALHAN_AI=gemini\n"
            "# GEMINI_API_KEY=\n",
            encoding="utf-8",
        )
        print(f"   만들었어요. 로그인 코드: {code}   (잊으면 .env 파일 첫 줄에 있어요)")

    if os.name == "nt":
        _win_shortcuts()
    if "onedrive" in str(ROOT).lower():
        print("\n! 이 폴더가 OneDrive 안에 있어요. 동기화 때문에 느려지거나 자료 파일이 잠길 수 있으니, "
              "가능하면 OneDrive 밖(예: C:\\Users\\이름\\malhandaero)으로 옮기고 install을 한 번 더 실행해 주세요.")

    print("\n설치가 끝났어요.")
    if shutil.which("claude"):
        print("· Claude Code를 찾았어요. 로그인되어 있으면 바로 쓸 수 있습니다.")
        print("  (로그인 확인: 터미널에서 claude auth status)")
    else:
        if os.environ.get("GEMINI_API_KEY") or "GEMINI_API_KEY=" in env.read_text(encoding="utf-8-sig").replace("# GEMINI_API_KEY=", ""):
            print("· Gemini 키로 연결합니다.")
        else:
            print("· 이 PC에서 Claude Code를 찾지 못했어요. 셋 중 하나를 해 주세요.")
            print("  1) Claude Code를 설치하고 로그인한다  2) .env에 GEMINI_API_KEY를 넣는다 (무료)  3) .env에 ANTHROPIC_API_KEY를 넣는다")
            print("  아무것도 없이 화면만 보려면 .env에 MALHAN_AI=fake 를 넣으세요.")
    if os.name == "nt":
        print("· 처음 켤 때 Windows 방화벽 창이 뜨면 '액세스 허용'을 눌러야 폰에서 들어올 수 있어요.")
    print("· 이제 " + ("바탕 화면의 「말한대로 켜기」" if os.name == "nt" else "「start.command」") + " 를 실행하세요.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as e:
        print(f"\n설치 중에 멈췄어요 (단계 실패: {e.cmd[0] if e.cmd else ''}). 인터넷 연결을 확인하고 다시 실행해 주세요.")
        sys.exit(1)
