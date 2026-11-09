"""녹음 글에서 '내가 챙길 일'을 뽑는다: 지시문 만들기, 응답 해석, 겹침 제거."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher

from . import llm, transcript

WEEKDAYS = "월화수목금토일"

KIND_NOTE = {
    "call": "통화 녹음이다. 두 사람이 말한다.",
    "meeting": "회의 녹음이다. 여러 사람이 말한다.",
    "memo": "본인이 혼자 할 일을 말로 불러 준 메모다. 모든 말이 본인의 말이다.",
    "file": "녹음을 글로 바꾼 파일이다.",
    "photo": "사진에서 읽어 낸 내용이다(안내문, 메모, 영수증, 화면 캡처 등). 이 내용을 보고 본인이 챙겨야 할 일을 뽑는다.",
}


@dataclass
class Candidate:
    text: str
    quote: str = ""
    due_text: str = ""
    due_date: str | None = None
    scope: str = "개인"
    owner: str = "me"   # me | unclear | other
    who: str = ""
    time: str | None = None  # HH:MM


@dataclass
class Context:
    today: date
    kind: str = "file"
    me_speaker: str | None = None
    skipped: list[str] = field(default_factory=list)  # 전에 '안 함'으로 넘긴 일
    known: list[str] = field(default_factory=list)    # 이미 열려 있는 일


def build_prompt(text: str, ctx: Context) -> str:
    wd = WEEKDAYS[ctx.today.weekday()]
    if ctx.kind == "memo":
        who = "- 모든 말이 본인의 말이므로 owner는 모두 \"me\"다."
    elif ctx.me_speaker:
        who = (f"- 화자 표기 중 \"{ctx.me_speaker}\"가 본인이다. 이 화자가 하겠다고 한 일과 이 화자가 부탁받아 맡은 일은 owner \"me\", "
               "다른 화자가 맡은 일은 owner \"other\", 누가 맡았는지 정해지지 않은 일은 owner \"unclear\"다.")
    else:
        who = ("- 누가 본인인지 모른다. 말한 사람이 스스로 하겠다고 한 일은 owner \"me\"로 두되, "
               "이름이 불린 다른 사람이 맡은 일은 \"other\", 누가 맡았는지 분명하지 않은 일은 \"unclear\"로 한다.")
    parts = [
        "아래는 한 사람이 휴대폰으로 남긴 녹음이나 사진을 글로 바꾼 내용이다. " + KIND_NOTE.get(ctx.kind, KIND_NOTE["file"]),
        "두 가지를 만들어라: (1) 내용 요약, (2) 앞으로 해야 할 일 목록.",
        "",
        "요약 규칙:",
        "- 결정된 것과 중요한 내용을 2~4개의 짧은 항목으로 쓴다. 항목마다 줄을 바꾸고 '- '로 시작하며, 한 항목은 한 문장(해요체)을 넘기지 않는다.",
        "- 녹음에 없는 내용을 보태지 않는다. 할 일로 뽑은 것은 요약에 다시 쓰지 않는다.",
        "- 내용이 아주 짧거나 할 일을 불러 준 메모뿐이면 빈 문자열로 둔다.",
        "",
        "할 일 규칙:",
        "- 앞으로 누군가 해야 하는 일을 모두 뽑는다. 이미 끝난 일, 단순한 감상이나 잡담은 뽑지 않는다.",
        who,
        "- who에는 owner가 other나 unclear일 때 녹음에 나온 담당자 이름이나 화자 표기를 적는다. 없으면 빈 문자열.",
        "- 같은 일은 한 번만 뽑는다. 아래 '이미 적어 둔 일'과 겹치면 뽑지 않는다.",
        "- text는 무엇을 하는지 알 수 있는 한국어 한 줄, '~하기' 꼴로 쓴다. 대상과 내용을 빼먹지 않는다. 녹음에 없는 내용을 보태지 않는다.",
        "- due는 녹음에 나온 기한 표현 그대로(예: 금요일까지, 14일). 없으면 빈 문자열.",
        f"- dueDate는 기한을 YYYY-MM-DD로 바꾼 값. 오늘은 {ctx.today.isoformat()} ({wd}요일)이다. 지난 날짜가 되지 않게 가장 가까운 앞날로 잡는다. 알 수 없으면 null.",
        "- time은 녹음에 시각이 나왔을 때만 HH:MM(24시간). 없으면 null.",
        '- scope는 회사 일이면 "회사", 집안일·가족·개인 일이면 "개인".',
        "- quote는 근거가 된 원문 한 문장을 그대로 옮긴다.",
        "",
        "출력: JSON 객체 하나만. 다른 글은 쓰지 않는다.",
        '형식: {"summary":"","items":[{"text":"","owner":"me","who":"","due":"","dueDate":null,"time":null,"scope":"개인","quote":""}]}',
        "",
    ]
    if ctx.skipped:
        parts += ["이 사람이 전에 '안 함'으로 넘긴 일(비슷한 종류는 뽑지 않는다):"]
        parts += [f"- {s}" for s in ctx.skipped[-10:]] + [""]
    if ctx.known:
        parts += ["이미 적어 둔 일:"] + [f"- {s}" for s in ctx.known[-40:]] + [""]
    parts += ["녹음 내용:", "<<<", text, ">>>"]
    return "\n".join(parts)


_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


_TIME = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


def _json_part(raw: str):
    """응답에서 JSON 객체나 배열을 찾아 읽는다. 앞뒤에 다른 글이 붙어 있어도 된다."""
    spans = []
    for open_, close in (("{", "}"), ("[", "]")):
        a, b = raw.find(open_), raw.rfind(close)
        if a != -1 and b > a:
            spans.append((a, b))
    for a, b in sorted(spans):  # 먼저 시작하는 쪽이 바깥
        try:
            return json.loads(raw[a : b + 1])
        except json.JSONDecodeError:
            continue
    return None


def parse_result(raw: str) -> tuple[str, list[Candidate]]:
    """AI 응답 → (요약, 후보 목록). 형식이 어긋난 원소는 버린다. 예전 꼴(배열만)도 받는다."""
    data = _json_part(raw)
    summary, arr = "", []
    if isinstance(data, dict):
        summary = str(data.get("summary") or "").strip()[:1500]
        arr = data.get("items") if isinstance(data.get("items"), list) else []
    elif isinstance(data, list):
        arr = data
    out: list[Candidate] = []
    for r in arr:
        if not isinstance(r, dict):
            continue
        text = str(r.get("text") or "").strip()
        if not text:
            continue
        dd, tm = r.get("dueDate"), r.get("time")
        out.append(
            Candidate(
                text=text[:200],
                quote=str(r.get("quote") or "")[:300],
                due_text=str(r.get("due") or "")[:40],
                due_date=dd if isinstance(dd, str) and _DATE.match(dd) else None,
                scope="회사" if r.get("scope") == "회사" else "개인",
                owner=r.get("owner") if r.get("owner") in ("me", "unclear", "other") else "me",
                who=str(r.get("who") or "")[:30],
                time=tm.zfill(5) if isinstance(tm, str) and _TIME.match(tm) else None,
            )
        )
    return summary, out


def parse_candidates(raw: str) -> list[Candidate]:
    return parse_result(raw)[1]


def _norm(s: str) -> str:
    return re.sub(r"[\s\W_]+", "", s).lower()


def is_same(a: str, b: str, threshold: float = 0.85) -> bool:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    return na == nb or SequenceMatcher(None, na, nb).ratio() >= threshold


def dedupe(cands: list[Candidate], known: list[str]) -> list[Candidate]:
    kept: list[Candidate] = []
    for c in cands:
        if any(is_same(c.text, k) for k in known):
            continue
        if any(is_same(c.text, k.text) for k in kept):
            continue
        kept.append(c)
    return kept


def extract(text: str, ctx: Context) -> tuple[str, list[Candidate]]:
    """글 → (요약, 후보 목록). 길면 나눠서 뽑고 합친 뒤 겹침을 없앤다."""
    found: list[Candidate] = []
    summaries: list[str] = []
    for part in transcript.chunks(text.strip()):
        if not part.strip():
            continue
        summary, cands = parse_result(llm.complete(build_prompt(part, ctx)))
        found += cands
        if summary:
            summaries.append(summary)
    return "\n".join(summaries), dedupe(found, ctx.known)


def summary_prompt(today: date, done: list[str], left: list[str], later: list[str]) -> str:
    def lines(a: list[str]) -> str:
        return "\n".join(f"- {x}" for x in a) if a else "- 없음"

    return "\n".join(
        [
            "한 사람의 하루 할 일 기록이다. 하루를 마무리하는 짧은 정리를 한국어 존댓말(해요체)로 써라.",
            "규칙: 3~4문장. 목록에 있는 사실만 말한다. 평가하거나 훈계하지 않는다. 남은 일은 내일로 넘어간다고 알려 준다.",
            "내일 먼저 챙기면 좋은 일이 있으면 하나만 짚는다. 머리말, 제목, 목록 기호는 쓰지 않는다.",
            "",
            f"날짜: {today.isoformat()} ({WEEKDAYS[today.weekday()]}요일)",
            "한 일:\n" + lines(done),
            "못 끝낸 일:\n" + lines(left),
            "나중으로 미뤄 둔 일:\n" + lines(later),
        ]
    )


def plain_summary(done: list[str], left: list[str]) -> str:
    s = f"한 일 {len(done)}건, 남은 일 {len(left)}건이에요."
    return s + (" 남은 일은 다음 날로 넘어가요." if left else "")
