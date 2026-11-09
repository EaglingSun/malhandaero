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
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import calsync, db, extract, llm, stt, transcript

WEB = Path(__file__).resolve().parent.parent / "web"
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


def current_user(mh_token: str | None = Cookie(default=None)):
    if not mh_token:
        raise HTTPException(401, "먼저 들어와 주세요.")
    with db.session() as con:
        row = con.execute("SELECT id, name FROM users WHERE token = ?", (mh_token,)).fetchone()
    if not row:
        raise HTTPException(401, "먼저 들어와 주세요.")
    return row


def item_dict(r, t: date | None = None) -> dict:
    d = dict(r)
    d["carried_days"] = 0
    if t and d["status"] == "todo" and d["plan_date"] and d["plan_date"] < t.isoformat():
        d["carried_days"] = (t - date.fromisoformat(d["plan_date"])).days
    return d


def input_dict(r, with_text: bool = False) -> dict:
    d = dict(r)
    d["speakers"] = json.loads(d.get("speakers") or "[]")
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
    }


# ---------- 입력 처리(받기 → 글 → 추출) ----------
def process_input(input_id: int) -> None:
    """뒤에서 도는 작업. 실패하면 사유를 입력에 남긴다."""
    with db.session() as con:
        row = con.execute("SELECT * FROM inputs WHERE id = ?", (input_id,)).fetchone()
    if not row:
        return
    try:
        text = row["transcript"]
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
        )
        summary, cands = extract.extract(text, ctx)
        with db.session() as con:
            # 다시 뽑을 때: 이 입력에서 나왔고 아직 고르지 않은 것(새로 적어 둔 것, 남의 일)만 갈아 끼운다
            con.execute("DELETE FROM items WHERE input_id = ? AND status IN ('new','other')", (input_id,))
            kept = [r["text"] for r in con.execute("SELECT text FROM items WHERE input_id = ?", (input_id,))]
            for c in extract.dedupe(cands, kept):
                con.execute(
                    "INSERT INTO items(user_id, input_id, text, quote, due_text, due_date, plan_time, scope, owner, who, status)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (row["user_id"], input_id, c.text, c.quote, c.due_text, c.due_date, c.time, c.scope, c.owner, c.who,
                     "other" if c.owner == "other" else "new"),
                )
        _set_input(input_id, status="extracted", error="", summary=summary)
    except (llm.LlmUnavailable, stt.SttUnavailable) as e:
        _set_input(input_id, status="failed", error=str(e))
    except Exception as e:  # 뒤에서 도는 작업이라 사유를 남기고 끝낸다
        _set_input(input_id, status="failed", error=f"처리하지 못했어요: {type(e).__name__}")


def _set_input(input_id: int, **fields) -> None:
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


@app.patch("/api/inputs/{input_id}")
def patch_input(input_id: int, body: InputPatch, bg: BackgroundTasks, user=Depends(current_user)):
    with db.session() as con:
        row = _own_input(con, input_id, user["id"])
        again = body.reextract
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
        due = q("SELECT * FROM items WHERE user_id = ? AND status IN ('new','later') AND due_date = ? ORDER BY id", uid, ds)
        log = con.execute("SELECT summary FROM day_logs WHERE user_id = ? AND date = ?", (uid, ds)).fetchone()
        pending = con.execute(
            "SELECT COUNT(*) AS n FROM inputs WHERE user_id = ? AND status IN ('received','transcribing','ready','extracting')", (uid,)
        ).fetchone()["n"]
        need_me = q(
            "SELECT id, title, kind, speakers FROM inputs WHERE user_id = ? AND status = 'extracted' AND me_speaker IS NULL AND speakers != '[]' ORDER BY id DESC LIMIT 3",
            uid,
        ) if d == t else []
    return {
        "date": ds,
        "today": t.isoformat(),
        "is_today": d == t,
        "new": [item_dict(r) for r in new],
        "todo": [item_dict(r, t if d == t else None) for r in todo],
        "done": [item_dict(r) for r in done],
        "due": [item_dict(r) for r in due],
        "summary": log["summary"] if log else "",
        "pending_inputs": pending,
        "need_me": [{"id": r["id"], "title": r["title"], "kind": r["kind"], "speakers": json.loads(r["speakers"])} for r in need_me],
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
        row = con.execute("SELECT cal_ref FROM items WHERE id = ? AND user_id = ?", (item_id, user["id"])).fetchone()
        con.execute("DELETE FROM items WHERE id = ? AND user_id = ?", (item_id, user["id"]))
    if row and row["cal_ref"]:
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
        out.update(provider=link["provider"], mode=link["mode"], status=link["status"],
                   label=link["config"].get("calendar_name") or link["config"].get("user") or "")
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
    """연결을 끊는다. 이미 캘린더에 들어간 일정은 그대로 둔다."""
    with db.session() as con:
        con.execute("DELETE FROM calendar_links WHERE user_id = ?", (user["id"],))
        con.execute("UPDATE items SET cal_ref = NULL WHERE user_id = ?", (user["id"],))
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
    if not done and not left:
        return {"summary": "", "note": "이날 고른 일이 없어요."}
    try:
        summary = llm.complete(extract.summary_prompt(d, done, left, later), max_tokens=400).strip()
    except Exception:
        summary = ""
    summary = summary or extract.plain_summary(done, left)
    with db.session() as con:
        con.execute(
            "INSERT INTO day_logs(user_id, date, summary) VALUES (?,?,?) ON CONFLICT(user_id, date) DO UPDATE SET summary = excluded.summary, created_at = datetime('now')",
            (uid, ds, summary),
        )
    return {"summary": summary}


# ---------- 화면 파일 ----------
@app.get("/")
def index():
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/sw.js")
def service_worker():
    return FileResponse(WEB / "sw.js", media_type="application/javascript", headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=WEB), name="web")
