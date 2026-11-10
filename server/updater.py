"""저장소의 최신 버전으로 맞춘다. 켜기 전에 tools/update.py가 부르고, 켜진 뒤에는 화면의 '업데이트'과 새벽 자동 확인이 부른다.

하는 일 (순서대로, 어느 단계가 실패해도 지금 판으로 그냥 켠다)
  1. 이 폴더가 git 저장소(git clone으로 받은 것)인지 본다. 아니면 안내만 하고 건너뛴다.
  2. origin에서 업데이트를 받아 온다. 빨리 감기(fast-forward)만 한다. 직접 고친 파일이 있으면 덮어쓰지 않고 건너뛴다.
  3. requirements.txt가 바뀌었거나 .venv가 없으면 설치(tools/install.py)를 다시 한다.
  4. 화면(manifest)이 바뀌었으면 휴대폰에서 앱을 다시 설치하라고 알려 준다.

끄는 법: .env에 MALHAN_AUTO_UPDATE=0  또는  ./run.sh --no-update
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PY = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
REPO_URL = "https://github.com/EaglingSun/malhandaero.git"
TIMEOUT = 40  # 초. 느린 인터넷에서도 켜기를 오래 막지 않는다
RESTART_CODE = 3  # 서버가 이 코드로 끝나면 run.py가 새 버전으로 다시 켠다

# 마지막 실행 결과. 화면에 보여 주기 위해 남긴다
RESULT: dict = {"updated": False, "before": "", "after": "", "log": [], "changed": [], "messages": []}


def _reset() -> None:
    RESULT.update(updated=False, before="", after="", log=[], changed=[], messages=[])


def _env_file_says_off() -> bool:
    env = ROOT / ".env"
    if not env.exists():
        return False
    for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("MALHAN_AUTO_UPDATE="):
            return line.split("=", 1)[1].strip().strip('"').strip("'") in ("0", "false", "no", "off")
    return False


def git(*args: str, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT)
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else f"git {args[0]} 실패")
    return r.stdout.strip()


def say(msg: str) -> None:
    RESULT["messages"].append(msg)
    print(f"  {msg}", flush=True)


def adopt() -> None:
    """저장소가 아닌 폴더를 원격 main에 붙인다. 추적 파일은 저장소 내용으로 맞춰지고(같은 판이면 내용 그대로) 실행 권한도 되살아난다.
    git이 모르는 파일(data/, .env, .venv/)은 건드리지 않는다."""
    git("init", "--quiet")
    git("remote", "add", "origin", REPO_URL)
    git("fetch", "--quiet", "--depth", "1", "origin", "main")
    git("checkout", "--quiet", "--force", "-B", "main", "origin/main")
    git("branch", "--quiet", "--set-upstream-to=origin/main", "main")
    say(f"연결했어요 ({git('rev-parse', 'HEAD')[:7]}). 이제 켤 때마다 업데이트돼요.")


def install() -> None:
    say("설치를 다시 합니다 (바뀐 것만 받아요)…")
    subprocess.check_call([sys.executable, str(ROOT / "tools" / "install.py")], cwd=ROOT)


def main(argv: list[str]) -> int:
    _reset()
    print("\n말한대로 업데이트 확인", flush=True)
    if "--no-update" in argv or os.environ.get("MALHAN_AUTO_UPDATE") == "0" or _env_file_says_off():
        say("자동 업데이트가 꺼져 있어요. 지금 버전으로 켭니다.")
        return 0
    if not shutil.which("git"):
        say("git이 없어서 업데이트하지 못해요. 지금 버전으로 켭니다. (Mac: 터미널에서 git 입력 → 설치 안내 / Windows: https://git-scm.com)")
        return 0
    if not (ROOT / ".git").exists():
        # 압축 파일로 풀었거나 파일만 복사된 폴더: 한 번만 저장소에 연결한다. data/와 .env는 git이 모르는 파일이라 그대로 남는다
        say("이 폴더를 저장소에 연결합니다 (처음 한 번). 자료와 설정은 그대로 둬요.")
        try:
            adopt()
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            say(f"연결하지 못했어요: {e}. 지금 버전으로 켭니다. (인터넷이 되면 다음에 다시 시도해요)")
            shutil.rmtree(ROOT / ".git", ignore_errors=True)  # 절반만 된 .git이 남지 않게
            return 0

    try:
        if git("status", "--porcelain", "--untracked-files=no"):
            say("직접 고친 파일이 있어서 덮어쓰지 않고 지금 버전으로 켭니다. (git stash 로 치우면 다시 업데이트돼요)")
            return 0
        before = git("rev-parse", "HEAD")
        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        try:
            git("fetch", "--quiet", "origin", branch)
        except (RuntimeError, subprocess.TimeoutExpired):
            say(f"깃허브에 닿지 못해 지금 버전({before[:7]})으로 켭니다. 인터넷이 되면 다음에 다시 확인해요.")
            return 0
        remote = git("rev-parse", f"origin/{branch}")
        if remote == before:
            RESULT.update(before=before[:7], after=before[:7])
            say(f"지금이 최신이에요 ({before[:7]}).")
            changed: list[str] = []
        else:
            git("merge", "--ff-only", "--quiet", f"origin/{branch}")
            after = git("rev-parse", "HEAD")
            changed = git("diff", "--name-only", before, after).splitlines()
            log = git("log", "--oneline", "--no-decorate", f"{before}..{after}").splitlines()
            RESULT.update(updated=True, before=before[:7], after=after[:7], changed=changed,
                          log=[(l.split(" ", 1)[1] if " " in l else l) for l in log])
            say(f"업데이트했어요 ({before[:7]} → {after[:7]}, 변경 {len(log)}건)")
            for line in log[:8]:
                say("  · " + (line.split(" ", 1)[1] if " " in line else line))
            if len(log) > 8:
                say(f"  · … 외 {len(log) - 8}건")
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        say(f"업데이트하지 못했어요: {e}. 지금 버전으로 켭니다.")
        return 0

    if not VENV_PY.exists() or any(c in changed for c in ("requirements.txt", "requirements-stt.txt", "tools/install.py")):
        try:
            install()
        except subprocess.CalledProcessError:
            say("설치가 끝까지 되지 않았어요. 인터넷을 확인한 뒤 다시 켜 주세요.")
            return 1
    if "web/manifest.webmanifest" in changed:
        say("! 휴대폰 앱의 모양·공유 설정이 바뀌었어요. 휴대폰에서 말한대로를 지우고 홈 화면에 다시 추가해 주세요.")
    elif any(p.startswith("web/") for p in changed):
        say("화면이 바뀌었어요. 휴대폰 화면이 예전 모양이면 새로고침해 주세요.")
    return 0


def restart_soon(delay: float = 1.0) -> None:
    """응답을 보낸 뒤 서버를 끝낸다. run.py가 RESTART_CODE를 보고 새 버전으로 다시 켠다."""
    import threading

    threading.Timer(delay, lambda: os._exit(RESTART_CODE)).start()
