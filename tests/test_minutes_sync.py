"""회의록 형식의 수치가 추출 지시문(server/extract.py)과 기준 문서(docs/MINUTES_FORMAT.md)에서 같은지 본다.

형식을 바꿀 때 한쪽만 고치면 여기서 실패한다. 글귀가 바뀌어 수치를 못 찾아도 실패한다(조용히 넘어가지 않게).
"""
import inspect
import re
from datetime import date
from pathlib import Path

import pytest

from server import extract

DOC = (Path(__file__).resolve().parent.parent / "docs" / "MINUTES_FORMAT.md").read_text(encoding="utf-8")
PROMPT = extract.build_prompt("화자 1: 안녕", extract.Context(today=date(2026, 11, 10), kind="meeting"))

# (이름, 지시문에서 찾는 꼴, 문서에서 찾는 꼴들)
PAIRS = [
    ("내 일 개수", r"많아도 (\d+)개를 넘기지", [r"회의당 \*\*(\d+)건 이하", r"내 일 ≤(\d+)개"]),
    ("주제당 요점 수", r"(\d+~\d+)개로 압축", [r"`points` (\d+~\d+)개", r"요점 (\d+~\d+)개"]),
    ("요점 한 줄 길이", r"한 줄 (\d+)자 안팎", [r"한 줄 (\d+)자 안팎"]),
    ("세부 한 줄 길이", r"각 (\d+)자 안팎", [r"각 (\d+)자 안팎"]),
    ("요약 줄 수", r"(\d+~\d+)개의 짧은 항목", [r"결정·중요 내용 (\d+~\d+)줄"]),
]


@pytest.mark.parametrize("name,in_prompt,in_doc", PAIRS, ids=[p[0] for p in PAIRS])
def test_prompt_and_doc_agree(name, in_prompt, in_doc):
    found = re.findall(in_prompt, PROMPT)
    assert found, f"{name}: 지시문에서 수치를 찾지 못했어요 ({in_prompt})"
    want = set(found)
    assert len(want) == 1, f"{name}: 지시문 안에서 값이 서로 달라요 {want}"
    for pat in in_doc:
        got = re.findall(pat, DOC)
        assert got, f"{name}: docs/MINUTES_FORMAT.md에서 수치를 찾지 못했어요 ({pat})"
        assert set(got) == want, f"{name}: 지시문 {want} ≠ 문서 {set(got)} ({pat})"


def test_chunk_size_agrees():
    # 환경 변수로 바뀐 값이 아니라 코드에 적힌 기본값을 본다
    src = re.search(r'"MALHAN_CHUNK", "(\d+)"', inspect.getsource(extract))
    doc = re.search(r"조각은 (\d+)만 자 단위", DOC)
    assert src and doc, "조각 크기를 코드나 문서에서 찾지 못했어요"
    assert int(src.group(1)) == int(doc.group(1)) * 10000
