from datetime import timedelta

from fastapi.testclient import TestClient

from server import app as appmod, db

client = TestClient(appmod.app)


def join(name="선"):
    r = client.post("/api/join", json={"name": name, "code": "우리집"})
    assert r.status_code == 200
    return r


def test_join_requires_code():
    c = TestClient(appmod.app)
    assert c.get("/api/me").status_code == 401
    assert c.post("/api/join", json={"name": "누구", "code": "틀림"}).status_code == 403


def test_text_input_becomes_candidates_then_moves_through_days():
    join()
    today = appmod.today()
    r = client.post("/api/inputs", data={"kind": "memo", "text": "토요일에 엄마한테 전화할게. 날씨 좋다. 수요일까지 준비물 챙겨야지."})
    assert r.status_code == 200
    iid = r.json()["id"]

    d = client.get("/api/day").json()
    assert d["is_today"] and len(d["new"]) == 2 and d["pending_inputs"] == 0
    inp = client.get(f"/api/inputs/{iid}").json()
    assert inp["status"] == "extracted" and len(inp["items"]) == 2 and "날씨" in inp["transcript"]

    a, b = d["new"][0]["id"], d["new"][1]["id"]
    assert client.patch(f"/api/items/{a}", json={"status": "todo"}).json()["plan_date"] == today.isoformat()
    assert client.patch(f"/api/items/{b}", json={"status": "later"}).json()["plan_date"] is None
    d = client.get("/api/day").json()
    assert [x["id"] for x in d["todo"]] == [a] and d["new"] == []
    assert [x["id"] for x in client.get("/api/items", params={"status": "later"}).json()] == [b]

    # 어제 하기로 했던 일은 오늘 화면에 넘어와 보이고, 어제 화면에도 남는다
    yday = (today - timedelta(days=1)).isoformat()
    with db.session() as con:
        con.execute("UPDATE items SET plan_date = ? WHERE id = ?", (yday, a))
    d = client.get("/api/day").json()
    assert d["todo"][0]["carried_days"] == 1
    assert [x["id"] for x in client.get("/api/day", params={"date": yday}).json()["todo"]] == [a]

    # 끝내면 오늘의 끝낸 일로 가고, 어제 화면에서는 빠진다
    client.patch(f"/api/items/{a}", json={"status": "done"})
    d = client.get("/api/day").json()
    assert d["todo"] == [] and [x["id"] for x in d["done"]] == [a]
    assert client.get("/api/day", params={"date": yday}).json()["todo"] == []
    wk = {x["date"]: x for x in client.get("/api/week").json()}
    assert wk[today.isoformat()]["done"] == 1 and len(wk) == 7

    s = client.post("/api/day/close").json()["summary"]
    assert s and client.get("/api/day").json()["summary"] == s


def test_reextract_keeps_chosen_items_and_skips_duplicates():
    join("재추출")
    iid = client.post("/api/inputs", data={"kind": "memo", "text": "우유 사야 해. 내일 은행 서류 챙겨야 해."}).json()["id"]
    new = client.get("/api/day").json()["new"]
    assert len(new) == 2
    client.patch(f"/api/items/{new[0]['id']}", json={"status": "todo"})
    client.patch(f"/api/inputs/{iid}", json={"reextract": True})
    items = client.get(f"/api/inputs/{iid}").json()["items"]
    assert len(items) == 2 and sorted(i["status"] for i in items) == ["new", "todo"]
    # 같은 내용을 한 번 더 넣어도 열려 있는 일과 겹치면 새로 만들지 않는다
    client.post("/api/inputs", data={"kind": "memo", "text": "우유 사야 해."})
    assert len(client.get("/api/day").json()["new"]) == 1


def test_speakers_detected_and_me_can_be_set():
    join("화자")
    text = "화자 1: 금요일까지 보내 주실 수 있나요?\n화자 2: 네, 제가 금요일까지 보내겠습니다."
    iid = client.post("/api/inputs", data={"kind": "call", "text": text}).json()["id"]
    inp = client.get(f"/api/inputs/{iid}").json()
    assert inp["speakers"] == ["화자 1", "화자 2"] and inp["me_speaker"] is None
    assert client.get("/api/day").json()["need_me"][0]["id"] == iid
    assert client.patch(f"/api/inputs/{iid}", json={"me_speaker": "없는 사람"}).status_code == 400
    assert client.patch(f"/api/inputs/{iid}", json={"me_speaker": "화자 2"}).json()["reextract"] is True
    assert client.get(f"/api/inputs/{iid}").json()["me_speaker"] == "화자 2"
    assert client.get("/api/day").json()["need_me"] == []


def test_text_file_upload_and_share_target():
    join("파일")
    r = client.post("/api/inputs", data={"kind": "file"}, files={"file": ("통화 녹음 홍길동.txt", "내일까지 견적서 보낼게요.".encode("cp949"), "text/plain")})
    assert r.status_code == 200
    inp = client.get(f"/api/inputs/{r.json()['id']}").json()
    assert inp["title"] == "통화 녹음 홍길동.txt" and "견적서" in inp["transcript"]
    r = client.post("/share", data={"title": "회의", "text": "회의록 정리해서 올려야 해."}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/?shared=1"
    assert len(client.get("/api/inputs").json()) == 2


def test_audio_without_stt_fails_with_reason():
    join("음성")
    r = client.post("/api/inputs", data={"kind": "memo"}, files={"file": ("memo.m4a", b"\x00\x01fake", "audio/mp4")})
    inp = client.get(f"/api/inputs/{r.json()['id']}").json()
    assert inp["status"] == "failed" and "음성 인식" in inp["error"]


def test_people_do_not_see_each_other():
    join("엄마")
    client.post("/api/items", json={"text": "엄마만 아는 일"})
    mine = client.get("/api/day").json()["todo"][0]["id"]
    join("아빠")
    assert client.get("/api/day").json()["todo"] == []
    assert client.patch(f"/api/items/{mine}", json={"status": "done"}).status_code == 404


def test_photo_is_read_then_extracted_and_removed():
    import io

    from PIL import Image

    join("사진")
    buf = io.BytesIO()
    Image.new("RGB", (3000, 2000), "white").save(buf, "JPEG")
    r = client.post("/api/inputs", data={"kind": "file"}, files={"file": ("가정통신문.jpg", buf.getvalue(), "image/jpeg")})
    assert r.status_code == 200
    inp = client.get(f"/api/inputs/{r.json()['id']}").json()
    assert inp["kind"] == "photo" and inp["status"] == "extracted" and len(inp["items"]) == 2
    assert not list((db.data_dir() / "audio").glob("*.jpg"))  # 사진은 글로 바꾼 뒤 남기지 않는다


def test_calendar_export_all_day_and_timed():
    join("캘린더")
    it = client.post("/api/items", json={"text": "치과 예약, 확인; 전화", "plan_date": "2026-11-12"}).json()
    links = client.get(f"/api/items/{it['id']}/calendar").json()
    assert "dates=20261112%2F20261113" in links["google_url"] and links["date"] == "2026-11-12"
    ics = client.get(links["ics_url"])
    assert ics.headers["content-type"].startswith("text/calendar")
    assert "DTSTART;VALUE=DATE:20261112\r\n" in ics.text and "SUMMARY:치과 예약\\, 확인\\; 전화\r\n" in ics.text
    assert "BEGIN:VALARM" in ics.text and "TRIGGER:PT9H" in ics.text

    links = client.get(f"/api/items/{it['id']}/calendar", params={"time": "15:00"}).json()
    assert "20261112T060000Z%2F20261112T063000Z" in links["google_url"]  # 서울 15:00 = UTC 06:00
    ics = client.get(links["ics_url"]).text
    assert "DTSTART:20261112T060000Z" in ics and "TRIGGER:-PT10M" in ics
    assert client.get(f"/api/items/{it['id']}/calendar", params={"time": "오후"}).status_code == 400


MEETING_REPLY = """{"summary": "출시 일정을 14일로 정했어요. 시험 결과는 금요일에 다시 봐요.",
 "items": [
  {"text": "시험 결과서 검토 의견 보내기", "owner": "me", "due": "14일", "dueDate": "2099-11-14", "time": "15:00", "scope": "회사", "quote": "제가 14일 3시까지 보내겠습니다."},
  {"text": "회의실 예약하기", "owner": "other", "who": "민수", "scope": "회사"},
  {"text": "고객사에 일정 알리기", "owner": "unclear", "who": "", "scope": "회사"}
 ]}"""


def test_meeting_keeps_summary_and_other_peoples_items_recoverable(monkeypatch):
    from server import llm

    monkeypatch.setattr(llm, "complete", lambda prompt, max_tokens=2000: MEETING_REPLY)
    join("회의")
    iid = client.post("/api/inputs", data={"kind": "meeting", "text": "화자 1: 제가 14일 3시까지 보내겠습니다.\n화자 2: 회의실은 민수 씨가요."}).json()["id"]
    inp = client.get(f"/api/inputs/{iid}").json()
    assert "출시 일정" in inp["summary"]
    by = {i["text"]: i for i in inp["items"]}
    assert by["회의실 예약하기"]["status"] == "other" and by["회의실 예약하기"]["who"] == "민수"
    assert by["고객사에 일정 알리기"]["status"] == "new" and by["고객사에 일정 알리기"]["owner"] == "unclear"

    day = client.get("/api/day").json()
    new = day["new"]
    assert sorted(i["text"] for i in new) == ["고객사에 일정 알리기", "시험 결과서 검토 의견 보내기"]  # 남의 일은 목록에 안 뜬다
    assert [b["id"] for b in day["briefs"]] == [iid] and "출시 일정" in day["briefs"][0]["summary"]   # 요약은 첫 화면에도 보인다
    assert client.get("/api/day", params={"date": "2000-01-01"}).json()["briefs"] == []                # 그날 넣은 것만
    assert client.get("/api/inputs").json()[0]["item_count"] == 2

    # '나'를 정해 다시 뽑아도 남의 일은 입력 안에 남아 있고, 내 일로 가져올 수 있다
    client.patch(f"/api/inputs/{iid}", json={"me_speaker": "화자 1"})
    other = next(i for i in client.get(f"/api/inputs/{iid}").json()["items"] if i["status"] == "other")
    got = client.patch(f"/api/items/{other['id']}", json={"status": "todo"}).json()
    assert got["status"] == "todo" and got["owner"] == "me"

    # 한 번에 넣기: 기한이 앞날이면 그 날짜로, 없으면 오늘로. 시각도 함께 간다
    assert client.post("/api/items/accept-all", json={}).json()["moved"] == 2
    d14 = client.get("/api/day", params={"date": "2099-11-14"}).json()["todo"]
    assert [i["text"] for i in d14] == ["시험 결과서 검토 의견 보내기"] and d14[0]["plan_time"] == "15:00"
    today_todo = [i["text"] for i in client.get("/api/day").json()["todo"]]
    assert "고객사에 일정 알리기" in today_todo and "회의실 예약하기" in today_todo
    links = client.get(f"/api/items/{d14[0]['id']}/calendar").json()
    assert "20991114T060000Z" in links["google_url"]  # 정해 둔 15:00(서울)이 일정 시각이 된다


def test_item_text_and_time_can_be_edited():
    join("고치기")
    it = client.post("/api/items", json={"text": "치과"}).json()
    r = client.patch(f"/api/items/{it['id']}", json={"text": "치과 예약 전화하기", "plan_time": "9:30", "plan_date": "2099-01-02"}).json()
    assert r["text"] == "치과 예약 전화하기" and r["plan_time"] == "09:30" and r["plan_date"] == "2099-01-02"
    assert client.patch(f"/api/items/{it['id']}", json={"plan_time": ""}).json()["plan_time"] is None
    assert client.patch(f"/api/items/{it['id']}", json={"plan_time": "25:99"}).status_code == 400


def test_old_database_gets_new_columns(tmp_path, monkeypatch):
    import sqlite3

    monkeypatch.setenv("MALHAN_DATA", str(tmp_path))
    con = sqlite3.connect(tmp_path / "malhandaero.db")
    con.executescript("""
      CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, token TEXT NOT NULL UNIQUE, created_at TEXT);
      CREATE TABLE inputs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT, title TEXT, source_name TEXT, received_date TEXT,
        media_path TEXT, transcript TEXT, speakers TEXT, me_speaker TEXT, status TEXT, error TEXT, created_at TEXT);
      CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, input_id INTEGER, text TEXT, quote TEXT, due_text TEXT, due_date TEXT,
        scope TEXT, status TEXT, plan_date TEXT, done_at TEXT, addon TEXT, record_id INTEGER, created_at TEXT, updated_at TEXT);
      INSERT INTO items(user_id, text, status) VALUES (1, '옛 항목', 'todo');
    """)
    con.commit(); con.close()
    db.init()
    with db.session() as c:
        row = c.execute("SELECT text, owner, plan_time FROM items").fetchone()
        assert (row["text"], row["owner"], row["plan_time"]) == ("옛 항목", "me", None)
        assert "summary" in {r["name"] for r in c.execute("PRAGMA table_info(inputs)")}


def test_qr_link_logs_in_my_other_device_once():
    join("큐알")
    client.post("/api/items", json={"text": "내 폰에서도 보여야 하는 일"})
    link = client.post("/api/link", json={"kind": "me"}).json()
    assert link["svg"].startswith("<svg") and "/l/" in link["url"] and link["minutes"] == 10
    token = link["url"].rsplit("/", 1)[1]
    phone = TestClient(appmod.app)                                   # 로그인 안 된 다른 기기
    r = phone.get(f"/l/{token}", follow_redirects=False)
    assert r.headers["location"] == "/?link=ok"
    assert [i["text"] for i in phone.get("/api/day").json()["todo"]] == ["내 폰에서도 보여야 하는 일"]
    other = TestClient(appmod.app)                                   # 같은 QR을 다른 사람이 다시 쓰면 안 된다
    assert other.get(f"/l/{token}", follow_redirects=False).headers["location"] == "/?link=expired"
    assert other.get("/api/me").status_code == 401


def test_family_invite_needs_only_a_name_and_expires(monkeypatch):
    from datetime import timedelta

    join("초대한사람")
    token = client.post("/api/link", json={"kind": "family"}).json()["url"].rsplit("/", 1)[1]
    guest = TestClient(appmod.app)
    assert guest.get(f"/l/{token}", follow_redirects=False).headers["location"] == f"/?invite={token}"
    assert guest.post("/api/join", json={"name": "초대받은사람", "invite": token}).status_code == 200   # 가족 코드 없이
    assert guest.get("/api/day").json()["todo"] == []                                                  # 목록은 따로
    appmod._links[token]["until"] -= timedelta(minutes=11)                                             # 시간이 지나면
    late = TestClient(appmod.app)
    assert late.post("/api/join", json={"name": "늦은사람", "invite": token}).status_code == 403
    assert late.post("/api/join", json={"name": "늦은사람", "invite": "아무값"}).status_code == 403


def test_qr_uses_outside_address_when_there_is_one(monkeypatch):
    join("주소")
    monkeypatch.setenv("MALHAN_PUBLIC_URL", "https://malhandaero.tail1234.ts.net/")
    link = client.post("/api/link", json={}).json()
    assert link["url"].startswith("https://malhandaero.tail1234.ts.net/l/") and link["secure"] is True
    monkeypatch.delenv("MALHAN_PUBLIC_URL")
    monkeypatch.setenv("MALHAN_LAN_URL", "http://192.168.0.12:8000")
    pc = TestClient(appmod.app, base_url="http://localhost:8000")
    pc.post("/api/join", json={"name": "주소", "code": "우리집"})
    link = pc.post("/api/link", json={}).json()
    assert link["url"].startswith("http://192.168.0.12:8000/l/") and link["secure"] is False           # PC에서 localhost로 열었어도 폰이 열 수 있는 주소를 준다
