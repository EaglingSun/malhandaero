"""녹음 글에서 '내가 챙길 일'을 뽑는다: 지시문 만들기, 응답 해석, 겹침 제거."""
from __future__ import annotations

import json
import os
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
    details: list[str] = field(default_factory=list)  # 상위 할 일 아래 묶인 세부 항목


@dataclass
class Context:
    today: date
    kind: str = "file"
    me_speaker: str | None = None
    skipped: list[str] = field(default_factory=list)  # 전에 '안 함'으로 넘긴 일
    known: list[str] = field(default_factory=list)    # 이미 열려 있는 일
    from_audio: bool = False                          # 음성 파일을 글로 바꾼 것: 화자 표기가 없다


def build_prompt(text: str, ctx: Context) -> str:
    wd = WEEKDAYS[ctx.today.weekday()]
    if ctx.kind == "memo":
        who = "- 모든 말이 본인의 말이므로 owner는 모두 \"me\"다."
    elif ctx.me_speaker:
        who = (f"- 화자 표기 중 \"{ctx.me_speaker}\"가 본인이다. 이 화자가 하겠다고 한 일과 이 화자가 부탁받아 맡은 일은 owner \"me\", "
               "다른 화자가 맡은 일은 owner \"other\", 누가 맡았는지 정해지지 않은 일은 owner \"unclear\"다.")
    elif ctx.from_audio:
        who = ("- 음성을 글로 바꾼 것이라 누가 말했는지 표시가 없고, 이 녹음을 넣은 사람이 본인이다. "
               "1인칭으로 하겠다고 다짐한 말('제가 ~할게요', '~해야겠다')만 owner \"me\"로 두고, "
               "'~해 주세요', '~해 줘'처럼 상대에게 부탁·지시한 일과 이름이 불린 사람의 일은 \"other\", 그 밖은 \"unclear\"로 한다.")
    else:
        who = ("- 누가 본인인지 모른다. 말한 사람이 스스로 하겠다고 한 일은 owner \"me\"로 두되, "
               "이름이 불린 다른 사람이 맡은 일은 \"other\", 누가 맡았는지 분명하지 않은 일은 \"unclear\"로 한다.")
    long_form = ctx.kind in ("meeting", "call", "file")  # 회의·통화: 회의록(minutes)까지 만든다
    parts = [
        "아래는 한 사람이 휴대폰으로 남긴 녹음이나 사진을 글로 바꾼 내용이다. " + KIND_NOTE.get(ctx.kind, KIND_NOTE["file"]),
        "만들 것: (1) summary 요약, (2) items 할 일 목록" + (", (3) minutes 회의록." if long_form else "."),
        "",
        "요약(summary) 규칙:",
        "- 결정된 것과 중요한 내용을 2~4개의 짧은 항목으로 쓴다. 항목마다 줄을 바꾸고 '- '로 시작하며, 한 항목은 한 문장(해요체)을 넘기지 않는다.",
        "- 녹음에 없는 내용을 보태지 않는다. 할 일로 뽑은 것은 요약에 다시 쓰지 않는다.",
        "- 내용이 아주 짧거나 할 일을 불러 준 메모뿐이면 빈 문자열로 둔다.",
        "",
        "할 일(items) 규칙:",
        "- 앞으로 누군가 해야 하는 일을 뽑는다. 이미 끝난 일, 단순한 감상이나 잡담은 뽑지 않는다.",
        who,
        "- 이름이나 화자 표기로 담당자가 불린 일은 반드시 owner \"other\"다. \"unclear\"는 담당자를 아무도 말하지 않은 일에만 쓴다.",
        "- 본인이 다른 사람에게 \"~해 주세요\", \"~해 줘\"라고 시킨 일은 owner \"other\"다.",
        "- who에는 owner가 other나 unclear일 때 녹음에 나온 담당자 이름이나 화자 표기를 적는다. 없으면 빈 문자열.",
        "- 묶어서 뽑는다: 같은 주제·같은 담당자의 잔일은 하나의 상위 할 일로 합치고, 잔일은 details 배열에 짧게 적는다(각 20자 안팎). "
        "상위 할 일 text는 결과가 무엇인지 알 수 있게 쓴다(예: 'LCT 테스트 계획을 개발팀과 확정하기').",
        "- owner가 me인 상위 할 일은 많아도 5개를 넘기지 않는다. 더 있으면 더 크게 묶는다. 작은 일이라도 빠뜨리지 말고 details에 넣거나, 할 일이 아니면 minutes에 남긴다.",
        "- 같은 일은 한 번만 뽑는다. 아래 '이미 적어 둔 일'과 겹치면 뽑지 않는다.",
        "- text는 무엇을 하는지 알 수 있는 한국어 한 줄, '~하기' 꼴로 쓴다. 대상과 내용을 빼먹지 않는다. 녹음에 없는 내용을 보태지 않는다.",
        "- due는 녹음에 나온 기한 표현 그대로(예: 금요일까지, 14일). 없으면 빈 문자열.",
        f"- dueDate는 기한을 YYYY-MM-DD로 바꾼 값. 오늘은 {ctx.today.isoformat()} ({wd}요일)이다. 지난 날짜가 되지 않게 가장 가까운 앞날로 잡는다. 알 수 없으면 null.",
        "- time은 녹음에 시각이 나왔을 때만 HH:MM(24시간). 없으면 null.",
        '- scope는 회사 일이면 "회사", 집안일·가족·개인 일이면 "개인".',
        "- quote는 근거가 된 원문 한 문장을 그대로 옮긴다.",
        "",
    ]
    if long_form:
        parts += [
            "회의록(minutes) 규칙 — 다른 사람에게 그대로 보낼 문서다. 녹취 요약이 아니라 회의록처럼 쓴다:",
            "- 한 줄 30자 안팎으로 짧게. '~라고 했어요', '~라고 봤어요' 같은 대화 중계는 쓰지 않고 내용 자체를 적는다(예: 'GTest 100% 호환 지원이 고객 요구예요').",
            "- 발언자는 의견이 갈렸을 때만 괄호로 붙인다(예: '전부 가져와야 가치 (지은) / 샘플만이면 충분 (개발팀)').",
            "- topics: 주제마다 하나, 회의 순서대로. topic은 짧은 제목. points는 배경·현황·쟁점을 3~5개로 압축(비슷한 말은 합친다). decisions는 그 주제에서 정해진 것.",
            "- attendees: 녹음에 나온 참석자 이름이나 화자 표기. next: 정해진 다음 일정(날짜·회의·기한). questions: 결론이 안 나 확인이 필요한 것.",
            "- 할 일로 뽑지 않은 작은 언급도 points나 questions에 남겨 빠지는 내용이 없게 한다. 녹음에 없는 내용은 쓰지 않는다. 짧은 메모·통화면 topics를 비워도 된다.",
            "",
        ]
    fmt_items = '"items":[{"text":"","owner":"me","who":"","due":"","dueDate":null,"time":null,"scope":"개인","quote":"","details":[]}]'
    fmt_minutes = ',"minutes":{"attendees":[],"topics":[{"topic":"","points":[],"decisions":[]}],"questions":[],"next":[]}' if long_form else ""
    parts += [
        "출력: JSON 객체 하나만. 다른 글은 쓰지 않는다.",
        '형식: {"summary":"",' + fmt_items + fmt_minutes + "}",
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


def _strs(v, limit: int = 300, n: int = 40) -> list[str]:
    return [str(x).strip()[:limit] for x in v if isinstance(x, (str, int, float)) and str(x).strip()][:n] if isinstance(v, list) else []


def parse_minutes(data) -> dict:
    """회의록 부분만 정리한다. 없거나 깨졌으면 빈 회의록."""
    m = data.get("minutes") if isinstance(data, dict) else None
    out: dict = {"attendees": [], "topics": [], "questions": [], "next": []}
    if not isinstance(m, dict):
        return out
    out["attendees"] = _strs(m.get("attendees"), limit=30, n=20)
    out["next"] = _strs(m.get("next"))
    for t in (m.get("topics") if isinstance(m.get("topics"), list) else [])[:30]:
        if not isinstance(t, dict):
            continue
        topic = str(t.get("topic") or "").strip()[:80]
        points, decisions = _strs(t.get("points")), _strs(t.get("decisions"))
        if topic or points or decisions:
            out["topics"].append({"topic": topic or "기타", "points": points, "decisions": decisions})
    out["questions"] = _strs(m.get("questions"))
    return out


def parse_result(raw: str) -> tuple[str, list[Candidate], dict]:
    """AI 응답 → (요약, 후보 목록, 회의록). 형식이 어긋난 원소는 버린다. 예전 꼴(배열만)도 받는다."""
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
                details=_strs(r.get("details"), limit=80, n=12),
            )
        )
    return summary, out, parse_minutes(data)


def parse_candidates(raw: str) -> list[Candidate]:
    return parse_result(raw)[1]


def merge_minutes(parts: list[dict]) -> dict:
    out: dict = {"attendees": [], "topics": [], "questions": [], "next": []}
    for m in parts:
        out["topics"] += m.get("topics", [])
        for k in ("attendees", "questions", "next"):
            out[k] += [q for q in m.get(k, []) if q not in out[k]]
    return out


def minutes_markdown(title: str, date_: str, summary: str, minutes: dict, items: list[dict]) -> str:
    """회의록 Markdown. 머리(일시·참석·안건) → 주제별 논의·결정 → 결정 모음 → 확인할 것 → 할 일 → 다음 일정."""
    topics = minutes.get("topics") or []
    L = [f"# {title or '회의'}", ""]
    head = [f"일시: {date_}"]
    if minutes.get("attendees"):
        head.append("참석: " + ", ".join(minutes["attendees"]))
    L += head + [""]
    if topics:
        L += ["안건: " + " · ".join(f"{i + 1}. {t.get('topic') or '기타'}" for i, t in enumerate(topics)), ""]
    if summary:
        L += ["## 요약"] + [("- " + x.lstrip("-•· ").strip()) for x in summary.splitlines() if x.strip()] + [""]
    for i, t in enumerate(topics):
        L.append(f"## {i + 1}. {t.get('topic') or '기타'}")
        L += [f"- {p}" for p in t.get("points", [])]
        L += [f"- **결정** {d}" for d in t.get("decisions", [])]
        L.append("")
    decisions = [d for t in topics for d in t.get("decisions", [])]
    if decisions:
        L += ["## 결정 사항"] + [f"- {d}" for d in decisions] + [""]
    if minutes.get("questions"):
        L += ["## 확인할 것"] + [f"- {q}" for q in minutes["questions"]] + [""]
    mine = [i for i in items if i.get("status") not in ("other", "skipped")]
    others = [i for i in items if i.get("status") == "other"]

    def line(i, who_default=""):
        who = i.get("who") or who_default
        tail = " · ".join(x for x in (who, i.get("due_text") or "") if x)
        return [f"- [ ] {i['text']}" + (f" ({tail})" if tail else "")] + [f"    - {d}" for d in (i.get("details") or [])]

    if mine or others:
        L += ["## 할 일"]
        for i in mine:
            L += line(i, "나")
        for i in others:
            L += line(i)
        L.append("")
    if minutes.get("next"):
        L += ["## 다음 일정"] + [f"- {n}" for n in minutes["next"]] + [""]
    return "\n".join(L).rstrip() + "\n"


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


CHUNK = int(os.environ.get("MALHAN_CHUNK", "60000"))  # 글자. 회의 1~2시간(3~5만 자)은 한 번에 읽는다


def extract(text: str, ctx: Context) -> tuple[str, list[Candidate], dict]:
    """글 → (요약, 후보 목록, 회의록). 아주 길면 나눠서 뽑고 합친 뒤 겹침을 없앤다."""
    found: list[Candidate] = []
    summaries: list[str] = []
    minutes: list[dict] = []
    for part in transcript.chunks(text.strip(), size=CHUNK, overlap=min(1500, CHUNK // 10)):
        if not part.strip():
            continue
        summary, cands, m = parse_result(llm.complete(build_prompt(part, ctx), max_tokens=6000))
        found += cands
        if summary:
            summaries.append(summary)
        if m["topics"] or m["questions"]:
            minutes.append(m)
    return "\n".join(summaries), dedupe(found, ctx.known), merge_minutes(minutes)


def summary_prompt(today: date, done: list[str], left: list[str], later: list[str], note: str = "") -> str:
    def lines(a: list[str]) -> str:
        return "\n".join(f"- {x}" for x in a) if a else "- 없음"

    parts = [
        "한 사람의 하루 할 일 기록이다. 하루를 마무리하는 짧은 정리를 한국어 존댓말(해요체)로 써라.",
        "규칙: 3~4문장. 목록에 있는 사실만 말한다. 평가하거나 훈계하지 않는다. 남은 일은 내일로 넘어간다고 알려 준다.",
        "내일 먼저 챙기면 좋은 일이 있으면 하나만 짚는다. 머리말, 제목, 목록 기호는 쓰지 않는다.",
    ]
    if note.strip():
        parts.append("'오늘 한 줄'은 본인이 그날에 대해 남긴 기분 표시(이모지)나 짧은 말이다. 그 기분과 내용을 한 문장으로 자연스럽게 녹이되, 적힌 그대로 쓰고 해석이나 조언을 보태지 않는다. 이모지는 글에 그대로 넣지 않는다.")
    parts += [
        "",
        f"날짜: {today.isoformat()} ({WEEKDAYS[today.weekday()]}요일)",
        "한 일:\n" + lines(done),
        "못 끝낸 일:\n" + lines(left),
        "나중으로 미뤄 둔 일:\n" + lines(later),
    ]
    if note.strip():
        parts.append("오늘 한 줄:\n" + note.strip())
    return "\n".join(parts)


def plain_summary(done: list[str], left: list[str]) -> str:
    s = f"한 일 {len(done)}건, 남은 일 {len(left)}건이에요."
    return s + (" 남은 일은 다음 날로 넘어가요." if left else "")
