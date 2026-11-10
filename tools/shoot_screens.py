"""포스터용 실제 화면 캡처. 임시 data/ 에 보기용 자료를 넣고 앱을 켠 뒤, 폰 크기 브라우저로 찍는다.

실행: python tools/shoot_screens.py [out_dir]   (playwright + Chrome 필요: pip install playwright)
결과: out_dir/{today,add,inputs,minutes,calendar,month}.png  (390×844 @2x)
이름·내용은 전부 예시(무당이·슈구리). 실제 data/ 는 건드리지 않는다.
"""
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "docs" / "img" / "screens")
PORT = 8765
TODAY = date.today()
D = TODAY.isoformat()


def seed(data_dir: Path) -> None:
    sys.path.insert(0, str(ROOT))
    from server import db
    db.init()
    con = sqlite3.connect(data_dir / "malhandaero.db")
    con.execute("INSERT INTO users(name, token) VALUES ('나', 'tok')")
    uid = con.execute("SELECT id FROM users").fetchone()[0]
    y = (TODAY - timedelta(days=1)).isoformat()
    minutes = {
        "attendees": ["나", "무당이"],
        "topics": [
            {"topic": "출시 일정", "points": ["기존 일정은 테스트 기간이 2주뿐이에요", "개발팀도 이번 주 코드 정리를 계획했어요"], "decisions": ["코드 프리즈를 약 1주 앞당겨요"]},
            {"topic": "테스트 범위", "points": ["기능별로 다 만들면 케이스가 너무 많아져요", "단순 기능은 케이스가 많아도 괜찮아요"], "decisions": ["시나리오 기반으로 테스트해요", "케이스 수는 소요 시간을 보고 정해요"]},
            {"topic": "고객 시연", "points": ["시연 일정과 테스트 기간은 겹치지 않아요"]},
        ],
        "questions": ["외부 자료 도착 시점은 아직 몰라요"],
    }
    inputs = [
        ("call", "통화 무당이_261110.txt", "출시 일정과 테스트 범위를 정했어요.", minutes, D),
        ("call", "통화 슈구리_261110.txt", "점심 메뉴 주문 통화", {}, D),
        ("meeting", "1109_계획 리뷰 회의.txt", "계획 리뷰 — 범위를 먼저 정하고 나머지는 후속", {}, y),
        ("call", "통화 남편_261109_210146_original.txt", "주차 문제 상의", {}, y),
        ("memo", "음성 메모_261109_234522_original.txt", "내일 공유 자료 챙기기", {}, y),
    ]
    ids = []
    for kind, title, summary, m, day in inputs:
        cur = con.execute(
            "INSERT INTO inputs(user_id, kind, title, source_name, received_date, transcript, status, summary, minutes, done_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (uid, kind, title, title, day, "(녹취 본문)", "extracted", summary, json.dumps(m, ensure_ascii=False) if m else "", f"{day} 18:00:00"),
        )
        ids.append(cur.lastrowid)
    items = [
        # text, scope, status, plan_date, done_at, input_id, owner, who, due_text, cal_ref
        ("교육생 공유 자료 전달하기", "회사", "todo", D, None, ids[4], "me", "", "", None),
        ("공모전 출품하기", "개인", "todo", (TODAY - timedelta(days=1)).isoformat(), None, None, "me", "", "", None),   # 어제에서 넘어옴
        ("시나리오 목록 초안 공유하기", "회사", "todo", (TODAY + timedelta(days=3)).isoformat(), None, ids[0], "me", "", "금요일까지", None),
        ("일정표 갱신해 공지하기", "회사", "other", None, None, ids[0], "other", "무당이", "", None),
        ("외부 자료 도착 시점 확인해 알려 주기", "회사", "other", None, None, ids[0], "other", "슈구리", "이번 주", None),
        ("집에 가는 길에 기름 넣기", "개인", "done", D, f"{D} 18:40:00", None, "me", "", "", None),
        ("견적서 검토 의견 보내기", "회사", "done", D, f"{D} 17:10:00", ids[2], "me", "", "", "cal:2"),
        ("점심 메뉴 주문하기", "개인", "done", D, f"{D} 11:50:00", ids[1], "me", "", "", None),
        ("주차 자리 확인하기", "개인", "done", D, f"{D} 09:00:00", ids[3], "me", "", "", None),
    ]
    for t in items:
        con.execute(
            "INSERT INTO items(user_id, text, scope, status, plan_date, done_at, input_id, owner, who, due_text, cal_ref) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (uid, *t),
        )
    # 캘린더에서 「할 일로」 가져온 일 하나 (화면에 '할 일로 들어옴'이 보이게)
    con.execute("INSERT INTO items(user_id, text, scope, status, plan_date, plan_time, owner, addon, cal_ref) VALUES (?,?,?,?,?,?,?,?,?)",
                (uid, "고객 사전 회의", "회사", "todo", D, "11:00", "me", "calendar", "cal:1"))
    # 지난 날들: 달력 칸과 식물 카드용
    for back, done_n, left_n, mood in [(1, 3, 0, "😊"), (2, 4, 1, "🔥"), (3, 1, 2, ""), (4, 3, 0, "😌"), (5, 2, 0, "😊"), (6, 3, 1, "😌")]:
        day = (TODAY - timedelta(days=back)).isoformat()
        for i in range(done_n):
            con.execute("INSERT INTO items(user_id, text, scope, status, plan_date, done_at) VALUES (?,?,?,?,?,?)", (uid, f"지난 일 {back}-{i}", "회사", "done", day, f"{day} 18:00:00"))
        for i in range(left_n):
            con.execute("INSERT INTO items(user_id, text, scope, status, plan_date) VALUES (?,?,?,?,?)", (uid, f"미룬 일 {back}-{i}", "개인", "later", day))
        con.execute("INSERT INTO day_logs(user_id, date, summary, note, mood) VALUES (?,?,?,?,?)", (uid, day, "정리 글", "잘 버텼다", mood))
    con.execute("INSERT INTO addon_settings(user_id, addon, enabled, options) VALUES (?,?,?,?)", (uid, "diary", 1, "{}"))
    con.commit()
    con.close()


EVENTS_FEW = [("ev2", "주간 이슈 리뷰", "10:00"), ("ev5", "팀 점심", "12:00")]
EVENTS_MANY = None   # fake_calendar()가 채운다
EVENTS = {"now": EVENTS_FEW}


def fake_calendar():
    global EVENTS_MANY
    from server import calsync, llm
    llm.mode = lambda: "claude"   # "흉내 모드" 안내가 화면에 뜨지 않게 (AI를 부를 일은 없다)
    calsync.get_link = lambda user_id: {"provider": "google", "config": {}, "label": "구글", "mode": "timed", "read_source": {}, "write_target": {}}
    EVENTS_MANY = [
        ("ev1", "슈구리 연차", None),
        ("ev2", "주간 이슈 리뷰", "10:00"),
        ("ev3", "자동화 현황 공유", "10:00"),
        ("cal:1", "고객 사전 회의", "11:00"),
        ("ev5", "팀 점심", "12:00"),
        ("ev6", "교육 준비 회의", "14:00"),
        ("ev7", "시연 리허설", "16:00"),
    ]
    calsync.day_events = lambda link, day: [{"ref": r, "title": t, "time": tm, "description": "", "uid": r} for r, t, tm in EVENTS["now"]] if day == TODAY else []


def serve():
    import uvicorn
    from server import app as appmod
    uvicorn.run(appmod.app, host="127.0.0.1", port=PORT, log_level="error")


def main() -> None:
    data = Path(tempfile.mkdtemp(prefix="malhan-shoot-"))
    os.environ.update({
        "MALHAN_DATA": str(data), "MALHAN_AI": "fake", "MALHAN_FAMILY_CODE": "1234", "MALHAN_STT": "0",
        "MALHAN_AUTO_UPDATE": "0", "MALHAN_PORT": str(PORT), "MALHAN_LABEL": "", "MALHAN_POST_URL": "",
    })
    seed(data)
    fake_calendar()
    threading.Thread(target=serve, daemon=True).start()
    time.sleep(2.5)

    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    base = f"http://127.0.0.1:{PORT}"
    ua = "Mozilla/5.0 (Linux; Android 14; SM-S921N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"
    with sync_playwright() as p:
        br = p.chromium.launch(channel="chrome", args=["--no-sandbox"])
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, user_agent=ua, locale="ko-KR")
        ctx.add_cookies([{"name": "mh_token", "value": "tok", "url": base}])
        ctx.add_init_script("try{localStorage.setItem('installbar-off','1')}catch(e){}")
        pg = ctx.new_page()
        pg.goto(base + "/")
        pg.wait_for_selector(".tabs")
        pg.wait_for_timeout(1200)

        def shot(name):
            pg.wait_for_timeout(500)
            pg.screenshot(path=str(OUT / f"{name}.png"))
            print("·", name)

        pg.evaluate("window.scrollTo(0,0)")
        shot("today")                                   # 오늘: 캘린더 일정 + 오늘 + 끝낸 일
        pg.click("#btn-add"); pg.wait_for_timeout(600); shot("add")     # 할 일 넣기 시트
        pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
        try:
            pg.click("#sheet .sheet-back", timeout=800)
        except Exception:
            pass
        pg.click('.tabs button[data-tab="inputs"]'); pg.wait_for_timeout(900); shot("inputs")   # 넣은 것
        pg.locator("li", has_text="통화 무당이").locator("text=열어 보기").first.click(); pg.wait_for_timeout(900)
        pg.evaluate("var m=document.querySelector('.minutes'); if(m){window.scrollTo(0, m.getBoundingClientRect().top + window.scrollY - 64);}")
        shot("minutes")                                 # 회의록
        pg.click('.tabs button[data-tab="month"]'); pg.wait_for_timeout(900); shot("month")      # 달력
        EVENTS["now"] = EVENTS_MANY
        pg.click('.tabs button[data-tab="today"]'); pg.wait_for_timeout(900)
        pg.evaluate("window.scrollTo(0,0)")
        shot("calendar")                                # 캘린더 일정 7건이 위에 보이는 오늘
        br.close()
    print(f"\n{OUT}")


if __name__ == "__main__":
    main()
