"""PC에 로그인하면 말한대로가 알아서 켜지게 한다(서비스처럼). 끄면 다시 켜고, 잠들지 않게 한다.

    python tools/autostart.py install   # 등록 (Mac: launchd, Windows: 시작 프로그램)
    python tools/autostart.py remove    # 해제
    python tools/autostart.py status

Mac은 ~/Library/LaunchAgents/com.malhandaero.plist 로 등록한다. 로그인하면 바로 켜지고, 죽으면 launchd가 다시 켠다.
  창 없이 돌므로 화면 출력은 data/server.log 에 쌓인다. 덮개를 닫으면 잠드는 것은 시스템 설정(전원 어댑터 연결 시 잠자기 방지)으로.
Windows는 시작 프로그램 폴더에 tools/run.bat을 부르는 bat을 둔다. 로그인하면 검은 창이 하나 뜨며 켜진다(창을 최소화해 두면 된다).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABEL = "com.malhandaero.server"


def _mac_plist() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _mac_install() -> None:
    py = ROOT / ".venv" / "bin" / "python"
    if not py.exists():
        sys.exit("먼저 설치(말한대로 처음 설치.command)를 해 주세요.")
    # launchd는 PATH가 거의 비어 있어서 claude·tailscale을 못 찾는다. 지금 셸의 PATH를 그대로 넘긴다
    path = os.environ.get("PATH", "")
    for extra in ("/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".local" / "bin"), str(Path.home() / ".npm-global" / "bin")):
        if extra not in path:
            path += ":" + extra
    claude = shutil.which("claude")
    if claude and str(Path(claude).parent) not in path:
        path += ":" + str(Path(claude).parent)
    log = ROOT / "data" / "server.log"
    log.parent.mkdir(exist_ok=True)
    # run.sh를 통해 켠다: 켤 때 업데이트 확인 → caffeinate(잠들지 않게) → 서버
    args = ["/bin/sh", str(ROOT / "tools" / "run.sh")]
    xml_args = "\n".join(f"      <string>{a}</string>" for a in args)
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key>
  <array>
{xml_args}
  </array>
  <key>WorkingDirectory</key><string>{ROOT}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>{path}</string>
    <key>HOME</key><string>{Path.home()}</string>
    <key>LANG</key><string>ko_KR.UTF-8</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>{log}</string>
  <key>StandardErrorPath</key><string>{log}</string>
</dict>
</plist>
"""
    p = _mac_plist()
    p.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["launchctl", "unload", str(p)], capture_output=True)
    p.write_text(plist, encoding="utf-8")
    r = subprocess.run(["launchctl", "load", "-w", str(p)], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("등록하지 못했어요: " + (r.stderr or r.stdout).strip())
    print(f"등록했어요. 로그인하면 알아서 켜지고, 꺼지면 다시 켜요.\n  로그: {log}\n  해제: python tools/autostart.py remove")
    print("  지금 켜 둔 '말한대로 켜기' 창이 있으면 닫아도 돼요(포트가 겹치면 launchd 쪽이 10초 뒤 다시 시도해요).")
    print("  덮개를 닫아도 켜 두려면: 시스템 설정 → 배터리 → 전원 어댑터 → '디스플레이가 꺼져 있을 때 자동으로 잠자기 방지'")


def _mac_remove() -> None:
    p = _mac_plist()
    if p.exists():
        subprocess.run(["launchctl", "unload", "-w", str(p)], capture_output=True)
        p.unlink()
        print("해제했어요. 이제 '말한대로 켜기.command'로 직접 켜면 돼요.")
    else:
        print("등록돼 있지 않아요.")


def _mac_status() -> None:
    p = _mac_plist()
    r = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    print(("등록됨 · " + ("실행 중" if LABEL in r.stdout else "멈춤")) if p.exists() else "등록 안 됨")


def _win_startup() -> Path:
    return Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "말한대로.bat"


def _win_install() -> None:
    if not (ROOT / ".venv" / "Scripts" / "python.exe").exists():
        sys.exit("먼저 「말한대로 처음 설치.bat」을 실행해 주세요.")
    p = _win_startup()
    p.parent.mkdir(parents=True, exist_ok=True)
    # 시작 프로그램 폴더의 bat 하나: run.bat 을 최소화된 창으로 켠다 (ASCII만 — cmd가 UTF-8 bat를 깨뜨린다)
    p.write_text(f'@echo off\r\nstart "malhandaero" /min cmd /c ""{ROOT / "tools" / "run.bat"}""\r\n', encoding="ascii", errors="replace")
    print(f"등록했어요. 로그인하면 최소화된 창으로 켜져요.\n  파일: {p}\n  해제: python tools\\autostart.py remove")
    print("  PC가 잠들면 끊겨요: 설정 → 시스템 → 전원 → 화면 및 절전 → 절전 모드 '안 함'")


def _win_remove() -> None:
    p = _win_startup()
    if p.exists():
        p.unlink()
        print("해제했어요.")
    else:
        print("등록돼 있지 않아요.")


def _win_status() -> None:
    print("등록됨" if _win_startup().exists() else "등록 안 됨")


def main() -> None:
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()
    if cmd not in ("install", "remove", "status"):
        sys.exit(__doc__)
    if sys.platform == "darwin":
        {"install": _mac_install, "remove": _mac_remove, "status": _mac_status}[cmd]()
    elif os.name == "nt":
        {"install": _win_install, "remove": _win_remove, "status": _win_status}[cmd]()
    else:
        sys.exit("Linux는 systemd --user 서비스로 직접 등록해 주세요 (ExecStart=.venv/bin/python tools/run.py).")


if __name__ == "__main__":
    main()
