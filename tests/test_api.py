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
    # 처음부터 다시 뽑기: 고른 것(todo)까지 지우고 새로 만든다
    client.patch(f"/api/inputs/{iid}", json={"reset": True})
    items = client.get(f"/api/inputs/{iid}").json()["items"]
    assert len(items) == 2 and all(i["status"] == "new" for i in items)


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


def test_audio_without_stt_fails_with_reason(monkeypatch):
    from server import stt

    monkeypatch.setattr(stt, "available", lambda: False)
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
  {"text": "시험 결과서 검토 의견 보내기", "owner": "me", "due": "14일", "dueDate": "2099-11-14", "time": "15:00", "scope": "회사", "quote": "제가 14일 3시까지 보내겠습니다.", "details": ["커버리지 표 확인", "의견 문서로 정리"]},
  {"text": "회의실 예약하기", "owner": "other", "who": "슈구리", "scope": "회사"},
  {"text": "고객사에 일정 알리기", "owner": "unclear", "who": "", "scope": "회사"}
 ],
 "minutes": {"topics": [{"topic": "출시 일정", "points": ["14일 출시로 정했어요."], "decisions": ["14일 출시"]}], "questions": ["고객사 통보 담당은 누구?"]}}"""


def test_meeting_keeps_summary_and_other_peoples_items_recoverable(monkeypatch):
    from server import llm

    monkeypatch.setattr(llm, "complete", lambda prompt, max_tokens=2000: MEETING_REPLY)
    join("회의")
    iid = client.post("/api/inputs", data={"kind": "meeting", "text": "화자 1: 제가 14일 3시까지 보내겠습니다.\n화자 2: 회의실은 슈구리 씨가요."}).json()["id"]
    inp = client.get(f"/api/inputs/{iid}").json()
    assert "출시 일정" in inp["summary"]
    assert inp["has_minutes"] and inp["minutes"]["topics"][0]["topic"] == "출시 일정" and inp["minutes"]["questions"] == ["고객사 통보 담당은 누구?"]
    by = {i["text"]: i for i in inp["items"]}
    assert by["시험 결과서 검토 의견 보내기"]["details"] == ["커버리지 표 확인", "의견 문서로 정리"]       # 세부는 상위 할 일 아래 묶인다
    md = client.get(f"/api/inputs/{iid}/minutes.md")
    assert md.status_code == 200 and "## 1. 출시 일정" in md.text and "- [ ] 회의실 예약하기 (슈구리)" in md.text and "    - 커버리지 표 확인" in md.text
    assert by["회의실 예약하기"]["status"] == "other" and by["회의실 예약하기"]["who"] == "슈구리"
    assert by["고객사에 일정 알리기"]["status"] == "new" and by["고객사에 일정 알리기"]["owner"] == "unclear"

    day = client.get("/api/day").json()
    new = day["new"]
    assert sorted(i["text"] for i in new) == ["고객사에 일정 알리기", "시험 결과서 검토 의견 보내기"]  # 남의 일은 목록에 안 뜬다
    assert [b["id"] for b in day["briefs"]] == [iid] and "출시 일정" in day["briefs"][0]["summary"]   # 요약은 첫 화면에도 보인다
    assert day["briefs"][0]["has_minutes"] == 1
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


def test_update_button_pulls_and_schedules_restart(monkeypatch):
    from server import updater

    join("새판")
    assert "version" in client.get("/api/me").json()
    calls = []
    monkeypatch.setattr(updater, "restart_soon", lambda delay=1.0: calls.append(delay))

    def fake_main(argv):
        updater.RESULT.update(updated=False, messages=["지금이 최신이에요 (abc1234)."], log=[], changed=[])
        return 0
    monkeypatch.setattr(updater, "main", fake_main)
    r = client.post("/api/update").json()
    assert r["restarting"] is False and "최신" in r["messages"][0] and calls == []       # 업데이트가 없으면 그대로 돈다

    def fake_main2(argv):
        updater.RESULT.update(updated=True, before="abc1234", after="def5678", messages=["업데이트했어요"], log=["화면 고침"], changed=["web/app.js"])
        return 0
    monkeypatch.setattr(updater, "main", fake_main2)
    r = client.post("/api/update").json()
    assert r["restarting"] is True and r["log"] == ["화면 고침"] and calls == [1.0]        # 업데이트면 받은 뒤 다시 켠다


def test_inputs_stuck_in_processing_resume_after_restart():
    join("재개")
    iid = client.post("/api/inputs", data={"kind": "memo", "text": "내일 은행 서류 챙겨야 해."}).json()["id"]
    with db.session() as con:  # 서버가 꺼져서 처리 중에 멈춘 상태를 만든다
        con.execute("UPDATE inputs SET status = 'extracting' WHERE id = ?", (iid,))
        con.execute("DELETE FROM items WHERE input_id = ?", (iid,))
    assert appmod.pending_count() == 1
    pend = client.get("/api/day").json()
    assert pend["pending_inputs"] == 1 and pend["pending"][0]["id"] == iid and pend["pending"][0]["long"] is False   # 화면이 '듣고 정리하는 중'을 보여 줄 재료
    assert appmod.resume_pending() == 1
    inp = client.get(f"/api/inputs/{iid}").json()
    assert inp["status"] == "extracted" and len(inp["items"]) == 1 and appmod.pending_count() == 0


def test_update_waits_for_processing_inputs(monkeypatch):
    from server import updater

    join("대기")
    iid = client.post("/api/inputs", data={"kind": "memo", "text": "x"}).json()["id"]
    with db.session() as con:
        con.execute("UPDATE inputs SET status = 'extracting' WHERE id = ?", (iid,))
    calls, idle = [], []
    monkeypatch.setattr(updater, "restart_soon", lambda delay=1.0: calls.append(delay))
    monkeypatch.setattr(appmod, "_restart_when_idle", lambda: idle.append(1))
    monkeypatch.setattr(updater, "main", lambda argv: updater.RESULT.update(updated=True, before="a", after="b", messages=["업데이트했어요"], log=[], changed=[]))
    r = client.post("/api/update").json()
    assert r["waiting"] == 1 and idle == [1] and calls == [] and "끝나면" in r["messages"][-1]   # 처리 중이면 바로 끄지 않는다


def test_skip_all_clears_new_items_of_one_input():
    join("치우기")
    a = client.post("/api/inputs", data={"kind": "memo", "text": "우유 사야 해. 빵 사야 해."}).json()["id"]
    b = client.post("/api/inputs", data={"kind": "memo", "text": "세탁소에서 옷 찾아 오는 거 잊지 말기."}).json()["id"]
    assert len(client.get("/api/day").json()["new"]) == 3
    r = client.post("/api/items/skip-all", json={"input_id": a}).json()
    assert r["skipped"] == 2 and len(r["ids"]) == 2
    left = client.get("/api/day").json()["new"]
    assert len(left) == 1 and left[0]["input_id"] == b
    assert client.post("/api/items/skip-all", json={}).json()["skipped"] == 1 and client.get("/api/day").json()["new"] == []
    assert client.post("/api/items/restore", json={"ids": r["ids"]}).json()["restored"] == 2       # 되돌리기
    assert sorted(i["input_id"] for i in client.get("/api/day").json()["new"]) == [a, a]


def test_stats_summarize_usage():
    join("수치")
    client.post("/api/inputs", data={"kind": "meeting", "text": "화자 1: 우유 사야 해.\n화자 2: 빵은 제가 사야 해요."})
    client.post("/api/items", json={"text": "직접 적은 일"})
    new = client.get("/api/day").json()["new"]
    client.patch(f"/api/items/{new[0]['id']}", json={"status": "skipped"})
    st = client.get("/api/stats", params={"days": 7}).json()
    assert st["inputs"]["total"] == 1 and st["inputs"]["by_kind"] == {"meeting": 1}
    assert st["seconds_to_list"]["median"] is not None and st["seconds_to_list"]["median"] >= 0
    assert st["items"]["manual"] == 1 and st["items"]["extracted_mine"] == 2 and st["items"]["skipped"] == 1 and st["items"]["skip_ratio"] == 0.5
    assert st["items"]["per_meeting"] == 2.0


def test_daily_note_is_opt_in_and_feeds_the_wrap_up(monkeypatch):
    from server import llm

    join("한줄")
    assert client.get("/api/me").json()["diary"] is False
    assert client.post("/api/settings/diary", json={"enabled": True}).json()["diary"] is True and client.get("/api/me").json()["diary"] is True
    r = client.post("/api/day/note", json={"note": "  저녁에 비가 와서 늦게 들어왔다  ", "mood": "😮‍💨"}).json()
    assert r["note"] == "저녁에 비가 와서 늦게 들어왔다" and r["mood"] == "😮‍💨"
    d0 = client.get("/api/day").json()
    assert d0["note"] == "저녁에 비가 와서 늦게 들어왔다" and d0["mood"] == "😮‍💨"
    seen = {}
    monkeypatch.setattr(llm, "complete", lambda prompt, max_tokens=2000: seen.setdefault("p", prompt) and "비 오는 날 하루를 마쳤어요.")
    client.post("/api/items", json={"text": "우산 사기"})
    r = client.post("/api/day/close").json()
    assert "오늘 한 줄:\n😮‍💨 저녁에 비가 와서 늦게 들어왔다" in seen["p"] and r["summary"].startswith("비 오는 날")
    d = client.get("/api/day").json()
    assert d["summary"] == "비 오는 날 하루를 마쳤어요." and d["note"] == "저녁에 비가 와서 늦게 들어왔다" and d["mood"] == "😮‍💨"   # 마무리를 써도 한 줄은 남는다
    assert client.post("/api/day/note", json={"mood": "😊"}).json() == {"date": d["date"], "note": "", "mood": "😊"}   # 이모지만도 된다


def test_month_view_scores_days_and_streak(monkeypatch):
    from server import app as appmod
    monkeypatch.setenv("MALHAN_POST_URL", "https://example.com/post/1")
    join("달력")
    t = appmod.today()
    a = client.post("/api/items", json={"text": "하나"}).json()
    b = client.post("/api/items", json={"text": "둘"}).json()
    c = client.post("/api/items", json={"text": "셋"}).json()
    for it in (a, b, c):
        client.patch(f"/api/items/{it['id']}", json={"status": "done"})
    client.post("/api/items", json={"text": "남은 것"})
    client.post("/api/day/note", json={"mood": "😊"})
    m = client.get("/api/month").json()
    assert m["ym"] == t.strftime("%Y-%m") and m["post_url"] == "https://example.com/post/1"
    day = next(d for d in m["days"] if d["date"] == t.isoformat())
    assert day["done"] == 3 and day["left"] == 1 and day["mood"] == "😊" and day["closed"] is False
    assert day["score"] == 4                     # 넣음 1 + 마침 2(3건) + 한 줄 1
    assert m["active_days"] == 1 and m["streak"] == 1 and m["done_total"] == 3 and m["left_total"] == 1
    assert m["score"] == round(100 * 4 / (4 * m["elapsed_days"]))          # 한 줄을 안 켰으면 만점 4
    client.post("/api/settings/diary", json={"enabled": True})
    assert client.get("/api/month").json()["score"] == round(100 * 4 / (5 * m["elapsed_days"]))
    assert appmod.day_score(0, 0, False, False) == 0 and appmod.day_score(1, 1, True, True) == 4
    assert client.get("/api/month?ym=2020-13").status_code == 400
    assert client.get("/api/month?ym=2020-02").json()["days"][-1]["date"] == "2020-02-29"
