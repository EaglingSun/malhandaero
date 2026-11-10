"""말한대로 서버. 실행: uvicorn server.app:app --host 0.0.0.0 --port 8000"""
from __future__ import annotations

import json
import os
import secrets
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, Cookie, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import calsync, db, extract, llm, stt, transcript, updater

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
TZ = ZoneInfo(os.environ.get("MALHAN_TZ", "Asia/Seoul"))
COOKIE = "mh_token"
AUDIO_EXT = {".m4a", ".mp3", ".wav", ".webm", ".ogg", ".aac", ".amr", ".3gp", ".mp4", ".flac"}
MAX_TEXT = 400_000
MAX_AUDIO = 200 * 1024 * 1024
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif"}
MAX_IMAGE = 25 * 1024 * 1024
KINDS = {"call", "meeting", "memo", "file", "photo"}
STATUSES = {"new", "todo", "later", "skipped", "done", "other"}

app = FastAPI(title="말한대로")
db.init()


# ---------- 공통 ----------
def today() -> date:
    return datetime.now(TZ).date()


def parse_date(s: str | None) -> date:
    if not s:
        return today()
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise HTTPException(400, "날짜는 YYYY-MM-DD 꼴이어야 해요.")


def family_code() -> str:
    return os.environ.get("MALHAN_FAMILY_CODE", "")


def set_env_value(key: str, value: str) -> None:
    """.env의 한 줄을 바꾸거나 더한다(다른 줄은 그대로). 지금 켜진 서버에도 바로 반영."""
    env = ROOT / ".env"
    lines = env.read_text(encoding="utf-8-sig").splitlines() if env.exists() else []
    out, done = [], False
    for line in lines:
        if line.split("=", 1)[0].strip() == key and not line.lstrip().startswith("#"):
            if not done:
                out.append(f"{key}={value}")
                done = True
        else:
            out.append(line)
    if not done:
        out.insert(0, f"{key}={value}")
    env.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.environ[key] = value


def current_user(mh_token: str | None = Cookie(default=None)):
    if not mh_token:
        raise HTTPException(401, "먼저 들어와 주세요.")
    with db.session() as con:
        row = con.execute("SELECT id, name FROM users WHERE token = ?", (mh_token,)).fetchone()
    if not row:
        raise HTTPException(401, "먼저 들어와 주세요.")
    return row


def _json_list(v) -> list:
    try:
        x = json.loads(v or "[]")
        return x if isinstance(x, list) else []
    except ValueError:
        return []


def item_dict(r, t: date | None = None) -> dict:
    d = dict(r)
    d["details"] = _json_list(d.get("details"))
    d["carried_days"] = 0
    if t and d["status"] == "todo" and d["plan_date"] and d["plan_date"] < t.isoformat():
        d["carried_days"] = (t - date.fromisoformat(d["plan_date"])).days
    return d


def input_dict(r, with_text: bool = False) -> dict:
    d = dict(r)
    d["speakers"] = json.loads(d.get("speakers") or "[]")
    try:
        d["minutes"] = json.loads(d.get("minutes") or "") or {"topics": [], "questions": []}
    except ValueError:
        d["minutes"] = {"topics": [], "questions": []}
    d["has_minutes"] = bool(d["minutes"].get("topics") or d["minutes"].get("questions"))
    d.pop("media_path", None)
    d.pop("user_id", None)
    if not with_text:
        d["chars"] = len(d.pop("transcript", "") or "")
    return d


# ---------- 들어오기 ----------
class JoinBody(BaseModel):
    name: str
    code: str = ""
    invite: str = ""   # QR로 받은 초대. 있으면 가족 코드 대신 쓴다


# ---------- QR로 연결 ----------
LINK_MINUTES = 10
_links: dict[str, dict] = {}   # 토큰 → {kind, user_id, until}. 서버를 끄면 사라진다


def _link_get(token: str) -> dict | None:
    now = datetime.now(TZ)
    for k in [k for k, v in _links.items() if v["until"] < now]:
        _links.pop(k, None)
    return _links.get(token)


def public_base(request: Request) -> str:
    """휴대폰이 열 주소. 집 밖 주소(https)가 있으면 그것, 없으면 지금 열어 본 주소."""
    fixed = os.environ.get("MALHAN_PUBLIC_URL", "").rstrip("/")
    if fixed:
        return fixed
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    if host.split(":")[0] in ("localhost", "127.0.0.1"):  # 폰에서는 localhost가 PC가 아니다
        lan = os.environ.get("MALHAN_LAN_URL", "").rstrip("/")
        if lan:
            return lan
    return f"{proto}://{host}"


class LinkBody(BaseModel):
    kind: str = "me"   # me(내 다른 기기) | family(가족 초대)


@app.post("/api/link")
def make_link(body: LinkBody, request: Request, user=Depends(current_user)):
    import segno

    kind = body.kind if body.kind in ("me", "family") else "me"
    token = secrets.token_urlsafe(12)
    _links[token] = {"kind": kind, "user_id": user["id"], "until": datetime.now(TZ) + timedelta(minutes=LINK_MINUTES)}
    url = f"{public_base(request)}/l/{token}"
    return {"url": url, "kind": kind, "minutes": LINK_MINUTES, "secure": url.startswith("https://"),
            "svg": segno.make(url, error="m").svg_inline(scale=6, border=2, dark="#223244")}


@app.get("/l/{token}")
def open_link(token: str):
    link = _link_get(token)
    if not link:
        return RedirectResponse("/?link=expired", status_code=303)
    if link["kind"] == "family":
        return RedirectResponse(f"/?invite={token}", status_code=303)   # 이름만 정하면 된다. 시간 안에는 여러 명이 쓸 수 있다
    _links.pop(token, None)                                             # 내 기기 연결은 한 번만
    with db.session() as con:
        row = con.execute("SELECT token FROM users WHERE id = ?", (link["user_id"],)).fetchone()
    if not row:
        return RedirectResponse("/?link=expired", status_code=303)
    res = RedirectResponse("/?link=ok", status_code=303)
    res.set_cookie(COOKIE, row["token"], max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax")
    return res


@app.post("/api/join")
def join(body: JoinBody):
    name = body.name.strip()[:20]
    if not name:
        raise HTTPException(400, "이름을 적어 주세요.")
    invited = bool(body.invite) and (_link_get(body.invite) or {}).get("kind") == "family"
    if body.invite and not invited:
        raise HTTPException(403, "초대 시간이 지났어요. QR을 다시 받아 주세요.")
    code = family_code()
    if not invited:
        if not code:
            raise HTTPException(503, "서버에 가족 코드가 설정되지 않았어요. .env의 MALHAN_FAMILY_CODE를 정해 주세요.")
        if not secrets.compare_digest(body.code.strip().encode(), code.encode()):
            raise HTTPException(403, "가족 코드가 맞지 않아요.")
    with db.session() as con:
        row = con.execute("SELECT id, name, token FROM users WHERE name = ?", (name,)).fetchone()
        if row:
            token = row["token"]
        else:
            token = secrets.token_urlsafe(32)
            con.execute("INSERT INTO users(name, token) VALUES (?, ?)", (name, token))
    res = JSONResponse({"name": name})
    res.set_cookie(COOKIE, token, max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax")
    return res


@app.post("/api/leave")
def leave():
    res = JSONResponse({"ok": True})
    res.delete_cookie(COOKIE)
    return res


@app.get("/api/me")
def me(user=Depends(current_user)):
    return {
        "name": user["name"],
        "today": today().isoformat(),
        "ai": llm.mode(),
        "stt": stt.available(),
        "version": _version(),
        "label": app_label(),
        "update": dict(UPDATE_AVAILABLE) if UPDATE_AVAILABLE else None,
        "diary": _diary_on(user["id"]),
        "post_url": os.environ.get("MALHAN_POST_URL", "").strip(),
    }


def _diary_on(user_id: int) -> bool:
    with db.session() as con:
        r = con.execute("SELECT enabled FROM addon_settings WHERE user_id = ? AND addon = 'diary'", (user_id,)).fetchone()
    return bool(r and r["enabled"])


class CodeChange(BaseModel):
    code: str


@app.post("/api/settings/code")
def change_code(body: CodeChange, user=Depends(current_user)):
    """들어올 때 쓰는 코드를 바꾼다. 이미 들어와 있는 폰은 그대로, 새로 들어오는 기기부터 새 코드."""
    code = body.code.strip()
    if not (2 <= len(code) <= 32):
        raise HTTPException(400, "코드는 2~32자로 정해 주세요.")
    set_env_value("MALHAN_FAMILY_CODE", code)
    return {"ok": True}


class DiaryToggle(BaseModel):
    enabled: bool


@app.post("/api/settings/diary")
def diary_toggle(body: DiaryToggle, user=Depends(current_user)):
    """'오늘 한 줄'을 쓸지. 기본은 꺼짐, 쓰고 싶은 사람만 켠다."""
    with db.session() as con:
        con.execute("INSERT INTO addon_settings(user_id, addon, enabled) VALUES (?, 'diary', ?) ON CONFLICT(user_id, addon) DO UPDATE SET enabled = excluded.enabled",
                    (user["id"], 1 if body.enabled else 0))
    return {"diary": body.enabled}


class DayNote(BaseModel):
    note: str = ""
    mood: str = ""


@app.post("/api/day/note")
def day_note(body: DayNote, date_: str | None = Query(None, alias="date"), user=Depends(current_user)):
    """그날의 기분 이모지와 한 줄을 저장한다. 마무리 글이 없으면 빈 마무리로 자리를 만든다."""
    ds = parse_date(date_).isoformat()
    note = body.note.strip()[:200]
    mood = body.mood.strip()[:8]
    with db.session() as con:
        con.execute(
            "INSERT INTO day_logs(user_id, date, summary, note, mood) VALUES (?,?,'',?,?) "
            "ON CONFLICT(user_id, date) DO UPDATE SET note = excluded.note, mood = excluded.mood",
            (user["id"], ds, note, mood),
        )
    return {"date": ds, "note": note, "mood": mood}


# ---------- 업데이트 ----------
def _version() -> str:
    try:
        return updater.git("rev-parse", "--short", "HEAD")
    except Exception:
        return ""


_update_lock = __import__("threading").Lock()


def _update_now() -> dict:
    """업데이트를 받아 온다. 받았으면 잠시 뒤 서버를 끝내고 run.py가 새 버전으로 다시 켠다."""
    if not _update_lock.acquire(blocking=False):
        return {"busy": True, "messages": ["이미 확인하는 중이에요."]}
    try:
        updater.main([])
        out = dict(updater.RESULT)
        # 받은 게 없어도 이 PC에서 직접 고친 코드가 있으면 그 코드로 다시 켠다 (Claude Code로 고친 뒤 폰에서 「업데이트」만 누르면 되게)
        if out.get("local") and not out["updated"]:
            out["messages"].append("직접 고친 코드로 다시 켤게요.")
        out["restarting"] = out["updated"] or bool(out.get("local"))
        if out["restarting"]:
            n = pending_count()
            out["waiting"] = n
            if n:
                out["messages"].append(f"처리 중인 녹음 {n}건이 끝나면 새 버전으로 다시 켤게요.")
                _restart_when_idle()
            else:
                updater.restart_soon()
        return out
    finally:
        _update_lock.release()


def _restart_when_idle(poll: float = 5.0) -> None:
    """처리 중인 입력이 모두 끝난 뒤에 다시 켠다 (Claude Code 호출 도중에 끊기지 않게)."""
    import threading
    import time

    def wait():
        while pending_count():
            time.sleep(poll)
        updater.restart_soon(0.5)

    threading.Thread(target=wait, daemon=True).start()


@app.post("/api/update")
def update_now(user=Depends(current_user)):
    """화면의 '업데이트'. 업데이트가 있으면 받아서 다시 켠다. 자료(data/)와 설정(.env)은 그대로다."""
    return _update_now()


UPDATE_AVAILABLE: dict = {}  # {"after": "abc1234", "log": [...]} 새 버전이 있을 때. 화면 위 띠로 알린다


def _check_remote() -> None:
    """받지는 않고 새 버전이 있는지만 본다 (git fetch). 있으면 UPDATE_AVAILABLE에 적어 화면이 띠를 보여 준다."""
    try:
        branch = updater.git("rev-parse", "--abbrev-ref", "HEAD")
        updater.git("fetch", "--quiet", "origin", branch)
        here, there = updater.git("rev-parse", "HEAD"), updater.git("rev-parse", f"origin/{branch}")
        if here != there and updater.git("merge-base", "--is-ancestor", here, there) == "":
            log = updater.git("log", "--oneline", "--no-decorate", f"{here}..{there}").splitlines()
            UPDATE_AVAILABLE.update(after=there[:7], log=[(l.split(" ", 1)[1] if " " in l else l) for l in log][:8])
        else:
            UPDATE_AVAILABLE.clear()
    except Exception:
        pass


def _nightly_update() -> None:
    """한 시간마다 새 버전이 있는지 보고(화면에 띠), 새벽 4시쯤 하루 한 번 저절로 받아 다시 켠다.
    MALHAN_AUTO_UPDATE=now 이면 새 버전을 보는 즉시 — 단 처리 중인 녹음이 없을 때 — 받아 다시 켠다."""
    import time

    last, tick = "", 0
    while True:
        time.sleep(600)
        tick += 1
        if os.environ.get("MALHAN_AUTO_UPDATE") == "0":
            continue
        now = datetime.now(TZ)
        nightly = now.hour == 4 and last != now.date().isoformat()
        if tick % 6 == 0 or nightly:
            _check_remote()
        if nightly or (UPDATE_AVAILABLE and os.environ.get("MALHAN_AUTO_UPDATE", "1").lower() == "now" and not pending_count()):
            if nightly:
                last = now.date().isoformat()
            if UPDATE_AVAILABLE or nightly:
                try:
                    _update_now()
                except Exception:
                    pass


if os.environ.get("MALHAN_NIGHTLY_UPDATE", "1") == "1" and not os.environ.get("PYTEST_CURRENT_TEST"):
    __import__("threading").Thread(target=_nightly_update, daemon=True).start()


# ---------- 입력 처리(받기 → 글 → 추출) ----------
def process_input(input_id: int) -> None:
    """뒤에서 도는 작업. 실패하면 사유를 입력에 남긴다."""
    with db.session() as con:
        row = con.execute("SELECT * FROM inputs WHERE id = ?", (input_id,)).fetchone()
    if not row:
        return
    try:
        text = row["transcript"]
        from_audio = bool(row["media_path"]) and row["kind"] != "photo" and not text
        if row["media_path"] and not text:
            _set_input(input_id, status="transcribing")
            media = Path(row["media_path"])
            text = llm.read_image(media) if row["kind"] == "photo" else stt.transcribe(media)
            media.unlink(missing_ok=True)  # 음성·사진은 글로 바꾼 뒤 지운다
            _set_input(input_id, transcript=text, media_path=None)
        names = transcript.speakers(text)
        me_spk = row["me_speaker"] or transcript.guess_me(names)
        _set_input(input_id, speakers=json.dumps(names, ensure_ascii=False), me_speaker=me_spk, status="extracting")
        if not text.strip():
            _set_input(input_id, status="extracted")
            return
        with db.session() as con:
            known = [r["text"] for r in con.execute(
                "SELECT text FROM items WHERE user_id = ? AND status IN ('new','todo','later') AND (input_id IS NULL OR input_id != ?)",
                (row["user_id"], input_id))]
            skipped = [r["text"] for r in con.execute(
                "SELECT text FROM items WHERE user_id = ? AND status = 'skipped' ORDER BY updated_at DESC LIMIT 10",
                (row["user_id"],))]
        ctx = extract.Context(
            today=date.fromisoformat(row["received_date"]),
            kind=row["kind"], me_speaker=me_spk, skipped=skipped, known=known,
            from_audio=from_audio or (not names and (row["source_name"] or "").lower().endswith(tuple(AUDIO_EXT))),
        )
        summary, cands, minutes = extract.extract(text, ctx)
        with db.session() as con:
            # 다시 뽑을 때: 이 입력에서 나왔고 아직 고르지 않은 것(새로 적어 둔 것, 남의 일)만 갈아 끼운다
            con.execute("DELETE FROM items WHERE input_id = ? AND status IN ('new','other')", (input_id,))
            kept = [r["text"] for r in con.execute("SELECT text FROM items WHERE input_id = ?", (input_id,))]
            for c in extract.dedupe(cands, kept):
                con.execute(
                    "INSERT INTO items(user_id, input_id, text, quote, due_text, due_date, plan_time, scope, owner, who, status, details)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (row["user_id"], input_id, c.text, c.quote, c.due_text, c.due_date, c.time, c.scope, c.owner, c.who,
                     "other" if c.owner == "other" else "new", json.dumps(c.details, ensure_ascii=False)),
                )
        _set_input(input_id, status="extracted", error="", summary=summary,
                   minutes=json.dumps(minutes, ensure_ascii=False) if (minutes.get("topics") or minutes.get("questions")) else "")
    except (llm.LlmUnavailable, stt.SttUnavailable) as e:
        _set_input(input_id, status="failed", error=str(e))
    except Exception as e:  # 뒤에서 도는 작업이라 사유를 남기고 끝낸다
        _set_input(input_id, status="failed", error=f"처리하지 못했어요: {type(e).__name__}")


PENDING = ("received", "transcribing", "ready", "extracting")


def pending_count(user_id: int | None = None) -> int:
    q = "SELECT COUNT(*) AS n FROM inputs WHERE status IN ('received','transcribing','ready','extracting')"
    with db.session() as con:
        if user_id is None:
            return con.execute(q).fetchone()["n"]
        return con.execute(q + " AND user_id = ?", (user_id,)).fetchone()["n"]


def resume_pending() -> int:
    """서버가 (업데이트 등으로) 꺼졌다 켜질 때, 처리 중이던 입력을 처음부터 다시 돌린다. 안 그러면 '찾는 중'에 영영 멈춘다."""
    with db.session() as con:
        ids = [r["id"] for r in con.execute("SELECT id FROM inputs WHERE status IN ('received','transcribing','ready','extracting') ORDER BY id")]
    for i in ids:
        _set_input(i, status="received")
        process_input(i)
    return len(ids)


@app.on_event("startup")
def _resume_on_startup() -> None:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    __import__("threading").Thread(target=resume_pending, daemon=True).start()


def _set_input(input_id: int, **fields) -> None:
    if fields.get("status") in ("extracted", "failed"):
        fields["done_at"] = datetime.now(calsync.UTC).strftime("%Y-%m-%d %H:%M:%S")
    cols = ", ".join(f"{k} = ?" for k in fields)
    with db.session() as con:
        con.execute(f"UPDATE inputs SET {cols} WHERE id = ?", (*fields.values(), input_id))


async def _store_input(user_id: int, kind: str, title: str, text: str, file: UploadFile | None, on: date) -> int:
    kind = kind if kind in KINDS else "file"
    media_path = None
    source = ""
    if file is not None and file.filename:
        source = Path(file.filename).name[:120]
        ext = Path(source).suffix.lower()
        ctype = file.content_type or ""
        is_image = ext in IMAGE_EXT or ctype.startswith("image/")
        is_audio = not is_image and (ext in AUDIO_EXT or ctype.startswith(("audio/", "video/")))
        if is_image or is_audio:
            if is_image:
                kind = "photo"
            limit = MAX_IMAGE if is_image else MAX_AUDIO
            keep = ext if ext in (IMAGE_EXT | AUDIO_EXT) else (".jpg" if is_image else ".bin")
            dest = db.data_dir() / "audio" / f"{uuid.uuid4().hex}{keep}"
            size = 0
            with dest.open("wb") as f:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > limit:
                        f.close()
                        dest.unlink(missing_ok=True)
                        raise HTTPException(413, "파일이 너무 커요. 사진은 25MB, 녹음은 200MB 이하로 넣어 주세요.")
                    f.write(chunk)
            media_path = str(dest)
        else:
            raw = await file.read(MAX_TEXT * 4 + 1)
            if len(raw) > MAX_TEXT * 4:
                raise HTTPException(413, "글 파일이 너무 커요.")
            for enc in ("utf-8-sig", "utf-16", "cp949"):
                try:
                    text = (text + "\n" + raw.decode(enc)).strip()
                    break
                except UnicodeError:
                    continue
            else:
                raise HTTPException(400, "글 파일을 읽지 못했어요. 텍스트(txt) 파일인지 확인해 주세요.")
    text = (text or "").strip()[:MAX_TEXT]
    if not text and not media_path:
        raise HTTPException(400, "넣을 내용이 없어요.")
    with db.session() as con:
        cur = con.execute(
            "INSERT INTO inputs(user_id, kind, title, source_name, received_date, media_path, transcript) VALUES (?,?,?,?,?,?,?)",
            (user_id, kind, (title or source or "").strip()[:80], source, on.isoformat(), media_path, text),
        )
        return cur.lastrowid


@app.post("/api/inputs")
async def add_input(
    bg: BackgroundTasks,
    kind: str = Form("file"),
    title: str = Form(""),
    text: str = Form(""),
    on: str = Form(""),
    file: UploadFile | None = File(None),
    user=Depends(current_user),
):
    input_id = await _store_input(user["id"], kind, title, text, file, parse_date(on))
    bg.add_task(process_input, input_id)
    return {"id": input_id, "status": "received"}


@app.post("/share")
async def share_target(
    bg: BackgroundTasks,
    title: str = Form(""),
    text: str = Form(""),
    url: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    mh_token: str | None = Cookie(default=None),
):
    """폰의 '공유'로 들어오는 길. 받자마자 처리하고 첫 화면으로 돌려보낸다."""
    try:
        user = current_user(mh_token)
    except HTTPException:
        return RedirectResponse("/?shared=join", status_code=303)
    count = 0
    body = "\n".join(x for x in (text, url) if x).strip()
    for f in files or []:
        try:
            bg.add_task(process_input, await _store_input(user["id"], "file", title, "", f, today()))
            count += 1
        except HTTPException:
            continue
    if body:
        bg.add_task(process_input, await _store_input(user["id"], "file", title, body, None, today()))
        count += 1
    return RedirectResponse(f"/?shared={count}", status_code=303)


@app.get("/api/inputs")
def list_inputs(limit: int = 60, user=Depends(current_user)):
    with db.session() as con:
        rows = con.execute(
            """SELECT i.*, (SELECT COUNT(*) FROM items t WHERE t.input_id = i.id AND t.status NOT IN ('skipped','other')) AS item_count
               FROM inputs i WHERE i.user_id = ? ORDER BY i.id DESC LIMIT ?""",
            (user["id"], max(1, min(limit, 200))),
        ).fetchall()
    return [input_dict(r) for r in rows]


def _own_input(con, input_id: int, user_id: int):
    row = con.execute("SELECT * FROM inputs WHERE id = ? AND user_id = ?", (input_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, "찾지 못했어요.")
    return row


@app.get("/api/inputs/{input_id}")
def get_input(input_id: int, user=Depends(current_user)):
    with db.session() as con:
        row = _own_input(con, input_id, user["id"])
        items = con.execute("SELECT * FROM items WHERE input_id = ? ORDER BY id", (input_id,)).fetchall()
    d = input_dict(row, with_text=True)
    d["items"] = [item_dict(r) for r in items]
    return d


class InputPatch(BaseModel):
    me_speaker: str | None = None
    kind: str | None = None
    title: str | None = None
    reextract: bool = False
    reset: bool = False   # 이 녹음에서 나온 할 일을 상태와 관계없이 모두 지우고 처음부터 다시 뽑는다


@app.patch("/api/inputs/{input_id}")
def patch_input(input_id: int, body: InputPatch, bg: BackgroundTasks, user=Depends(current_user)):
    with db.session() as con:
        row = _own_input(con, input_id, user["id"])
        again = body.reextract or body.reset
        if body.reset:
            refs = [r["cal_ref"] for r in con.execute("SELECT cal_ref FROM items WHERE input_id = ? AND cal_ref IS NOT NULL", (input_id,))]
            con.execute("DELETE FROM items WHERE input_id = ?", (input_id,))
            for ref in refs:  # 캘린더에 들어간 것도 빼 준다
                bg.add_task(calsync.sync_item, user["id"], 0, ref)
        if body.me_speaker is not None:
            names = json.loads(row["speakers"] or "[]")
            if body.me_speaker and body.me_speaker not in names:
                raise HTTPException(400, "그 화자는 이 녹음에 없어요.")
            con.execute("UPDATE inputs SET me_speaker = ? WHERE id = ?", (body.me_speaker or None, input_id))
            again = True
        if body.kind in KINDS:
            con.execute("UPDATE inputs SET kind = ? WHERE id = ?", (body.kind, input_id))
            again = True
        if body.title is not None:
            con.execute("UPDATE inputs SET title = ? WHERE id = ?", (body.title.strip()[:80], input_id))
    if again:
        _set_input(input_id, status="received")
        bg.add_task(process_input, input_id)
    return {"ok": True, "reextract": again}


@app.delete("/api/inputs/{input_id}")
def delete_input(input_id: int, user=Depends(current_user)):
    with db.session() as con:
        row = _own_input(con, input_id, user["id"])
        if row["media_path"]:
            Path(row["media_path"]).unlink(missing_ok=True)
        con.execute("DELETE FROM items WHERE input_id = ? AND status IN ('new','other')", (input_id,))
        con.execute("DELETE FROM inputs WHERE id = ?", (input_id,))  # 이미 고른 항목은 남는다
    return {"ok": True}


@app.get("/api/inputs/{input_id}/minutes.md")
def minutes_md(input_id: int, user=Depends(current_user)):
    """회의록을 Markdown 파일로. 복사하거나 다른 메모 앱에 붙인다."""
    from fastapi.responses import Response

    with db.session() as con:
        row = _own_input(con, input_id, user["id"])
        items = con.execute("SELECT * FROM items WHERE input_id = ? ORDER BY id", (input_id,)).fetchall()
    d = input_dict(row)
    md = extract.minutes_markdown(d["title"] or KIND_LABEL.get(d["kind"], "회의"), d["received_date"], d["summary"], d["minutes"],
                                  [item_dict(i) for i in items])
    name = (d["title"] or "회의록").rsplit(".", 1)[0][:40]
    from urllib.parse import quote
    return Response(md, media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}.md"})


KIND_LABEL = {"call": "통화", "meeting": "회의", "memo": "내 메모", "file": "파일", "photo": "사진"}


# ---------- 날짜별 화면 ----------
@app.get("/api/day")
def day(date_: str | None = Query(None, alias="date"), user=Depends(current_user)):
    d, t = parse_date(date_), today()
    ds, uid = d.isoformat(), user["id"]
    with db.session() as con:
        q = lambda sql, *a: con.execute(sql, a).fetchall()  # noqa: E731
        if d == t:
            todo = q("SELECT * FROM items WHERE user_id = ? AND status = 'todo' AND plan_date <= ? ORDER BY (plan_time IS NULL), plan_time, plan_date, id", uid, ds)
            new = q("SELECT * FROM items WHERE user_id = ? AND status = 'new' ORDER BY id DESC", uid)
        else:
            todo = q("SELECT * FROM items WHERE user_id = ? AND status = 'todo' AND plan_date = ? ORDER BY (plan_time IS NULL), plan_time, id", uid, ds)
            new = []
        done = q("SELECT * FROM items WHERE user_id = ? AND status = 'done' AND done_at = ? ORDER BY updated_at", uid, ds)
        # 오늘 화면에선 '대신 적어 뒀어요'에 이미 보이는 새 항목을 '기한' 칸에 또 보이지 않게
        due = q("SELECT * FROM items WHERE user_id = ? AND status IN ('new','later') AND due_date = ? ORDER BY id", uid, ds)
        if new:
            shown = {r["id"] for r in new}
            due = [r for r in due if r["id"] not in shown]
        log = con.execute("SELECT summary, note, mood FROM day_logs WHERE user_id = ? AND date = ?", (uid, ds)).fetchone()
        pending_rows = con.execute(
            "SELECT id, title, kind, status, length(transcript) AS chars, created_at FROM inputs WHERE user_id = ? AND status IN ('received','transcribing','ready','extracting') ORDER BY id",
            (uid,),
        ).fetchall()
        pending = len(pending_rows)
        need_me = q(
            "SELECT id, title, kind, speakers FROM inputs WHERE user_id = ? AND status = 'extracted' AND me_speaker IS NULL AND speakers != '[]' ORDER BY id DESC LIMIT 3",
            uid,
        ) if d == t else []
        # 이날 넣은 회의·통화의 요약. 첫 화면에 접힌 한 줄로 보여 준다
        briefs = q(
            "SELECT id, title, kind, summary, (minutes != '') AS has_minutes FROM inputs WHERE user_id = ? AND received_date = ? AND (summary != '' OR minutes != '') ORDER BY id DESC LIMIT 10",
            uid, ds,
        )
    return {
        "date": ds,
        "today": t.isoformat(),
        "is_today": d == t,
        "new": [item_dict(r) for r in new],
        "todo": [item_dict(r, t if d == t else None) for r in todo],
        "done": [item_dict(r) for r in done],
        "due": [item_dict(r) for r in due],
        "summary": log["summary"] if log else "",
        "note": log["note"] if log else "",
        "mood": log["mood"] if log else "",
        "pending_inputs": pending,
        "pending": [{"id": r["id"], "title": r["title"], "kind": r["kind"], "status": r["status"], "long": (r["chars"] or 0) > 10000} for r in pending_rows],
        "need_me": [{"id": r["id"], "title": r["title"], "kind": r["kind"], "speakers": json.loads(r["speakers"])} for r in need_me],
        "briefs": [dict(r) for r in briefs],
    }


@app.get("/api/stats")
def stats(days: int = 30, user=Depends(current_user)):
    """쓰임새 수치 (공모 글·회고용). 최근 N일: 넣은 것, 처리 시간, 뽑힌 할 일과 '안 함' 비율, 직접 적은 것, 끝낸 것."""
    days = max(1, min(days, 365))
    uid = user["id"]
    with db.session() as con:
        since = f"-{days} days"
        inputs = con.execute(
            "SELECT kind, status, length(transcript) AS chars, (julianday(done_at) - julianday(created_at)) * 86400 AS secs, minutes != '' AS has_minutes"
            " FROM inputs WHERE user_id = ? AND created_at >= datetime('now', ?)", (uid, since)).fetchall()
        items = con.execute(
            "SELECT status, owner, input_id IS NULL AS manual, input_id FROM items WHERE user_id = ? AND created_at >= datetime('now', ?)", (uid, since)).fetchall()
        meeting_ids = {r["id"] for r in con.execute(
            "SELECT id FROM inputs WHERE user_id = ? AND kind = 'meeting' AND status = 'extracted' AND created_at >= datetime('now', ?)", (uid, since))}
    done_inputs = [r for r in inputs if r["status"] == "extracted" and r["secs"] is not None]
    secs = sorted(r["secs"] for r in done_inputs)
    long_secs = sorted(r["secs"] for r in done_inputs if (r["chars"] or 0) > 10000)
    med = (lambda a: a[len(a) // 2] if a else None)
    from_inputs = [r for r in items if not r["manual"]]
    mine = [r for r in from_inputs if r["status"] != "other"]
    by_kind: dict = {}
    for r in inputs:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
    meeting_mine = [r for r in mine if r["input_id"] in meeting_ids]
    return {
        "days": days,
        "inputs": {"total": len(inputs), "by_kind": by_kind, "failed": sum(1 for r in inputs if r["status"] == "failed"),
                   "with_minutes": sum(1 for r in inputs if r["has_minutes"])},
        "seconds_to_list": {"median": med(secs), "median_long": med(long_secs), "max": secs[-1] if secs else None},
        "items": {"extracted_mine": len(mine), "delegated": len(from_inputs) - len(mine), "manual": sum(1 for r in items if r["manual"]),
                  "skipped": sum(1 for r in mine if r["status"] == "skipped"),
                  "skip_ratio": round(sum(1 for r in mine if r["status"] == "skipped") / len(mine), 3) if mine else None,
                  "done": sum(1 for r in items if r["status"] == "done"),
                  "per_meeting": round(len(meeting_mine) / len(meeting_ids), 1) if meeting_ids else None},
    }


@app.get("/api/week")
def week(date_: str | None = Query(None, alias="date"), user=Depends(current_user)):
    """달력 띠: 해당 날짜가 든 주(월~일)의 날짜별 개수."""
    d, t = parse_date(date_), today()
    start = d - timedelta(days=d.weekday())
    out = []
    with db.session() as con:
        for i in range(7):
            x = start + timedelta(days=i)
            xs = x.isoformat()
            if x == t:
                left = con.execute("SELECT COUNT(*) n FROM items WHERE user_id = ? AND status = 'todo' AND plan_date <= ?", (user["id"], xs)).fetchone()["n"]
            else:
                left = con.execute("SELECT COUNT(*) n FROM items WHERE user_id = ? AND status = 'todo' AND plan_date = ?", (user["id"], xs)).fetchone()["n"]
            done = con.execute("SELECT COUNT(*) n FROM items WHERE user_id = ? AND status = 'done' AND done_at = ?", (user["id"], xs)).fetchone()["n"]
            out.append({"date": xs, "left": left, "done": done})
    return out


def _local_offset() -> str:
    """created_at(UTC)을 그 지역 날짜로 바꿀 때 쓰는 SQLite 수정자. 예: '+32400 seconds'"""
    off = datetime.now(TZ).utcoffset() or timedelta(0)
    return f"{int(off.total_seconds()):+d} seconds"


def day_score(added: int, done: int, closed: bool, noted: bool) -> int:
    """하루 활용 점수 0~5. 넣음 1, 마침 1(3건 이상 2), 마무리 1, 한 줄/기분 1."""
    return (1 if added else 0) + (2 if done >= 3 else 1 if done else 0) + (1 if closed else 0) + (1 if noted else 0)


@app.get("/api/month")
def month(ym: str | None = None, user=Depends(current_user)):
    """달력 뷰: 날마다 마친 수 · 남은 수 · 기분 · 마무리 여부 · 점수, 이달 활용 지수(0~100)와 연속 일수."""
    t = today()
    try:
        y, m = (int(x) for x in (ym or t.strftime("%Y-%m")).split("-"))
        first = date(y, m, 1)
    except (ValueError, TypeError):
        raise HTTPException(400, "달은 YYYY-MM 꼴이어야 해요.")
    last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    uid, lo, hi, off = user["id"], first.isoformat(), last.isoformat(), _local_offset()
    with db.session() as con:
        done = {r["d"]: r["n"] for r in con.execute("SELECT done_at d, COUNT(*) n FROM items WHERE user_id = ? AND status = 'done' AND done_at BETWEEN ? AND ? GROUP BY done_at", (uid, lo, hi))}
        left = {r["d"]: r["n"] for r in con.execute("SELECT plan_date d, COUNT(*) n FROM items WHERE user_id = ? AND status = 'todo' AND plan_date BETWEEN ? AND ? GROUP BY plan_date", (uid, lo, hi))}
        added = {r["d"]: r["n"] for r in con.execute("SELECT date(created_at, ?) d, COUNT(*) n FROM items WHERE user_id = ? AND date(created_at, ?) BETWEEN ? AND ? GROUP BY d", (off, uid, off, lo, hi))}
        inputs = {r["d"]: r["n"] for r in con.execute("SELECT date(created_at, ?) d, COUNT(*) n FROM inputs WHERE user_id = ? AND date(created_at, ?) BETWEEN ? AND ? GROUP BY d", (off, uid, off, lo, hi))}
        logs = {r["date"]: r for r in con.execute("SELECT date, summary, note, mood FROM day_logs WHERE user_id = ? AND date BETWEEN ? AND ?", (uid, lo, hi))}
    days = []
    for i in range((last - first).days + 1):
        x = (first + timedelta(days=i)).isoformat()
        lg = logs.get(x)
        sc = day_score(added.get(x, 0) + inputs.get(x, 0), done.get(x, 0), bool(lg and lg["summary"]), bool(lg and (lg["mood"] or lg["note"])))
        days.append({"date": x, "done": done.get(x, 0), "left": left.get(x, 0), "inputs": inputs.get(x, 0),
                     "mood": lg["mood"] if lg else "", "note": lg["note"] if lg else "", "closed": bool(lg and lg["summary"]), "score": sc})
    elapsed = [d for d in days if d["date"] <= t.isoformat()]
    active = sum(1 for d in elapsed if d["score"])
    streak = 0
    if first <= t:
        for d in reversed(elapsed):
            if not d["score"]:
                break
            streak += 1
    return {
        "ym": first.strftime("%Y-%m"), "today": t.isoformat(), "days": days,
        "elapsed_days": len(elapsed), "active_days": active, "streak": streak,
        "done_total": sum(d["done"] for d in days), "left_total": sum(d["left"] for d in days),
        # 한 줄을 안 켠 사람은 만점이 4점이라 분모도 4로 — 켜고 안 켜고가 지수에 불리하지 않게
        "score": round(100 * sum(d["score"] for d in elapsed) / ((5 if _diary_on(uid) else 4) * len(elapsed))) if elapsed else 0,
        "post_url": os.environ.get("MALHAN_POST_URL", "").strip(),
    }


# ---------- 항목 ----------
@app.get("/api/items")
def list_items(status: str = "later", user=Depends(current_user)):
    if status not in STATUSES:
        raise HTTPException(400, "알 수 없는 상태예요.")
    with db.session() as con:
        rows = con.execute(
            "SELECT * FROM items WHERE user_id = ? AND status = ? ORDER BY (due_date IS NULL), due_date, id DESC LIMIT 300",
            (user["id"], status),
        ).fetchall()
    return [item_dict(r) for r in rows]


class ItemNew(BaseModel):
    text: str
    scope: str = "개인"
    plan_date: str | None = None


@app.post("/api/items")
def add_item(body: ItemNew, bg: BackgroundTasks, user=Depends(current_user)):
    text = body.text.strip()[:200]
    if not text:
        raise HTTPException(400, "할 일을 적어 주세요.")
    plan = parse_date(body.plan_date).isoformat()
    with db.session() as con:
        cur = con.execute(
            "INSERT INTO items(user_id, text, scope, status, plan_date) VALUES (?,?,?,'todo',?)",
            (user["id"], text, "회사" if body.scope == "회사" else "개인", plan),
        )
        row = con.execute("SELECT * FROM items WHERE id = ?", (cur.lastrowid,)).fetchone()
    bg.add_task(calsync.sync_item, user["id"], row["id"])
    return item_dict(row)


class ItemPatch(BaseModel):
    status: str | None = None
    plan_date: str | None = None
    plan_time: str | None = None   # "HH:MM", 빈 문자열이면 시각 지움
    text: str | None = None
    scope: str | None = None


class AcceptAll(BaseModel):
    ids: list[int] | None = None


@app.post("/api/items/accept-all")
def accept_all(body: AcceptAll, bg: BackgroundTasks, user=Depends(current_user)):
    """새로 적어 둔 것을 한 번에 넣는다: 기한이 앞날이면 그 날짜로, 아니면 오늘로."""
    t = today().isoformat()
    with db.session() as con:
        rows = con.execute("SELECT id, due_date FROM items WHERE user_id = ? AND status = 'new'", (user["id"],)).fetchall()
        n = 0
        for r in rows:
            if body.ids is not None and r["id"] not in body.ids:
                continue
            plan = r["due_date"] if r["due_date"] and r["due_date"] >= t else t
            con.execute("UPDATE items SET status = 'todo', owner = 'me', plan_date = ?, updated_at = datetime('now') WHERE id = ?", (plan, r["id"]))
            bg.add_task(calsync.sync_item, user["id"], r["id"])
            n += 1
    return {"moved": n}


class SkipAll(BaseModel):
    input_id: int | None = None


@app.post("/api/items/skip-all")
def skip_all(body: SkipAll, user=Depends(current_user)):
    """새로 적어 둔 것을 한 번에 '안 함'으로. input_id를 주면 그 녹음에서 나온 것만."""
    with db.session() as con:
        where, args = "user_id = ? AND status = 'new'", [user["id"]]
        if body.input_id is not None:
            where += " AND input_id = ?"
            args.append(body.input_id)
        ids = [r["id"] for r in con.execute(f"SELECT id FROM items WHERE {where}", args)]
        con.execute(f"UPDATE items SET status = 'skipped', updated_at = datetime('now') WHERE {where}", args)
    return {"skipped": len(ids), "ids": ids}


class Restore(BaseModel):
    ids: list[int]


@app.post("/api/items/restore")
def restore_items(body: Restore, user=Depends(current_user)):
    """'모두 안 함'을 되돌린다: 준 id 중 안 함 상태인 것만 다시 '새로 적어 둔 것'으로."""
    if not body.ids:
        return {"restored": 0}
    marks = ",".join("?" * len(body.ids[:500]))
    with db.session() as con:
        cur = con.execute(f"UPDATE items SET status = 'new', updated_at = datetime('now') WHERE user_id = ? AND status = 'skipped' AND id IN ({marks})",
                          (user["id"], *body.ids[:500]))
    return {"restored": cur.rowcount}


@app.patch("/api/items/{item_id}")
def patch_item(item_id: int, body: ItemPatch, bg: BackgroundTasks, user=Depends(current_user)):
    with db.session() as con:
        row = con.execute("SELECT * FROM items WHERE id = ? AND user_id = ?", (item_id, user["id"])).fetchone()
        if not row:
            raise HTTPException(404, "찾지 못했어요.")
        f: dict = {}
        if body.text is not None and body.text.strip():
            f["text"] = body.text.strip()[:200]
        if body.scope in ("개인", "회사"):
            f["scope"] = body.scope
        if body.plan_time is not None:
            if body.plan_time and not extract._TIME.match(body.plan_time):
                raise HTTPException(400, "시각은 HH:MM 꼴이어야 해요.")
            f["plan_time"] = body.plan_time.zfill(5) if body.plan_time else None
        if body.status is not None:
            if body.status not in STATUSES:
                raise HTTPException(400, "알 수 없는 상태예요.")
            f["status"] = body.status
            if body.status != "other":
                f["owner"] = "me"  # 직접 고른 일은 내 일이다
            if body.status == "todo":
                f["plan_date"] = parse_date(body.plan_date).isoformat()
                f["done_at"] = None
            elif body.status == "done":
                f["done_at"] = today().isoformat()
                f["plan_date"] = row["plan_date"] or today().isoformat()
            else:
                f["plan_date"] = None
                f["done_at"] = None
        elif body.plan_date is not None and row["status"] == "todo":
            f["plan_date"] = parse_date(body.plan_date).isoformat()
        if f:
            cols = ", ".join(f"{k} = ?" for k in f)
            con.execute(f"UPDATE items SET {cols}, updated_at = datetime('now') WHERE id = ?", (*f.values(), item_id))
        row = con.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if f:
        bg.add_task(calsync.sync_item, user["id"], item_id)
    return item_dict(row, today())


@app.delete("/api/items/{item_id}")
def delete_item(item_id: int, bg: BackgroundTasks, user=Depends(current_user)):
    with db.session() as con:
        row = con.execute("SELECT cal_ref, addon FROM items WHERE id = ? AND user_id = ?", (item_id, user["id"])).fetchone()
        con.execute("DELETE FROM items WHERE id = ? AND user_id = ?", (item_id, user["id"]))
    if row and row["cal_ref"] and row["addon"] != "calendar":  # 캘린더에서 가져온 일정은 지우지 않는다
        bg.add_task(calsync.sync_item, user["id"], item_id, row["cal_ref"])
    return {"ok": True}


# ---------- 바깥 캘린더 ----------
def _own_item(item_id: int, user_id: int):
    with db.session() as con:
        row = con.execute("SELECT * FROM items WHERE id = ? AND user_id = ?", (item_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, "찾지 못했어요.")
    return row


def _times(row, time_: str | None):
    try:
        return calsync.event_times(row, time_, today())
    except ValueError:
        raise HTTPException(400, "시각은 HH:MM 꼴이어야 해요.")


@app.get("/api/items/{item_id}/calendar")
def calendar_links(item_id: int, time: str | None = None, user=Depends(current_user)):
    """손으로 넣을 때: 구글 캘린더 등록 화면 주소와, 다른 캘린더 앱용 일정 파일 주소."""
    from urllib.parse import urlencode

    row = _own_item(item_id, user["id"])
    d, start, end = _times(row, time)
    if start:
        dates = f"{start.astimezone(calsync.UTC):%Y%m%dT%H%M%SZ}/{end.astimezone(calsync.UTC):%Y%m%dT%H%M%SZ}"
    else:
        dates = f"{d:%Y%m%d}/{d + timedelta(days=1):%Y%m%d}"
    google = "https://calendar.google.com/calendar/render?" + urlencode(
        {"action": "TEMPLATE", "text": row["text"], "dates": dates, "details": row["quote"] or "말한대로에서 보냄"}
    )
    ics = f"/api/items/{item_id}/event.ics" + (f"?{urlencode({'time': time})}" if time else "")
    return {"google_url": google, "ics_url": ics, "date": d.isoformat()}


@app.get("/api/items/{item_id}/event.ics")
def event_ics(item_id: int, time: str | None = None, user=Depends(current_user)):
    """캘린더 앱이 여는 일정 파일. 알림을 함께 넣어 휴대폰 캘린더가 알려 주게 한다."""
    from fastapi.responses import Response

    row = _own_item(item_id, user["id"])
    _times(row, time)  # 시각 형식 확인
    return Response(calsync.build_ics(row, f"item-{item_id}@malhandaero", time), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="malhandaero-{item_id}.ics"'})


def _calendar_state(user_id: int) -> dict:
    link = calsync.get_link(user_id)
    out = {"provider": "", "mode": "timed", "status": "", "label": "", "google_ready": calsync.google_client() is not None}
    if link:
        cfg = link["config"]
        out.update(provider=link["provider"], mode=link["mode"], status=link["status"],
                   label=cfg.get("calendar_name") or cfg.get("user") or "",
                   read_source={"id": cfg.get("read_calendar_id") or cfg.get("read_calendar_url") or "", "name": cfg.get("read_calendar_name") or ""},
                   write_target={"id": cfg.get("write_calendar_id") or cfg.get("calendar_url") or "", "name": cfg.get("calendar_name") or ""})
    return out


@app.get("/api/calendar")
def calendar_get(user=Depends(current_user)):
    return _calendar_state(user["id"])


class NaverLink(BaseModel):
    user: str
    password: str
    calendar_url: str | None = None


@app.post("/api/calendar/naver")
def calendar_naver(body: NaverLink, user=Depends(current_user)):
    """네이버 아이디와 애플리케이션 비밀번호로 연결한다. 캘린더가 여럿이면 목록을 돌려주고 첫 번째를 쓴다."""
    uid, pw = body.user.strip().split("@")[0], body.password.strip()
    if not uid or not pw:
        raise HTTPException(400, "네이버 아이디와 애플리케이션 비밀번호를 넣어 주세요.")
    try:
        cals = calsync.Naver(uid, pw).calendars()
    except calsync.CalendarError as e:
        raise HTTPException(400, str(e))
    chosen = next((c for c in cals if c["url"] == body.calendar_url), cals[0])
    calsync.save_link(user["id"], "naver", {"user": uid, "password": pw, "calendar_url": chosen["url"], "calendar_name": chosen["name"] or "네이버 캘린더"})
    return {**_calendar_state(user["id"]), "calendars": cals}


def _redirect_uri(request: Request) -> str:
    # 프록시(Tailscale) 뒤에서는 바깥 주소를 써야 구글에 등록한 주소와 맞는다
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}/api/calendar/google/callback"


@app.get("/api/calendar/google/start")
def calendar_google_start(request: Request, user=Depends(current_user)):
    if not calsync.google_client():
        raise HTTPException(503, "구글 연결 준비가 안 됐어요. INSTALL.md의 '구글 캘린더 연결 준비'를 먼저 해 주세요.")
    state = secrets.token_urlsafe(16)
    res = RedirectResponse(calsync.google_auth_url(_redirect_uri(request), state), status_code=303)
    res.set_cookie("mh_gstate", state, max_age=600, httponly=True, samesite="lax")
    return res


@app.get("/api/calendar/google/callback")
def calendar_google_callback(request: Request, code: str = "", state: str = "", error: str = "",
                             mh_gstate: str | None = Cookie(default=None), mh_token: str | None = Cookie(default=None)):
    try:
        user = current_user(mh_token)
    except HTTPException:
        return RedirectResponse("/?cal=join", status_code=303)
    if error or not code or not mh_gstate or not secrets.compare_digest(state.encode(), mh_gstate.encode()):
        return RedirectResponse("/?cal=fail", status_code=303)
    try:
        refresh = calsync.google_exchange(code, _redirect_uri(request))
    except calsync.CalendarError:
        return RedirectResponse("/?cal=fail", status_code=303)
    calsync.save_link(user["id"], "google", {"refresh_token": refresh, "calendar_name": "구글 캘린더"})
    res = RedirectResponse("/?cal=ok", status_code=303)
    res.delete_cookie("mh_gstate")
    return res


@app.get("/api/calendar/events")
def calendar_events(date_: str | None = Query(None, alias="date"), user=Depends(current_user)):
    """연결된 캘린더의 그날 일정. 이미 할 일로 가져온 것은 item_id가 붙는다."""
    link = calsync.get_link(user["id"])
    if not link:
        return {"linked": False, "events": []}
    d = parse_date(date_)
    try:
        evs = calsync.day_events(link, d)
    except calsync.CalendarError as e:
        return {"linked": True, "events": [], "error": str(e)}
    except Exception as e:
        return {"linked": True, "events": [], "error": f"캘린더를 읽지 못했어요: {type(e).__name__}"}
    with db.session() as con:
        have = {r["cal_ref"]: (r["id"], r["addon"]) for r in con.execute("SELECT id, cal_ref, addon FROM items WHERE user_id = ? AND cal_ref IS NOT NULL", (user["id"],))}
        hidden = {r["ref"] for r in con.execute("SELECT ref FROM calendar_hidden WHERE user_id = ?", (user["id"],))}
    out, n_hidden = [], 0
    for e in evs:
        hit = have.get(e["ref"])
        if hit and hit[1] != "calendar":
            continue  # 말한대로가 올린 일정은 할 일 쪽에 '캘린더 ✓'로 보인다
        if e["ref"] in hidden:
            n_hidden += 1
            continue
        e["item_id"] = hit[0] if hit else None
        out.append(e)
    return {"linked": True, "events": out, "hidden": n_hidden}


class EventRef(BaseModel):
    ref: str = ""


@app.post("/api/calendar/events/hide")
def calendar_hide(body: EventRef, user=Depends(current_user)):
    """캘린더 일정 하나를 목록에서 숨긴다 (캘린더 쪽은 그대로)."""
    if not body.ref:
        raise HTTPException(400, "어느 일정인지 모르겠어요.")
    with db.session() as con:
        con.execute("INSERT OR IGNORE INTO calendar_hidden(user_id, ref) VALUES (?, ?)", (user["id"], body.ref))
    return {"ok": True}


@app.post("/api/calendar/events/unhide")
def calendar_unhide(body: EventRef, user=Depends(current_user)):
    """숨긴 일정을 다시 보이게. ref를 비우면 모두."""
    with db.session() as con:
        if body.ref:
            con.execute("DELETE FROM calendar_hidden WHERE user_id = ? AND ref = ?", (user["id"], body.ref))
        else:
            con.execute("DELETE FROM calendar_hidden WHERE user_id = ?", (user["id"],))
    return {"ok": True}


@app.get("/api/calendar/sources")
def calendar_sources(user=Depends(current_user)):
    """일정을 읽어 올 수 있는 캘린더 목록 (공유 캘린더 포함)."""
    link = calsync.get_link(user["id"])
    if not link:
        raise HTTPException(400, "먼저 캘린더를 연결해 주세요.")
    cfg = link["config"]
    try:
        if link["provider"] == "naver":
            cals = [{"id": c["url"], "name": c["name"] or "네이버 캘린더", "primary": c["url"] == cfg.get("calendar_url")} for c in calsync.Naver(cfg["user"], cfg["password"]).calendars()]
        else:
            cals = calsync.Google(cfg["refresh_token"]).calendars()
    except calsync.CalendarError as e:
        raise HTTPException(400, str(e))
    return {"sources": cals}


class ReadSource(BaseModel):
    id: str = ""      # 구글: 캘린더 ID / 네이버: 캘린더 주소. 비우면 쓰는 캘린더와 같게
    name: str = ""


@app.post("/api/calendar/source")
def calendar_set_source(body: ReadSource, user=Depends(current_user)):
    """일정을 읽어 올 캘린더를 정한다. 올리는 캘린더는 그대로다."""
    link = calsync.get_link(user["id"])
    if not link:
        raise HTTPException(400, "먼저 캘린더를 연결해 주세요.")
    sid = body.id.strip()
    if link["provider"] == "naver":
        calsync.update_config(user["id"], read_calendar_url=sid or None, read_calendar_name=body.name.strip()[:60] if sid else "")
    else:
        calsync.update_config(user["id"], read_calendar_id=sid or None, read_calendar_name=body.name.strip()[:60] if sid else "")
    return _calendar_state(user["id"])


@app.post("/api/calendar/target")
def calendar_set_target(body: ReadSource, bg: BackgroundTasks, user=Depends(current_user)):
    """할 일을 올릴 캘린더를 정한다. 이미 올라간 일정은 예전 캘린더에 그대로 남고, 앞으로 올리는 것부터 새 캘린더로 간다."""
    link = calsync.get_link(user["id"])
    if not link:
        raise HTTPException(400, "먼저 캘린더를 연결해 주세요.")
    sid = body.id.strip()
    if not sid:
        raise HTTPException(400, "올릴 캘린더를 골라 주세요.")
    name = body.name.strip()[:60] or ("네이버 캘린더" if link["provider"] == "naver" else "구글 캘린더")
    cfg = link["config"]
    current = cfg.get("calendar_url") if link["provider"] == "naver" else (cfg.get("write_calendar_id") or "primary")
    if sid == current or (link["provider"] == "google" and sid == "primary-id" and current == "primary"):
        return _calendar_state(user["id"])  # 같은 캘린더면 아무것도 바꾸지 않는다 (다시 올리면 중복이 생긴다)
    with db.session() as con:  # 예전 캘린더에 올라간 일정은 옮긴다: 예전 데서 지우고 새 데 올린다
        moving = [(r["id"], r["cal_ref"]) for r in con.execute("SELECT id, cal_ref FROM items WHERE user_id = ? AND cal_ref IS NOT NULL AND addon != 'calendar'", (user["id"],))]
    old_link = {**link, "config": dict(cfg)}
    for _, ref in moving:
        bg.add_task(calsync.remove_ref, old_link, ref)  # 예전 설정으로 예전 캘린더에서 뺀다
    if link["provider"] == "naver":
        calsync.update_config(user["id"], calendar_url=sid, calendar_name=name)
    else:
        calsync.update_config(user["id"], write_calendar_id=sid, calendar_name=name)
    with db.session() as con:
        con.execute("UPDATE items SET cal_ref = NULL WHERE user_id = ? AND addon != 'calendar'", (user["id"],))
        ids = [r["id"] for r in con.execute("SELECT id FROM items WHERE user_id = ? AND status = 'todo' AND plan_date >= ?", (user["id"], today().isoformat()))]
    for i in ids:
        bg.add_task(calsync.sync_item, user["id"], i)
    return _calendar_state(user["id"])


class ImportEvent(BaseModel):
    ref: str
    title: str
    time: str | None = None
    date: str | None = None
    scope: str = "회사"


@app.post("/api/calendar/events/import")
def calendar_import(body: ImportEvent, user=Depends(current_user)):
    """캘린더 일정을 그날 할 일로 가져온다. cal_ref로 같은 일정을 가리키되 addon='calendar'로 표시해, 캘린더 쪽 일정은 건드리지 않는다(원본은 캘린더)."""
    d = parse_date(body.date).isoformat()
    title = body.title.strip()[:200]
    if not title:
        raise HTTPException(400, "일정 제목이 비어 있어요.")
    if body.time and not extract._TIME.match(body.time):
        raise HTTPException(400, "시각은 HH:MM 꼴이어야 해요.")
    with db.session() as con:
        row = con.execute("SELECT * FROM items WHERE user_id = ? AND cal_ref = ?", (user["id"], body.ref)).fetchone()
        if row:
            return {**item_dict(row, today()), "already": True}
        cur = con.execute(
            "INSERT INTO items(user_id, text, quote, scope, status, plan_date, plan_time, cal_ref, addon) VALUES (?,?,?,?,'todo',?,?,?,'calendar')",
            (user["id"], title, "캘린더 일정에서 가져옴", "회사" if body.scope == "회사" else "개인", d, body.time.zfill(5) if body.time else None, body.ref),
        )
        row = con.execute("SELECT * FROM items WHERE id = ?", (cur.lastrowid,)).fetchone()
    return item_dict(row, today())


class CalendarMode(BaseModel):
    mode: str


@app.post("/api/calendar/mode")
def calendar_mode(body: CalendarMode, bg: BackgroundTasks, user=Depends(current_user)):
    if body.mode not in ("timed", "all"):
        raise HTTPException(400, "알 수 없는 설정이에요.")
    with db.session() as con:
        con.execute("UPDATE calendar_links SET mode = ? WHERE user_id = ?", (body.mode, user["id"]))
        ids = [r["id"] for r in con.execute("SELECT id FROM items WHERE user_id = ? AND status = 'todo' AND plan_date >= ?", (user["id"], today().isoformat()))]
    for i in ids:  # 앞으로 할 일을 새 기준에 맞춘다
        bg.add_task(calsync.sync_item, user["id"], i)
    return _calendar_state(user["id"])


@app.delete("/api/calendar")
def calendar_unlink(user=Depends(current_user)):
    """연결을 끊는다. 캘린더의 일정도, 할 일의 일정 번호도 그대로 둔다(같은 종류로 다시 연결하면 중복 없이 이어진다)."""
    calsync.unlink(user["id"])
    return _calendar_state(user["id"])


# ---------- 하루 정리 ----------
@app.post("/api/day/close")
def close_day(date_: str | None = Query(None, alias="date"), user=Depends(current_user)):
    d, t = parse_date(date_), today()
    ds, uid = d.isoformat(), user["id"]
    with db.session() as con:
        done = [r["text"] for r in con.execute("SELECT text FROM items WHERE user_id = ? AND status = 'done' AND done_at = ?", (uid, ds))]
        op = "<=" if d == t else "="
        left = [r["text"] for r in con.execute(f"SELECT text FROM items WHERE user_id = ? AND status = 'todo' AND plan_date {op} ?", (uid, ds))]
        later = [r["text"] for r in con.execute("SELECT text FROM items WHERE user_id = ? AND status = 'later' LIMIT 20", (uid,))]
        log = con.execute("SELECT note, mood FROM day_logs WHERE user_id = ? AND date = ?", (uid, ds)).fetchone()
    day_note_ = " ".join(x for x in [(log["mood"] if log else ""), (log["note"] if log else "")] if x).strip()
    if not done and not left and not day_note_:
        return {"summary": "", "note": "이날 고른 일이 없어요."}
    try:
        summary = llm.complete(extract.summary_prompt(d, done, left, later, day_note_), max_tokens=400).strip()
    except Exception:
        summary = ""
    summary = summary or extract.plain_summary(done, left)
    with db.session() as con:
        con.execute(
            "INSERT INTO day_logs(user_id, date, summary) VALUES (?,?,?) ON CONFLICT(user_id, date) DO UPDATE SET summary = excluded.summary, created_at = datetime('now')",  # note/mood는 그대로
            (uid, ds, summary),
        )
    return {"summary": summary}


# ---------- 화면 파일 ----------
@app.get("/")
def index():
    """화면 파일에 버전을 붙여 낸다: 업데이트 뒤 폰이 예전 style.css·app.js를 캐시에서 꺼내 쓰지 않게."""
    v = _version() or "0"
    html = (WEB / "index.html").read_text(encoding="utf-8").replace('href="/style.css"', f'href="/style.css?v={v}"').replace('src="/app.js"', f'src="/app.js?v={v}"')
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


@app.middleware("http")
async def _no_stale_assets(request: Request, call_next):
    resp = await call_next(request)
    if request.url.path.endswith((".css", ".js", ".webmanifest")):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


def app_label() -> str:
    """이 서버를 구분하는 이름. .env의 MALHAN_LABEL, 비우면 PC 종류(Mac/Windows/Linux).
    한 폰에 서버 두 개(집 Mac·회사 Windows)를 각각 앱으로 깔 때 이름이 달라야 구분이 된다."""
    label = os.environ.get("MALHAN_LABEL", "").strip()
    if label:
        return label
    import platform

    return {"Darwin": "Mac", "Windows": "Windows"}.get(platform.system(), platform.system() or "")


@app.get("/api/help/{topic}")
def help_prompt(topic: str, request: Request, user=Depends(current_user)):
    """Claude·ChatGPT에 붙여 넣을 설치 도우미 글. 이 PC의 실제 값(주소·폴더·OS)을 채워 준다."""
    import platform

    f = ROOT / "docs" / "prompts" / f"{topic}.md"
    if topic not in ("google-calendar", "tailscale") or not f.exists():
        raise HTTPException(404, "그런 안내는 없어요.")
    win = os.name == "nt"
    lan = os.environ.get("MALHAN_LAN_URL", "")
    public = os.environ.get("MALHAN_PUBLIC_URL", "")
    addrs = [a for a in ("http://localhost:8000", lan, public) if a]
    redirects = [f"{a}/api/calendar/google/callback" for a in addrs if not a.startswith("http://1") and not a.startswith("http://192")]
    if public:
        redirects = [r for r in redirects if "localhost" in r or r.startswith("https")]
    text = f.read_text(encoding="utf-8").format(
        OS={"Darwin": "Mac", "Windows": "Windows"}.get(platform.system(), platform.system()),
        ROOT=str(ROOT),
        ADDRESSES=" / ".join(addrs) or "http://localhost:8000",
        REDIRECTS="\n".join(f"   - `{r}`" for r in redirects) or "   - `http://localhost:8000/api/calendar/google/callback`",
        RESTART="run.bat 더블클릭" if win else "「말한대로 켜기.command」 더블클릭",
        LAN=lan or "http://(PC 주소):8000",
        RUNFILE="run.bat" if win else "말한대로 켜기.command",
        RUNREMOTE="run.bat --remote (명령 프롬프트에서)" if win else "터미널에서 ./run.sh --remote",
    )
    return {"topic": topic, "text": text}


@app.get("/manifest.webmanifest")
def manifest():
    """앱 이름에 서버 이름을 붙여 낸다. 이름이 바뀌면 폰에서 앱을 다시 설치해야 반영된다."""
    data = json.loads((WEB / "manifest.webmanifest").read_text(encoding="utf-8"))
    label = app_label()
    if label:
        data["name"] = f"말한대로 · {label}"
        data["short_name"] = f"말한대로 {label}"[:12]
    return JSONResponse(data, media_type="application/manifest+json", headers={"Cache-Control": "no-cache"})


@app.get("/sw.js")
def service_worker():
    return FileResponse(WEB / "sw.js", media_type="application/javascript", headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=WEB), name="web")
