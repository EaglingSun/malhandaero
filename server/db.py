"""SQLite 저장소. 표 정의와 연결만 둔다."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    token       TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS inputs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    kind          TEXT NOT NULL,              -- call | meeting | memo | file | photo
    title         TEXT NOT NULL DEFAULT '',
    source_name   TEXT NOT NULL DEFAULT '',
    received_date TEXT NOT NULL,              -- YYYY-MM-DD (사용자 기준 날짜)
    media_path    TEXT,
    transcript    TEXT NOT NULL DEFAULT '',
    speakers      TEXT NOT NULL DEFAULT '[]', -- JSON 배열
    me_speaker    TEXT,
    status        TEXT NOT NULL DEFAULT 'received',
    error         TEXT NOT NULL DEFAULT '',
    summary       TEXT NOT NULL DEFAULT '',   -- 회의·통화 요약
    minutes       TEXT NOT NULL DEFAULT '',   -- 회의록 JSON {topics, questions}
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    input_id    INTEGER REFERENCES inputs(id) ON DELETE SET NULL,
    text        TEXT NOT NULL,
    quote       TEXT NOT NULL DEFAULT '',
    due_text    TEXT NOT NULL DEFAULT '',
    due_date    TEXT,
    scope       TEXT NOT NULL DEFAULT '개인',   -- 개인 | 회사
    status      TEXT NOT NULL DEFAULT 'new',    -- new | todo | later | skipped | done | other(남의 일)
    plan_date   TEXT,
    plan_time   TEXT,                           -- HH:MM, 정했을 때만
    owner       TEXT NOT NULL DEFAULT 'me',     -- me | unclear | other
    who         TEXT NOT NULL DEFAULT '',       -- 남의 일이거나 불분명할 때 녹음에 나온 이름
    done_at     TEXT,
    addon       TEXT NOT NULL DEFAULT '',       -- 어느 더하기에서 왔는지 ('' = 본체)
    record_id   INTEGER,
    cal_ref     TEXT,
    details     TEXT NOT NULL DEFAULT '[]',   -- 상위 할 일 아래 묶인 세부 항목 JSON
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS day_logs (
    user_id     INTEGER NOT NULL REFERENCES users(id),
    date        TEXT NOT NULL,
    summary     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, date)
);
-- 바깥 캘린더 연결 (사람마다 하나)
CREATE TABLE IF NOT EXISTS calendar_links (
    user_id     INTEGER PRIMARY KEY REFERENCES users(id),
    provider    TEXT NOT NULL DEFAULT '',        -- naver | google
    mode        TEXT NOT NULL DEFAULT 'timed',   -- timed(시각을 정한 일만) | all(날짜가 정해진 모든 일)
    config      TEXT NOT NULL DEFAULT '{}',      -- 연결에 필요한 값 (이 PC에만 저장)
    status      TEXT NOT NULL DEFAULT '',        -- 마지막 실패 사유. 비어 있으면 정상
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
-- 더하기(애드온) 자리. 설계서 11장 참고. 아직 쓰는 코드는 없다.
CREATE TABLE IF NOT EXISTS addon_settings (
    user_id     INTEGER NOT NULL REFERENCES users(id),
    addon       TEXT NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 1,
    options     TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (user_id, addon)
);
CREATE TABLE IF NOT EXISTS records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    addon       TEXT NOT NULL,
    type        TEXT NOT NULL,
    input_id    INTEGER REFERENCES inputs(id) ON DELETE SET NULL,
    data        TEXT NOT NULL DEFAULT '{}',
    date        TEXT,
    status      TEXT NOT NULL DEFAULT 'open',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_items_user_status ON items(user_id, status);
CREATE INDEX IF NOT EXISTS idx_inputs_user_date ON inputs(user_id, received_date);
"""


def data_dir() -> Path:
    d = Path(os.environ.get("MALHAN_DATA", Path(__file__).resolve().parent.parent / "data"))
    d.mkdir(parents=True, exist_ok=True)
    (d / "audio").mkdir(exist_ok=True)
    return d


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(data_dir() / "malhandaero.db", timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


# 먼저 만들어진 DB에 나중에 생긴 칸을 더한다 (표, 칸, 정의)
MIGRATIONS = [
    ("inputs", "summary", "TEXT NOT NULL DEFAULT ''"),
    ("items", "plan_time", "TEXT"),
    ("items", "owner", "TEXT NOT NULL DEFAULT 'me'"),
    ("items", "who", "TEXT NOT NULL DEFAULT ''"),
    ("items", "addon", "TEXT NOT NULL DEFAULT ''"),
    ("items", "record_id", "INTEGER"),
    ("items", "cal_ref", "TEXT"),   # 바깥 캘린더에 넣은 일정의 주소나 번호
    ("inputs", "minutes", "TEXT NOT NULL DEFAULT ''"),
    ("items", "details", "TEXT NOT NULL DEFAULT '[]'"),
]


def init() -> None:
    con = connect()
    try:
        con.executescript(SCHEMA)
        for table, col, ddl in MIGRATIONS:
            have = {r["name"] for r in con.execute(f"PRAGMA table_info({table})")}
            if col not in have:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        con.commit()
    finally:
        con.close()


@contextmanager
def session():
    con = connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()
