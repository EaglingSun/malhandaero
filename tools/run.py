"""말한대로 서버를 켜고, 어디로 접속하면 되는지 알려 준다."""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
PORT = int(os.environ.get("MALHAN_PORT", "8000"))


def lan_ip() -> str | None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # 실제로 보내지는 않는다. 바깥으로 나가는 주소만 알아낸다
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def tailscale_bin() -> str | None:
    import shutil

    mac_app = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
    win_app = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Tailscale", "tailscale.exe")
    found = shutil.which("tailscale")
    for cand in (mac_app, win_app):
        if not found and os.path.exists(cand):
            found = cand
    return found


def tailscale_name(exe: str) -> str | None:
    """이 PC의 Tailscale 이름(예: my-mac.tail1234.ts.net). 연결되어 있지 않으면 None."""
    import json
    import subprocess

    try:
        out = subprocess.run([exe, "status", "--json"], capture_output=True, text=True, timeout=10).stdout
        st = json.loads(out)
        if st.get("BackendState") != "Running":
            return None
        return (st.get("Self", {}).get("DNSName") or "").rstrip(".") or None
    except Exception:
        return None


def open_remote(exe: str) -> tuple[bool, str]:
    """Tailscale로 https 주소를 연다. 같은 Tailscale에 들어온 기기에서만 보인다."""
    import subprocess

    try:
        r = subprocess.run([exe, "serve", "--bg", str(PORT)], capture_output=True, text=True, timeout=30)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def main() -> None:
    try:
        sys.stdout.reconfigure(line_buffering=True)  # 창에 바로바로 보이게
    except Exception:
        pass
    try:
        import uvicorn
    except ImportError:
        print("먼저 설치를 해 주세요: " + ("install.bat" if os.name == "nt" else "./install.sh"))
        sys.exit(1)
    from server import llm, stt  # .env를 읽은 뒤의 상태

    names = {"claude": "Claude Code", "anthropic": "Anthropic API", "fake": "흉내 모드(부정확)", "none": "없음", "codex": "Codex", "gpt": "OpenAI API", "gemini": "Gemini", "ollama": "Ollama", "openai": "OpenAI 호환 서버"}
    ip = lan_ip()
    if ip and not ip.startswith("127."):
        os.environ["MALHAN_LAN_URL"] = f"http://{ip}:{PORT}"
    lan = os.environ.get("MALHAN_LAN_URL", "")
    public, remote_note = "", ""
    ts = tailscale_bin()
    if "--local" in sys.argv:
        remote_note = "집 밖 주소는 껐어요 (--local)"
    elif not ts:
        remote_note = "집 밖에서도 쓰려면 Tailscale을 설치하세요 (앱의 「휴대폰 연결」에 안내)"
    else:
        name = tailscale_name(ts)
        if not name:
            remote_note = "Tailscale이 꺼져 있거나 로그인되지 않았어요"
        else:
            ok, detail = open_remote(ts)
            if ok:
                public = f"https://{name}"
                os.environ["MALHAN_PUBLIC_URL"] = public
            else:
                remote_note = f"Tailscale 주소를 열지 못했어요: {(detail or '').splitlines()[0][:120] if detail else ''}  (터미널에서 tailscale serve --bg {PORT})"
    best = public or lan

    # 화면: 꼭 필요한 것만. 폰에서 열 주소 하나, PC 주소, 상태 한 줄
    print("\n말한대로가 켜졌어요.\n")
    if best:
        print(f"  휴대폰 → Chrome 주소창에   {best}")
        print(f"  {'(Tailscale을 켠 내 기기에서 어디서나)' if public else '(같은 와이파이에서만)'}  이름과 가족 코드로 들어가요")
    print(f"  이 PC → http://localhost:{PORT}")
    eng = stt.engine()
    stt_text = {"whisper": "켜짐", "gemini": "켜짐(Gemini)"}.get(eng, "꺼짐")
    print(f"\n  AI {names.get(llm.mode(), llm.mode())} · 녹음 변환 {stt_text}" + (f" · 긴 글 {llm.claude_model_for('x' * 10 ** 6)}" if llm.mode() == "claude" and llm.claude_model_for("x" * 10 ** 6) else ""))
    if remote_note:
        print("  " + remote_note)
    if not os.environ.get("MALHAN_FAMILY_CODE"):
        print("  ! 가족 코드가 없어요. 설치를 다시 실행하거나 .env에 MALHAN_FAMILY_CODE를 넣어 주세요.")
    if llm.mode() == "none":
        print("  ! AI 없이 켜졌어요. 직접 적기·캘린더는 되고, 녹음·글에서 뽑기는 AI를 연결해야 해요 (Claude Code 로그인 또는 .env 키).")
    if best:
        try:
            import segno

            print()
            segno.make(best, error="m").terminal(compact=True, border=1)
        except Exception:
            pass
    print("  끄려면 이 창을 닫거나 Ctrl+C\n")
    serve()


def serve() -> None:
    """서버를 돌리고, 화면의 '업데이트'이나 새벽 자동 확인으로 업데이트를 받아 끝나면(RESTART_CODE) 새 코드로 다시 켠다."""
    import subprocess

    from server import updater

    args = [sys.executable, "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", str(PORT), "--log-level", "warning"]
    while True:
        try:
            code = subprocess.call(args, cwd=ROOT)
        except KeyboardInterrupt:
            return
        if code != updater.RESTART_CODE:
            sys.exit(code)
        try:
            ver = updater.git("rev-parse", "--short", "HEAD")
        except Exception:
            ver = "?"
        print(f"\n업데이트한 버전({ver})으로 다시 켭니다…\n", flush=True)


if __name__ == "__main__":
    main()
