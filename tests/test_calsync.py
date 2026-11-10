"""캘린더 자동 넣기: 진짜 네이버·구글 대신 같은 규약으로 답하는 작은 서버를 띄워 확인한다."""
import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from server import app as appmod

client = TestClient(appmod.app)
GOOD = "Basic " + base64.b64encode(b"sun:app-pass").decode()


class FakeCalendars(BaseHTTPRequestHandler):
    store: dict = {}       # 네이버: 주소 → ics
    events: dict = {}      # 구글: id → 본문
    seen: list = []

    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", ctype="application/xml"):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def _body(self):
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    # ---- 네이버 CalDAV ----
    def do_PROPFIND(self):
        self._body()
        if self.headers.get("Authorization") != GOOD:
            return self._send(401)
        ms = '<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">%s</d:multistatus>'
        if self.path == "/":
            x = "<d:response><d:href>/</d:href><d:propstat><d:prop><d:current-user-principal><d:href>/principals/users/sun/</d:href></d:current-user-principal></d:prop></d:propstat></d:response>"
        elif self.path == "/principals/users/sun/":
            x = "<d:response><d:href>/principals/users/sun/</d:href><d:propstat><d:prop><c:calendar-home-set><d:href>/caldav/sun/calendar/</d:href></c:calendar-home-set></d:prop></d:propstat></d:response>"
        else:
            x = ("<d:response><d:href>/caldav/sun/calendar/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>"
                 "<d:response><d:href>/caldav/sun/calendar/todo/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/><c:calendar/></d:resourcetype><d:displayname>할 일</d:displayname>"
                 "<c:supported-calendar-component-set><c:comp name=\"VTODO\"/></c:supported-calendar-component-set></d:prop></d:propstat></d:response>"
                 "<d:response><d:href>/caldav/sun/calendar/111/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/><c:calendar/></d:resourcetype><d:displayname>내 캘린더</d:displayname>"
                 "<c:supported-calendar-component-set><c:comp name=\"VEVENT\"/></c:supported-calendar-component-set></d:prop></d:propstat></d:response>")
        self._send(207, (ms % x).encode())

    def do_REPORT(self):
        self._body()
        if self.headers.get("Authorization") != GOOD:
            return self._send(401)
        ics = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:ev-1@naver\r\nDTSTART;TZID=Asia/Seoul:20990301T140000\r\nDTEND;TZID=Asia/Seoul:20990301T150000\r\n"
               "SUMMARY:주간 회의\\, 2층\r\nDESCRIPTION:안건 공유\r\nEND:VEVENT\r\nEND:VCALENDAR")
        ours = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:malhandaero-7@malhandaero\r\nDTSTART:20990301T060000Z\r\nSUMMARY:우유 사기\r\nDESCRIPTION:말한대로에서 보냄\r\nEND:VEVENT\r\nEND:VCALENDAR")
        allday = "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:ev-2@naver\r\nDTSTART;VALUE=DATE:20990301\r\nSUMMARY:창립기념일\r\nEND:VEVENT\r\nEND:VCALENDAR"
        def resp(href, body):
            return f"<d:response><d:href>{href}</d:href><d:propstat><d:prop><c:calendar-data><![CDATA[{body}]]></c:calendar-data></d:prop></d:propstat></d:response>"
        ms = ('<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">' + resp("/caldav/sun/calendar/111/ev1.ics", ics)
              + resp("/caldav/sun/calendar/111/malhandaero-7.ics", ours) + resp("/caldav/sun/calendar/111/ev2.ics", allday) + "</d:multistatus>")
        self._send(207, ms.encode())

    def do_GET(self):
        if self.path.startswith("/g/users/me/calendarList") and self.headers.get("Authorization") == "Bearer at":
            return self._send(200, json.dumps({"items": [{"id": "primary-id", "summary": "Sun", "primary": True}, {"id": "team@group.calendar.google.com", "summary": "팀 공유 일정"}]}).encode(), "application/json")
        if self.path.startswith("/g/calendars/team%40group.calendar.google.com/events?") and self.headers.get("Authorization") == "Bearer at":
            return self._send(200, json.dumps({"items": [{"id": "t1", "summary": "팀 주간 회의", "start": {"dateTime": "2099-05-05T14:00:00+09:00"}}]}).encode(), "application/json")
        if self.path.startswith("/g/calendars/primary/events?") and self.headers.get("Authorization") == "Bearer at":
            q = parse_qs(urlparse(self.path).query)
            day = q.get("timeMin", [""])[0][:10]
            dyn = [{"id": k, **v} for k, v in FakeCalendars.events.items()
                   if v.get("_calendar") in (None, "primary") and (not v.get("start") or (v["start"].get("dateTime") or v["start"].get("date") or "")[:10] >= day)]
            items = dyn + [{"id": "g1", "summary": "고객 미팅", "start": {"dateTime": "2099-05-05T10:00:00+09:00"}, "end": {"dateTime": "2099-05-05T11:00:00+09:00"}},
                     {"id": "g2", "summary": "휴가", "start": {"date": "2099-05-05"}},
                     {"id": "ev9", "summary": "회의 자료 보내기", "description": "근거 문장", "extendedProperties": {"private": {"malhandaero": "1"}}, "start": {"dateTime": "2099-05-05T09:30:00+09:00"}},
                     {"id": "g3", "status": "cancelled", "summary": "취소됨", "start": {"dateTime": "2099-05-05T12:00:00+09:00"}}]
            return self._send(200, json.dumps({"items": items}).encode(), "application/json")
        self._send(404)

    def do_PUT(self):
        body = self._body()
        if self.headers.get("Authorization") != GOOD:
            return self._send(401)
        FakeCalendars.store[self.path] = body.decode()
        self._send(201)

    def do_DELETE(self):
        if self.path.startswith("/g/"):
            FakeCalendars.events.pop(self.path.rsplit("/", 1)[1], None)
            return self._send(204)
        FakeCalendars.store.pop(self.path, None)
        self._send(204)

    # ---- 구글 ----
    def do_POST(self):
        body = self._body()
        if self.path == "/token":
            q = parse_qs(body.decode())
            FakeCalendars.seen.append(q)
            if q.get("grant_type") == ["authorization_code"] and q.get("code") == ["good-code"]:
                return self._send(200, json.dumps({"access_token": "at", "refresh_token": "rt-1"}).encode(), "application/json")
            if q.get("grant_type") == ["refresh_token"] and q.get("refresh_token") == ["rt-1"]:
                return self._send(200, json.dumps({"access_token": "at"}).encode(), "application/json")
            return self._send(400, json.dumps({"error": "invalid_grant"}).encode(), "application/json")
        if self.path.startswith("/g/calendars/") and self.path.endswith("/events") and self.headers.get("Authorization") == "Bearer at":
            eid = f"ev{len(FakeCalendars.events) + 1}"
            FakeCalendars.events[eid] = {**json.loads(body), "_calendar": self.path.split("/")[3]}
            return self._send(200, json.dumps({"id": eid}).encode(), "application/json")
        self._send(404)

    def do_PATCH(self):
        body = self._body()
        eid = self.path.rsplit("/", 1)[1]
        if eid not in FakeCalendars.events:
            return self._send(404)
        FakeCalendars.events[eid] = json.loads(body)
        self._send(200, b"{}", "application/json")


@pytest.fixture(scope="module")
def fake():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeCalendars)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()
    srv.server_close()


def join(name):
    assert client.post("/api/join", json={"name": name, "code": "우리집"}).status_code == 200


def test_naver_link_then_items_follow_into_calendar(fake, monkeypatch):
    monkeypatch.setenv("MALHAN_NAVER_CALDAV", fake)
    FakeCalendars.store.clear()
    join("네이버")
    r = client.post("/api/calendar/naver", json={"user": "sun", "password": "틀린비번"})
    assert r.status_code == 400 and "애플리케이션 비밀번호" in r.json()["detail"]
    r = client.post("/api/calendar/naver", json={"user": "sun@naver.com", "password": "app-pass"}).json()
    assert r["provider"] == "naver" and r["label"] == "내 캘린더" and [c["name"] for c in r["calendars"]] == ["내 캘린더"]  # 할 일 전용은 뺀다

    # 기본 설정은 '시각을 정한 일만': 시각 없는 일은 캘린더에 안 간다
    a = client.post("/api/items", json={"text": "우유 사기", "plan_date": "2099-03-01"}).json()
    assert FakeCalendars.store == {}
    client.patch(f"/api/items/{a['id']}", json={"plan_time": "15:00"})
    path = f"/caldav/sun/calendar/111/malhandaero-{a['id']}.ics"
    assert "SUMMARY:우유 사기" in FakeCalendars.store[path] and "DTSTART:20990301T060000Z" in FakeCalendars.store[path]
    assert client.get("/api/day", params={"date": "2099-03-01"}).json()["todo"][0]["cal_ref"].endswith(path)

    client.patch(f"/api/items/{a['id']}", json={"text": "우유랑 달걀 사기"})       # 고치면 캘린더도 바뀐다
    assert "SUMMARY:우유랑 달걀 사기" in FakeCalendars.store[path]
    client.patch(f"/api/items/{a['id']}", json={"status": "done"})                 # 끝내도 기록은 남긴다
    assert path in FakeCalendars.store
    client.patch(f"/api/items/{a['id']}", json={"status": "later"})                # 미루면 캘린더에서 뺀다
    assert path not in FakeCalendars.store

    # '날짜가 정해진 모든 일'로 바꾸면 시각 없는 앞날의 일도 들어간다
    b = client.post("/api/items", json={"text": "책 반납", "plan_date": "2099-03-02"}).json()
    assert client.post("/api/calendar/mode", json={"mode": "all"}).json()["mode"] == "all"
    bpath = f"/caldav/sun/calendar/111/malhandaero-{b['id']}.ics"
    assert "DTSTART;VALUE=DATE:20990302" in FakeCalendars.store[bpath]
    client.delete(f"/api/items/{b['id']}")                                         # 지우면 캘린더에서도 지운다
    assert bpath not in FakeCalendars.store

    assert client.delete("/api/calendar").json()["provider"] == ""


def test_calendar_failure_never_blocks_the_todo(fake, monkeypatch):
    monkeypatch.setenv("MALHAN_NAVER_CALDAV", fake)
    join("끊김")
    client.post("/api/calendar/naver", json={"user": "sun", "password": "app-pass"})
    from server import db
    with db.session() as con:  # 저장된 캘린더 주소를 닿지 않는 곳으로 바꿔 '서버가 죽은' 상황을 만든다
        con.execute("UPDATE calendar_links SET config = replace(config, ?, 'http://127.0.0.1:9') WHERE provider = 'naver' AND status = ''", (fake,))
    r = client.post("/api/items", json={"text": "전화하기", "plan_date": "2099-01-01"})
    client.patch(f"/api/items/{r.json()['id']}", json={"plan_time": "10:00"})
    assert client.get("/api/day", params={"date": "2099-01-01"}).json()["todo"][0]["plan_time"] == "10:00"
    assert "닿지 못했어요" in client.get("/api/calendar").json()["status"]


def test_google_oauth_round_trip_and_event_sync(fake, monkeypatch):
    for k, v in {"MALHAN_GOOGLE_CLIENT_ID": "cid", "MALHAN_GOOGLE_CLIENT_SECRET": "sec",
                 "MALHAN_GOOGLE_TOKEN_URL": fake + "/token", "MALHAN_GOOGLE_API": fake + "/g"}.items():
        monkeypatch.setenv(k, v)
    FakeCalendars.events.clear(); FakeCalendars.seen.clear()
    join("구글")
    assert client.get("/api/calendar").json()["google_ready"] is True
    r = client.get("/api/calendar/google/start", follow_redirects=False)
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert r.status_code == 303 and q["client_id"] == ["cid"] and q["access_type"] == ["offline"]
    assert q["redirect_uri"] == ["http://testserver/api/calendar/google/callback"]

    bad = client.get("/api/calendar/google/callback", params={"code": "good-code", "state": "다른값"}, follow_redirects=False)
    assert bad.headers["location"] == "/?cal=fail"                                   # 내가 시작한 요청이 아니면 받지 않는다
    ok = client.get("/api/calendar/google/callback", params={"code": "good-code", "state": q["state"][0]}, follow_redirects=False)
    assert ok.headers["location"] == "/?cal=ok" and client.get("/api/calendar").json()["provider"] == "google"
    assert FakeCalendars.seen[0]["redirect_uri"] == ["http://testserver/api/calendar/google/callback"]

    it = client.post("/api/items", json={"text": "회의 자료 보내기", "plan_date": "2099-05-05"}).json()
    client.patch(f"/api/items/{it['id']}", json={"plan_time": "09:30"})
    assert FakeCalendars.events["ev1"]["summary"] == "회의 자료 보내기"
    assert FakeCalendars.events["ev1"]["start"]["dateTime"].startswith("2099-05-05T09:30:00+09:00")
    client.patch(f"/api/items/{it['id']}", json={"plan_time": "11:00"})              # 같은 일정을 고친다 (새로 만들지 않는다)
    assert list(FakeCalendars.events) == ["ev1"] and "T11:00:00" in FakeCalendars.events["ev1"]["start"]["dateTime"]
    client.patch(f"/api/items/{it['id']}", json={"status": "skipped"})
    assert FakeCalendars.events == {}


def test_google_start_explains_when_not_set_up(monkeypatch):
    monkeypatch.delenv("MALHAN_GOOGLE_CLIENT_ID", raising=False)
    join("준비전")
    assert client.get("/api/calendar").json()["google_ready"] is False
    assert client.get("/api/calendar/google/start", follow_redirects=False).status_code == 503


def test_https_uses_bundled_certificates_and_reports_reason():
    from server import calsync

    ctx = calsync._ssl_context()
    assert ctx.verify_mode.name == "CERT_REQUIRED" and ctx.cert_store_stats()["x509_ca"] > 50   # 인증서 묶음이 실려 있다
    with pytest.raises(calsync.CalendarError) as e:
        calsync._http("GET", "http://127.0.0.1:9/")
    assert "127.0.0.1:9" in str(e.value) and "[" in str(e.value)                                  # 어디에, 왜 못 닿았는지 남긴다


def test_naver_falls_back_to_known_paths_when_discovery_is_refused(fake, monkeypatch):
    from server import calsync

    monkeypatch.setenv("MALHAN_NAVER_CALDAV", fake)
    nav = calsync.Naver("sun", "app-pass")
    real = nav._propfind

    def picky(url, props, depth="0"):
        if url.endswith(":%s/" % fake.rsplit(":", 1)[1]) or "principals" in url:   # 첫 두 단계를 거절하는 서버
            raise calsync.CalendarError("네이버 캘린더가 요청을 받지 않았어요 (응답 405).")
        return real(url, props, depth)

    monkeypatch.setattr(nav, "_propfind", picky)
    assert [c["name"] for c in nav.calendars()] == ["내 캘린더"]


def test_calendar_events_can_be_pulled_in_as_todos(fake, monkeypatch):
    monkeypatch.setenv("MALHAN_NAVER_CALDAV", fake)
    join("일정")
    assert client.get("/api/calendar/events", params={"date": "2099-03-01"}).json() == {"linked": False, "events": []}
    client.post("/api/calendar/naver", json={"user": "sun", "password": "app-pass"})
    r = client.get("/api/calendar/events", params={"date": "2099-03-01"}).json()
    assert r["linked"] and [e["title"] for e in r["events"]] == ["주간 회의, 2층", "창립기념일"]   # 말한대로가 넣은 일정은 뺀다, 시각 있는 것 먼저
    ev = r["events"][0]
    assert ev["time"] == "14:00" and ev["item_id"] is None and ev["ref"].endswith("/ev1.ics")
    it = client.post("/api/calendar/events/import", json={"ref": ev["ref"], "title": ev["title"], "time": ev["time"], "date": "2099-03-01"}).json()
    assert it["status"] == "todo" and it["plan_time"] == "14:00" and it["cal_ref"] == ev["ref"]
    assert client.get("/api/calendar/events", params={"date": "2099-03-01"}).json()["events"][0]["item_id"] == it["id"]
    again = client.post("/api/calendar/events/import", json={"ref": ev["ref"], "title": ev["title"], "date": "2099-03-01"}).json()
    assert again["id"] == it["id"] and again["already"] is True                                 # 두 번 눌러도 하나
    # 가져온 할 일은 캘린더 쪽을 건드리지 않는다: 고쳐도 복사본이 안 생기고, 지워도 일정은 남는다
    FakeCalendars.store.clear()
    client.patch(f"/api/items/{it['id']}", json={"text": "주간 회의 준비"})
    client.delete(f"/api/items/{it['id']}")
    assert FakeCalendars.store == {}


def test_google_events_listing(fake, monkeypatch):
    for k, v in {"MALHAN_GOOGLE_CLIENT_ID": "cid", "MALHAN_GOOGLE_CLIENT_SECRET": "sec",
                 "MALHAN_GOOGLE_TOKEN_URL": fake + "/token", "MALHAN_GOOGLE_API": fake + "/g"}.items():
        monkeypatch.setenv(k, v)
    from server import calsync
    join("구글일정")
    calsync.save_link(client.get("/api/me").json() and 0 or __import__("server.db", fromlist=["x"]).connect().execute("SELECT id FROM users WHERE name='구글일정'").fetchone()["id"],
                      "google", {"refresh_token": "rt-1", "calendar_name": "구글 캘린더"})
    r = client.get("/api/calendar/events", params={"date": "2099-05-05"}).json()
    assert [(e["title"], e["time"]) for e in r["events"]] == [("고객 미팅", "10:00"), ("휴가", None)]   # 취소·말한대로 일정은 뺀다
    # 내가 올린 일정이 근거 문장을 설명으로 달고 돌아와도(표식 없이) cal_ref로 알아보고 뺀다
    from server import db as _db
    with _db.session() as con:
        con.execute("INSERT INTO items(user_id, text, status, plan_date, cal_ref) VALUES ((SELECT id FROM users WHERE name='구글일정'), '고객 미팅 준비', 'todo', '2099-05-05', 'g1')")
    assert [e["title"] for e in client.get("/api/calendar/events", params={"date": "2099-05-05"}).json()["events"]] == ["휴가"]
    # 읽어 올 캘린더를 공유 캘린더로 바꾼다. 올리는 캘린더(primary)는 그대로
    srcs = client.get("/api/calendar/sources").json()["sources"]
    assert [c["name"] for c in srcs] == ["Sun", "팀 공유 일정"] and srcs[0]["primary"] is True
    st = client.post("/api/calendar/source", json={"id": "team@group.calendar.google.com", "name": "팀 공유 일정"}).json()
    assert st["read_source"] == {"id": "team@group.calendar.google.com", "name": "팀 공유 일정"}
    assert [e["title"] for e in client.get("/api/calendar/events", params={"date": "2099-05-05"}).json()["events"]] == ["팀 주간 회의"]
    FakeCalendars.events.clear()
    it = client.post("/api/items", json={"text": "올리는 쪽 확인", "plan_date": "2099-05-06"}).json()
    client.patch(f"/api/items/{it['id']}", json={"plan_time": "09:00"})
    assert "ev1" in FakeCalendars.events                                                   # 쓰기는 여전히 primary로
    assert client.post("/api/calendar/source", json={"id": ""}).json()["read_source"]["id"] == ""
    # 올릴 캘린더를 공유 캘린더로 바꾸면, 앞으로 할 일은 거기로 올라간다
    FakeCalendars.events.clear()
    st = client.post("/api/calendar/target", json={"id": "team@group.calendar.google.com", "name": "팀 공유 일정"}).json()
    assert st["write_target"] == {"id": "team@group.calendar.google.com", "name": "팀 공유 일정"}
    assert any(v["_calendar"] == "team%40group.calendar.google.com" for v in FakeCalendars.events.values())
    # 일정 숨기기 / 다시 보기
    client.post("/api/calendar/source", json={"id": "team@group.calendar.google.com", "name": "팀 공유 일정"})
    client.post("/api/calendar/events/hide", json={"ref": "t1"})
    r = client.get("/api/calendar/events", params={"date": "2099-05-05"}).json()
    assert r["events"] == [] and r["hidden"] == 1
    client.post("/api/calendar/events/unhide", json={})
    assert [e["title"] for e in client.get("/api/calendar/events", params={"date": "2099-05-05"}).json()["events"]] == ["팀 주간 회의"]


def test_relink_and_same_target_do_not_duplicate(fake, monkeypatch):
    for k, v in {"MALHAN_GOOGLE_CLIENT_ID": "cid", "MALHAN_GOOGLE_CLIENT_SECRET": "sec",
                 "MALHAN_GOOGLE_TOKEN_URL": fake + "/token", "MALHAN_GOOGLE_API": fake + "/g"}.items():
        monkeypatch.setenv(k, v)
    from server import calsync, db as _db
    join("중복")
    uid = _db.connect().execute("SELECT id FROM users WHERE name='중복'").fetchone()["id"]
    FakeCalendars.events.clear()
    calsync.save_link(uid, "google", {"refresh_token": "rt-1", "calendar_name": "구글 캘린더"})
    it = client.post("/api/items", json={"text": "치과 가기", "plan_date": "2099-07-01"}).json()
    client.patch(f"/api/items/{it['id']}", json={"plan_time": "10:00"})
    assert len(FakeCalendars.events) == 1
    # 끊었다가 같은 종류로 다시 연결 → 번호가 남아 있어 같은 일정을 고친다 (복사본 없음)
    client.delete("/api/calendar")
    assert client.get("/api/calendar").json()["provider"] == ""
    calsync.save_link(uid, "google", {"refresh_token": "rt-1", "calendar_name": "구글 캘린더"})
    client.patch(f"/api/items/{it['id']}", json={"plan_time": "11:00"})
    assert len(FakeCalendars.events) == 1
    # 올릴 캘린더를 '같은 것'으로 고르면 아무 일도 안 한다
    client.post("/api/calendar/target", json={"id": "primary", "name": "Sun"})
    client.post("/api/calendar/target", json={"id": "primary-id", "name": "Sun"})
    assert len(FakeCalendars.events) == 1
