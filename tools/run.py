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
    return shutil.which("tailscale") or (mac_app if os.path.exists(mac_app) else None)


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

    names = {"claude": "이 PC의 Claude Code (API 결제 없음)", "anthropic": "API 키", "fake": "흉내 모드 (화면 확인용, 부정확)", "none": "연결 안 됨"}
    print("\n말한대로를 켭니다.")
    print(f"  이 PC에서        http://localhost:{PORT}")
    ip = lan_ip()
    if ip and not ip.startswith("127."):
        print(f"  같은 와이파이 폰  http://{ip}:{PORT}")
    if ip and not ip.startswith("127."):
        os.environ["MALHAN_LAN_URL"] = f"http://{ip}:{PORT}"
    best = os.environ.get("MALHAN_LAN_URL", "")
    ts = tailscale_bin()
    local_only = "--local" in sys.argv
    if local_only:
        print("  집 밖 주소        꺼짐 (--local)")
    elif not ts:
        print("  집 밖 주소        없음. Tailscale을 설치하면 집 밖에서도 쓸 수 있어요 (INSTALL.md)")
    else:
        name = tailscale_name(ts)
        if not name:
            print("  집 밖 주소        Tailscale이 꺼져 있거나 로그인되지 않았어요.")
        else:
            ok, detail = open_remote(ts)
            if ok:
                best = f"https://{name}"
                os.environ["MALHAN_PUBLIC_URL"] = best
                print(f"  집 밖 주소        {best}   (Tailscale을 켠 내 기기에서만 열려요)")
            else:
                print(f"  집 밖 주소        열지 못했어요. 터미널에서 직접 실행해 보세요: tailscale serve --bg {PORT}")
                if detail:
                    print("                   " + detail.splitlines()[0][:150])
    print(f"  AI 연결          {names.get(llm.mode(), llm.mode())}")
    print(f"  녹음 파일 변환    {'켜짐' if stt.available() else '꺼짐 (글·사진·말하기는 됩니다)'}")
    if not os.environ.get("MALHAN_FAMILY_CODE"):
        print("  ! 가족 코드가 없어요. 설치를 다시 실행하거나 .env에 MALHAN_FAMILY_CODE를 넣어 주세요.")
    if llm.mode() == "none":
        print("  ! AI가 연결되지 않았어요. Claude Code에 로그인하거나 .env에 키를 넣어 주세요.")
    if best:
        try:
            import segno

            print("\n  휴대폰 카메라로 찍으면 열려요: " + best)
            segno.make(best, error="m").terminal(compact=True, border=1)
        except Exception:
            pass
    print("  끄려면 이 창을 닫거나 Ctrl+C\n")
    uvicorn.run("server.app:app", host="0.0.0.0", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
