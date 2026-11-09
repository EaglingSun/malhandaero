"""녹음 글에서 화자 표기를 해석한다.

지원하는 꼴
  1) 한 줄 꼴     : "화자 1: 내용", "[참석자 2] 내용", "나 00:12: 내용"
  2) 머리줄 꼴    : "화자 1  00:12" 다음 줄부터 내용
화자가 2명 미만이면 화자 분리가 안 된 글로 본다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_TIME = r"(?:\(?\[?\d{1,2}:\d{2}(?::\d{2})?\]?\)?)"
_LABEL = r"(?:화자|참석자|발화자|발신자|수신자|상대방|상대|Speaker|SPEAKER|speaker)\s*[0-9A-Za-z가-힣]{0,6}|나|본인|[가-힣]{2,4}|[A-Za-z][A-Za-z ]{1,14}"

# "[화자 1] 내용" / "화자 1: 내용" / "화자 1 00:12: 내용"
_INLINE = re.compile(
    rf"^\s*\[?(?P<spk>{_LABEL})\]?\s*{_TIME}?\s*[:：\]]\s*(?P<body>\S.*)$"
)
# "화자 1  00:12" (내용 없음, 다음 줄부터 내용)
_HEADER = re.compile(rf"^\s*\[?(?P<spk>{_LABEL})\]?\s*{_TIME}\s*$")
# 시간만 있는 줄
_TIME_ONLY = re.compile(rf"^\s*{_TIME}\s*$")


@dataclass
class Turn:
    speaker: str
    text: str


def _clean(label: str) -> str:
    return re.sub(r"\s+", " ", label).strip()


def parse_turns(text: str) -> list[Turn]:
    """화자 표기가 있으면 발화 단위로 나눈다. 없으면 빈 목록."""
    turns: list[Turn] = []
    current: Turn | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or _TIME_ONLY.match(line):
            continue
        m = _HEADER.match(line)
        if m:
            current = Turn(_clean(m.group("spk")), "")
            turns.append(current)
            continue
        m = _INLINE.match(line)
        if m:
            current = Turn(_clean(m.group("spk")), m.group("body").strip())
            turns.append(current)
            continue
        if current is not None:
            current.text = (current.text + " " + line.strip()).strip()
    turns = [t for t in turns if t.text]
    return turns if len({t.speaker for t in turns}) >= 2 else []


def speakers(text: str) -> list[str]:
    """등장 순서대로 화자 이름. 화자 분리가 안 된 글이면 빈 목록."""
    seen: list[str] = []
    for t in parse_turns(text):
        if t.speaker not in seen:
            seen.append(t.speaker)
    return seen


def guess_me(names: list[str]) -> str | None:
    """'나', '본인'처럼 스스로를 가리키는 표기가 있으면 그것을 고른다."""
    for n in names:
        if n in ("나", "본인", "발신자"):
            return n
    return None


def chunks(text: str, size: int = 12000, overlap: int = 600) -> list[str]:
    """긴 글을 줄 경계에서 나눈다. 앞 조각 끝을 조금 겹쳐 문맥을 잇는다."""
    if len(text) <= size:
        return [text]
    out: list[str] = []
    lines = text.splitlines(keepends=True)
    buf = ""
    for line in lines:
        if len(line) > size:  # 줄바꿈 없는 긴 글: 먼저 쌓인 것을 내보내고 일정 길이로 자른다
            if buf.strip():
                out.append(buf)
            buf = ""
            step = size - overlap
            pieces = [line[i : i + size] for i in range(0, len(line), step)]
            out.extend(pieces[:-1])
            line = pieces[-1]
        if len(buf) + len(line) > size and buf:
            out.append(buf)
            buf = buf[-overlap:]
        buf += line
    if buf.strip():
        out.append(buf)
    return out
