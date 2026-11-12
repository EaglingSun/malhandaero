"""게시글 맨 위에 붙일 움직이는 그림: 「말하기」 → 들은 말 → 오늘 화면에 할 일.

실행: python tools/shoot_gif.py [out.gif]      (playwright + Chrome + Pillow 필요)
결과: docs/img/poster/talk.gif (390×844, 약 12초). 보기용 자료는 tools/shoot_screens.py와 같고 실제 data/는 건드리지 않는다.
브라우저 음성 인식은 headless에서 안 되므로 듣는 화면은 글자를 한 어절씩 넣어 흉내 내고, AI 추출은 정해진 답으로 바꿔 끼운다.
"""
import io
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import shoot_screens as ss  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "docs" / "img" / "poster" / "talk.gif")
SPOKEN = "금요일까지 견적서 보내 주기로 했고, 퇴근길에 우유 사 가야 돼요."


def fake_extract():
    from server import extract
    cands = [
        extract.Candidate(text="견적서 보내기", quote="금요일까지 견적서 보내 주기로 했고", due_text="금요일까지", scope="회사"),
        extract.Candidate(text="퇴근길에 우유 사기", quote="퇴근길에 우유 사 가야 돼요", scope="개인"),
    ]
    extract.extract = lambda text, ctx: ("금요일까지 견적서, 퇴근길에 우유.", cands, {})


def main() -> None:
    data = Path(tempfile.mkdtemp(prefix="malhan-gif-"))
    os.environ.update({
        "MALHAN_DATA": str(data), "MALHAN_AI": "fake", "MALHAN_FAMILY_CODE": "1234", "MALHAN_STT": "0",
        "MALHAN_AUTO_UPDATE": "0", "MALHAN_PORT": str(ss.PORT), "MALHAN_LABEL": "", "MALHAN_POST_URL": "",
    })
    ss.seed(data)
    ss.fake_calendar()
    fake_extract()
    threading.Thread(target=ss.serve, daemon=True).start()
    time.sleep(2.5)

    from PIL import Image
    from playwright.sync_api import sync_playwright
    base = f"http://127.0.0.1:{ss.PORT}"
    ua = "Mozilla/5.0 (Linux; Android 14; SM-S921N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"
    frames: list[tuple[Image.Image, int]] = []   # (그림, 머무는 ms)

    with sync_playwright() as p:
        br = p.chromium.launch(channel="chrome", args=["--no-sandbox"])
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True, user_agent=ua, locale="ko-KR")
        ctx.add_cookies([{"name": "mh_token", "value": "tok", "url": base}])
        ctx.add_init_script("try{localStorage.setItem('installbar-off','1')}catch(e){}")
        pg = ctx.new_page()
        pg.goto(base + "/")
        pg.wait_for_selector(".tabs")
        pg.wait_for_timeout(1200)

        def frame(ms, wait=150):
            pg.wait_for_timeout(wait)
            frames.append((Image.open(io.BytesIO(pg.screenshot())).convert("RGB"), ms))

        pg.evaluate("window.scrollTo(0,0)")
        frame(1400)                                                    # 오늘
        pg.click("#btn-add"); pg.wait_for_timeout(500)
        frame(900)                                                     # 할 일 넣기 시트
        # 듣는 중: 단추가 빨갛게, 들은 말이 한 어절씩
        pg.evaluate("""() => { const b=document.getElementById('btn-mic'); b.classList.add('rec');
            const m=document.getElementById('mic-msg'); m.classList.add('live'); m.textContent=''; }""")
        words = SPOKEN.split(" ")
        for i in range(len(words) + 1):
            sec = i * 0.7
            pg.evaluate("""([t, s]) => { document.getElementById('btn-mic').innerHTML = '<b>다 말했어요</b><small>듣는 중 00:' + String(s).padStart(2,'0') + '</small>';
                document.getElementById('mic-msg').textContent = t; }""", [" ".join(words[:i]), int(sec)])
            frame(420, 60)
        frame(700, 60)
        # 다 말했어요 → 서버로 보내고 시트가 닫힌다
        pg.evaluate("""(t) => { const b=document.getElementById('btn-mic'); b.classList.remove('rec'); b.innerHTML='<b>말하기</b><small>누르고 말하면 끝</small>';
            const m=document.getElementById('mic-msg'); m.classList.remove('live'); m.textContent='';
            const fd=new FormData(); fd.append('kind','memo'); fd.append('title','말로 한 메모'); fd.append('text',t); fd.append('on', new Date().toISOString().slice(0,10));
            return fetch('/api/inputs',{method:'POST',body:fd}).then(r=>r.json()); }""", SPOKEN)
        try:
            pg.click("#sheet .sheet-back", timeout=800)
        except Exception:
            pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)
        pg.click('.tabs button[data-tab="today"]'); pg.wait_for_timeout(600)
        pg.evaluate("window.scrollTo(0,0)")
        frame(900)                                                     # 적어 두는 중
        pg.wait_for_timeout(3200)                                      # 뒤에서 뽑힌 것이 화면에 올 때까지(2.5초 주기)
        pg.evaluate("""() => { const s=document.getElementById('s-new'); if (s && !s.hidden) window.scrollTo(0, s.getBoundingClientRect().top + window.scrollY - 70); }""")
        frame(2200)                                                    # 대신 적어 뒀어요 2건
        try:
            pg.click("#s-new >> text=모두 넣기", timeout=1500); pg.wait_for_timeout(900)
            pg.evaluate("window.scrollTo(0,0)")
            frame(2600)                                                # 오늘 할 일에 들어감
        except Exception:
            pass
        br.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    ims = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT) for f, _ in frames]
    ims[0].save(OUT, save_all=True, append_images=ims[1:], duration=[ms for _, ms in frames], loop=0, optimize=True)
    print(f"{OUT}  {len(frames)}장  {OUT.stat().st_size // 1024}KB")


if __name__ == "__main__":
    main()
