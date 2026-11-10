"""바깥 캘린더에 자동으로 넣기. 네이버는 CalDAV(아이디 + 애플리케이션 비밀번호), 구글은 OAuth로 연결한다.

원칙
- 할 일 화면이 먼저다. 캘린더 쪽이 실패해도 할 일 저장은 그대로 되고, 사유만 연결 상태에 남긴다.
- 무엇을 보낼지는 사람이 정한다: timed(시각을 정한 일만, 기본) | all(날짜가 정해진 모든 일).

환경 변수
  MALHAN_GOOGLE_CLIENT_ID / MALHAN_GOOGLE_CLIENT_SECRET : 구글 연결에 필요 (INSTALL.md 참고)
  MALHAN_NAVER_CALDAV : 네이버 CalDAV 주소 (기본 https://caldav.calendar.naver.com)
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import db

UTC = ZoneInfo("UTC")
DAV = "{DAV:}"
CAL = "{urn:ietf:params:xml:ns:caldav}"
TIMEOUT = 20


class CalendarError(RuntimeError):
    pass


def tz() -> ZoneInfo:
    return ZoneInfo(os.environ.get("MALHAN_TZ", "Asia/Seoul"))


# ---------- 일정 내용 ----------
def event_times(row, time_: str | None = None, today: date | None = None):
    """항목의 날짜(하기로 한 날 → 기한 → 오늘)와 시각으로 (날짜, 시작, 끝). 시각이 없으면 하루 종일."""
    d = date.fromisoformat(row["plan_date"] or row["due_date"] or (today or datetime.now(tz()).date()).isoformat())
    time_ = time_ or row["plan_time"]
    if not time_:
        return d, None, None
    hh, mm = (int(x) for x in time_.split(":"))  # 형식이 틀리면 ValueError
    start = datetime(d.year, d.month, d.day, hh, mm, tzinfo=tz())
    return d, start, start + timedelta(minutes=30)


def ics_text(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def build_ics(row, uid: str, time_: str | None = None) -> str:
    d, start, end = event_times(row, time_)
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//malhandaero//KO", "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{datetime.now(UTC):%Y%m%dT%H%M%SZ}",
    ]
    if start:
        lines += [f"DTSTART:{start.astimezone(UTC):%Y%m%dT%H%M%SZ}", f"DTEND:{end.astimezone(UTC):%Y%m%dT%H%M%SZ}"]
        trigger = "-PT10M"  # 10분 전
    else:
        lines += [f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}"]
        trigger = "PT9H"    # 그날 오전 9시
    lines += [f"SUMMARY:{ics_text(row['text'])}"]
    if row["quote"]:
        lines += [f"DESCRIPTION:{ics_text(row['quote'])}"]
    lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{ics_text(row['text'])}", f"TRIGGER:{trigger}", "END:VALARM",
              "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


# ---------- 공통 HTTP ----------
def _ssl_context():
    """인증서 묶음을 직접 지정한다. Mac에 python.org 판을 깔면 기본 인증서가 없어 https가 모두 실패하기 때문이다."""
    import ssl

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _http(method: str, url: str, headers: dict | None = None, body: bytes | None = None) -> tuple[int, bytes]:
    import ssl

    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_context() if url.startswith("https") else None) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        with e:  # 응답을 닫는다
            return e.code, e.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        reason = getattr(e, "reason", e)
        if isinstance(reason, ssl.SSLError) or "CERTIFICATE" in str(reason).upper():
            raise CalendarError("캘린더 서버의 보안 인증서를 확인하지 못했어요. 설치를 다시 실행한 뒤 서버를 껐다 켜 주세요.")
        host = urllib.parse.urlparse(url).netloc
        raise CalendarError(f"캘린더 서버({host})에 닿지 못했어요. 인터넷 연결을 확인해 주세요. [{type(reason).__name__}: {str(reason)[:80]}]")


def _ics_unescape(v: str) -> str:
    return v.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def parse_vevent(ics: str, day: date) -> dict | None:
    """VEVENT 하나에서 제목·시각·설명을 꺼낸다. 접힌 줄(앞에 공백)을 펴고, 그날 것만 돌려준다."""
    lines: list[str] = []
    for raw in ics.replace("\r\n", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    props: dict = {}
    in_event = False
    for line in lines:
        if line == "BEGIN:VEVENT":
            in_event = True
            continue
        if line == "END:VEVENT":
            break
        if in_event and ":" in line:
            key, val = line.split(":", 1)
            props[key.split(";")[0].upper()] = (key, val)
    if "SUMMARY" not in props:
        return None
    start_key, start = props.get("DTSTART", ("", ""))
    time_: str | None = None
    if start:
        if "VALUE=DATE" in start_key.upper() or len(start) == 8:
            if start[:8] != f"{day:%Y%m%d}":
                return None
        else:
            try:
                dt = datetime.strptime(start[:15], "%Y%m%dT%H%M%S")
                if start.endswith("Z"):
                    dt = dt.replace(tzinfo=UTC).astimezone(tz())
                elif "TZID" in start_key.upper():
                    dt = dt.replace(tzinfo=tz())  # 한국 안에서 쓰는 전제. 다른 시간대 표기는 그대로 본다
                else:
                    dt = dt.replace(tzinfo=tz())
                if dt.date() != day:
                    return None
                time_ = f"{dt:%H:%M}"
            except ValueError:
                pass
    return {"title": _ics_unescape(props["SUMMARY"][1]).strip()[:200], "time": time_,
            "description": _ics_unescape(props.get("DESCRIPTION", ("", ""))[1]).strip()[:300], "uid": props.get("UID", ("", ""))[1]}


# ---------- 네이버 (CalDAV) ----------
class Naver:
    def __init__(self, user: str, password: str):
        self.base = os.environ.get("MALHAN_NAVER_CALDAV", "https://caldav.calendar.naver.com").rstrip("/")
        self.user = user
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        self.auth = {"Authorization": "Basic " + token}

    def _abs(self, href: str) -> str:
        return urllib.parse.urljoin(self.base + "/", href)

    def _propfind(self, url: str, props: str, depth: str = "0") -> ET.Element:
        body = f'<?xml version="1.0" encoding="utf-8"?><d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:prop>{props}</d:prop></d:propfind>'
        code, data = _http("PROPFIND", url, {**self.auth, "Depth": depth, "Content-Type": "application/xml; charset=utf-8"}, body.encode())
        if code in (401, 403):
            raise CalendarError("네이버 아이디나 애플리케이션 비밀번호가 맞지 않아요. 로그인 비밀번호가 아니라 '애플리케이션 비밀번호'를 넣어야 해요.")
        if code != 207:
            raise CalendarError(f"네이버 캘린더가 요청을 받지 않았어요 (응답 {code}).")
        try:
            return ET.fromstring(data)
        except ET.ParseError:
            raise CalendarError("네이버 캘린더의 응답을 읽지 못했어요.")

    def calendars(self) -> list[dict]:
        """내 캘린더 목록. 일정(VEVENT)을 넣을 수 있는 것만."""
        known_principal = f"/principals/users/{self.user}/"
        known_home = f"/caldav/{self.user}/calendar/"
        try:
            root = self._propfind(self.base + "/", "<d:current-user-principal/>")
            href = root.find(f".//{DAV}current-user-principal/{DAV}href")
            principal = self._abs(href.text if href is not None and href.text else known_principal)
        except CalendarError as e:
            if "비밀번호" in str(e) or "닿지" in str(e) or "인증서" in str(e):
                raise  # 로그인·연결 문제는 다른 주소로 가도 같다
            principal = self._abs(known_principal)
        try:
            root = self._propfind(principal, "<c:calendar-home-set/>")
            href = root.find(f".//{CAL}calendar-home-set/{DAV}href")
            home = self._abs(href.text) if href is not None and href.text else self._abs(known_home)
        except CalendarError as e:
            if "비밀번호" in str(e) or "닿지" in str(e) or "인증서" in str(e):
                raise
            home = self._abs(known_home)
        root = self._propfind(home, "<d:resourcetype/><d:displayname/><c:supported-calendar-component-set/>", depth="1")
        out = []
        for resp in root.findall(f"{DAV}response"):
            if resp.find(f".//{DAV}resourcetype/{CAL}calendar") is None:
                continue
            comps = [c.get("name") for c in resp.findall(f".//{CAL}supported-calendar-component-set/{CAL}comp")]
            if comps and "VEVENT" not in comps:
                continue  # 할 일 전용 등
            h = resp.find(f"{DAV}href")
            name = resp.find(f".//{DAV}displayname")
            url = self._abs(h.text) if h is not None and h.text else ""
            if url:
                out.append({"url": url if url.endswith("/") else url + "/", "name": (name.text or "").strip() if name is not None else ""})
        if not out:
            raise CalendarError("일정을 넣을 수 있는 네이버 캘린더를 찾지 못했어요.")
        return out

    def events(self, calendar_url: str, day: date) -> list[dict]:
        """그날의 일정. CalDAV calendar-query(REPORT)로 받아 VEVENT를 읽는다."""
        start = datetime(day.year, day.month, day.day, tzinfo=tz()).astimezone(UTC)
        end = start + timedelta(days=1)
        body = ('<?xml version="1.0" encoding="utf-8"?><c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
                '<d:prop><d:getetag/><c:calendar-data/></d:prop><c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VEVENT">'
                f'<c:time-range start="{start:%Y%m%dT%H%M%SZ}" end="{end:%Y%m%dT%H%M%SZ}"/></c:comp-filter></c:comp-filter></c:filter></c:calendar-query>')
        code, data = _http("REPORT", calendar_url, {**self.auth, "Depth": "1", "Content-Type": "application/xml; charset=utf-8"}, body.encode())
        if code in (401, 403):
            raise CalendarError("네이버 아이디나 애플리케이션 비밀번호가 맞지 않아요.")
        if code != 207:
            raise CalendarError(f"네이버 캘린더에서 일정을 읽지 못했어요 (응답 {code}).")
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            raise CalendarError("네이버 캘린더의 응답을 읽지 못했어요.")
        out = []
        for resp in root.findall(f"{DAV}response"):
            h, cd = resp.find(f"{DAV}href"), resp.find(f".//{CAL}calendar-data")
            if h is None or cd is None or not cd.text:
                continue
            ev = parse_vevent(cd.text, day)
            if ev:
                ev["ref"] = self._abs(h.text)
                out.append(ev)
        return sorted(out, key=lambda e: (e["time"] is None, e["time"] or ""))

    def put(self, calendar_url: str, uid: str, ics: str) -> str:
        url = calendar_url + urllib.parse.quote(uid) + ".ics"
        code, _ = _http("PUT", url, {**self.auth, "Content-Type": "text/calendar; charset=utf-8"}, ics.encode())
        if code not in (200, 201, 204):
            raise CalendarError(f"네이버 캘린더에 넣지 못했어요 (응답 {code}).")
        return url

    def delete(self, url: str) -> None:
        code, _ = _http("DELETE", url, self.auth)
        if code not in (200, 204, 404):
            raise CalendarError(f"네이버 캘린더에서 지우지 못했어요 (응답 {code}).")


# ---------- 구글 (OAuth + Calendar API) ----------
GOOGLE_SCOPE = "https://www.googleapis.com/auth/calendar.events"


def google_client() -> tuple[str, str] | None:
    cid, sec = os.environ.get("MALHAN_GOOGLE_CLIENT_ID"), os.environ.get("MALHAN_GOOGLE_CLIENT_SECRET")
    return (cid, sec) if cid and sec else None


def _g(name: str, default: str) -> str:
    return os.environ.get(name, default).rstrip("/")


def google_auth_url(redirect_uri: str, state: str) -> str:
    cid, _ = google_client() or ("", "")
    return _g("MALHAN_GOOGLE_AUTH_URL", "https://accounts.google.com/o/oauth2/v2/auth") + "?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": redirect_uri, "response_type": "code", "scope": GOOGLE_SCOPE,
        "access_type": "offline", "prompt": "consent", "state": state,
    })


def _google_token(params: dict) -> dict:
    cid, sec = google_client() or ("", "")
    body = urllib.parse.urlencode({**params, "client_id": cid, "client_secret": sec}).encode()
    code, data = _http("POST", _g("MALHAN_GOOGLE_TOKEN_URL", "https://oauth2.googleapis.com/token"),
                       {"Content-Type": "application/x-www-form-urlencoded"}, body)
    try:
        out = json.loads(data)
    except ValueError:
        out = {}
    if code != 200 or "access_token" not in out:
        if out.get("error") == "invalid_grant":
            raise CalendarError("구글 연결이 만료됐어요. 캘린더 연결에서 구글을 다시 연결해 주세요.")
        raise CalendarError("구글 로그인을 마치지 못했어요. 다시 연결해 주세요.")
    return out


def google_exchange(code_: str, redirect_uri: str) -> str:
    out = _google_token({"code": code_, "redirect_uri": redirect_uri, "grant_type": "authorization_code"})
    if not out.get("refresh_token"):
        raise CalendarError("구글이 계속 쓸 수 있는 연결을 주지 않았어요. 구글 계정의 '서드 파티 앱'에서 말한대로를 지운 뒤 다시 연결해 주세요.")
    return out["refresh_token"]


class Google:
    def __init__(self, refresh_token: str):
        self.api = _g("MALHAN_GOOGLE_API", "https://www.googleapis.com/calendar/v3")
        token = _google_token({"refresh_token": refresh_token, "grant_type": "refresh_token"})["access_token"]
        self.h = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}

    @staticmethod
    def body(row) -> dict:
        d, start, end = event_times(row)
        b: dict = {"summary": row["text"], "description": row["quote"] or "말한대로에서 보냄"}
        if start:
            b["start"] = {"dateTime": start.isoformat()}
            b["end"] = {"dateTime": end.isoformat()}
            b["reminders"] = {"useDefault": False, "overrides": [{"method": "popup", "minutes": 10}]}
        else:
            b["start"] = {"date": d.isoformat()}
            b["end"] = {"date": (d + timedelta(days=1)).isoformat()}
        return b

    def events(self, day: date) -> list[dict]:
        """그날의 일정 (기본 캘린더)."""
        start = datetime(day.year, day.month, day.day, tzinfo=tz())
        q = urllib.parse.urlencode({"timeMin": start.isoformat(), "timeMax": (start + timedelta(days=1)).isoformat(),
                                    "singleEvents": "true", "orderBy": "startTime", "maxResults": "50"})
        code, out = _http("GET", f"{self.api}/calendars/primary/events?{q}", self.h)
        if code != 200:
            raise CalendarError(f"구글 캘린더에서 일정을 읽지 못했어요 (응답 {code}).")
        res = []
        for e in json.loads(out).get("items", []):
            if e.get("status") == "cancelled" or not e.get("summary"):
                continue
            st = e.get("start", {})
            time_ = None
            if st.get("dateTime"):
                try:
                    time_ = f"{datetime.fromisoformat(st['dateTime'].replace('Z', '+00:00')).astimezone(tz()):%H:%M}"
                except ValueError:
                    pass
            res.append({"ref": e["id"], "title": e["summary"][:200], "time": time_, "description": (e.get("description") or "")[:300], "uid": e.get("iCalUID", "")})
        return res

    def upsert(self, row, ref: str | None) -> str:
        data = json.dumps(self.body(row)).encode()
        if ref:
            code, out = _http("PATCH", f"{self.api}/calendars/primary/events/{urllib.parse.quote(ref)}", self.h, data)
            if code == 200:
                return ref
            if code not in (404, 410):
                raise CalendarError(f"구글 캘린더의 일정을 고치지 못했어요 (응답 {code}).")
        code, out = _http("POST", f"{self.api}/calendars/primary/events", self.h, data)
        if code not in (200, 201):
            raise CalendarError(f"구글 캘린더에 넣지 못했어요 (응답 {code}).")
        return json.loads(out)["id"]

    def delete(self, ref: str) -> None:
        code, _ = _http("DELETE", f"{self.api}/calendars/primary/events/{urllib.parse.quote(ref)}", self.h)
        if code not in (200, 204, 404, 410):
            raise CalendarError(f"구글 캘린더에서 지우지 못했어요 (응답 {code}).")


# ---------- 연결 정보 ----------
def get_link(user_id: int) -> dict | None:
    with db.session() as con:
        r = con.execute("SELECT * FROM calendar_links WHERE user_id = ?", (user_id,)).fetchone()
    if not r or not r["provider"]:
        return None
    d = dict(r)
    d["config"] = json.loads(d["config"] or "{}")
    return d


def save_link(user_id: int, provider: str, config: dict, mode: str = "timed") -> None:
    with db.session() as con:
        con.execute(
            "INSERT INTO calendar_links(user_id, provider, mode, config, status) VALUES (?,?,?,?, '')"
            " ON CONFLICT(user_id) DO UPDATE SET provider = excluded.provider, config = excluded.config, status = '', updated_at = datetime('now')",
            (user_id, provider, mode, json.dumps(config, ensure_ascii=False)),
        )


def _note(user_id: int, text: str) -> None:
    with db.session() as con:
        con.execute("UPDATE calendar_links SET status = ?, updated_at = datetime('now') WHERE user_id = ?", (text, user_id))


def wants(link: dict, row) -> bool:
    """이 항목을 캘린더에 둘지: 하기로 했고 날짜가 있으며, 설정이 '시각 있는 일만'이면 시각까지 있어야 한다."""
    return bool(row["status"] in ("todo", "done") and row["plan_date"] and (link["mode"] == "all" or row["plan_time"]))


OURS = "말한대로에서 보냄"


def day_events(link: dict, day: date) -> list[dict]:
    """연결된 캘린더의 그날 일정. 말한대로가 넣은 일정은 뺀다."""
    if link["provider"] == "naver":
        cfg = link["config"]
        evs = Naver(cfg["user"], cfg["password"]).events(cfg["calendar_url"], day)
    else:
        evs = Google(link["config"]["refresh_token"]).events(day)
    return [e for e in evs if OURS not in (e.get("description") or "") and not (e.get("uid") or "").endswith("@malhandaero")]


def _remove(link: dict, ref: str) -> None:
    if link["provider"] == "naver":
        Naver(link["config"]["user"], link["config"]["password"]).delete(ref)
    else:
        Google(link["config"]["refresh_token"]).delete(ref)


def sync_item(user_id: int, item_id: int, removed_ref: str | None = None) -> None:
    """항목 하나를 캘린더와 맞춘다. 뒤에서 도는 작업이라 실패해도 사유만 남긴다."""
    link = get_link(user_id)
    if not link:
        return
    try:
        if removed_ref:  # 항목이 이미 지워진 경우
            _remove(link, removed_ref)
            return
        with db.session() as con:
            row = con.execute("SELECT * FROM items WHERE id = ? AND user_id = ?", (item_id, user_id)).fetchone()
        if not row:
            return
        if row["addon"] == "calendar":  # 캘린더에서 가져온 할 일: 원본은 캘린더라 건드리지 않는다
            return
        ref = row["cal_ref"]
        if wants(link, row):
            if link["provider"] == "naver":
                cfg = link["config"]
                ref = Naver(cfg["user"], cfg["password"]).put(cfg["calendar_url"], f"malhandaero-{item_id}", build_ics(row, f"malhandaero-{item_id}@malhandaero"))
            else:
                ref = Google(link["config"]["refresh_token"]).upsert(row, ref)
        elif ref:
            _remove(link, ref)
            ref = None
        if ref != row["cal_ref"]:
            with db.session() as con:
                con.execute("UPDATE items SET cal_ref = ? WHERE id = ?", (ref, item_id))
        if link["status"]:
            _note(user_id, "")
    except CalendarError as e:
        _note(user_id, str(e))
    except Exception as e:  # 캘린더 문제로 할 일 화면이 멈추면 안 된다
        _note(user_id, f"캘린더에 맞추지 못했어요: {type(e).__name__}")
