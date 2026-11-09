from datetime import date

from server import extract


def test_parse_candidates_tolerates_noise():
    raw = '여기 있어요:\n```json\n[{"text":"엄마한테 전화하기","due":"토요일","dueDate":"2026-11-14","scope":"개인","quote":"토요일에 엄마한테 전화할게."},{"text":""},"잡음",{"text":"검토 의견 보내기","dueDate":"금요일","scope":"회사"}]\n```'
    c = extract.parse_candidates(raw)
    assert [x.text for x in c] == ["엄마한테 전화하기", "검토 의견 보내기"]
    assert c[0].due_date == "2026-11-14" and c[1].due_date is None
    assert c[1].scope == "회사"


def test_parse_candidates_bad_json():
    assert extract.parse_candidates("죄송하지만 찾지 못했어요") == []
    assert extract.parse_candidates("[{broken") == []


def test_dedupe_against_known_and_self():
    cands = [extract.Candidate("엄마한테 전화하기"), extract.Candidate("엄마한테 전화 하기."), extract.Candidate("우유 사기")]
    kept = extract.dedupe(cands, known=["우유 사기"])
    assert [k.text for k in kept] == ["엄마한테 전화하기"]


def test_prompt_carries_context():
    ctx = extract.Context(today=date(2026, 11, 9), kind="call", me_speaker="화자 2", skipped=["점심 메뉴 정하기"], known=["우유 사기"])
    p = extract.build_prompt("화자 1: 안녕\n화자 2: 응", ctx)
    assert "2026-11-09 (월요일)" in p and '"화자 2"가 본인' in p
    assert "점심 메뉴 정하기" in p and "우유 사기" in p and "통화 녹음" in p
    assert "'- '로 시작" in p  # 요약은 목록으로


def test_parse_result_object_with_summary_owner_and_time():
    raw = '결과입니다 {"summary":"일정을 정했어요.","items":[{"text":"자료 보내기","owner":"unclear","who":"화자 2","time":"9:05","dueDate":"2026-11-14"},{"text":"예약하기","owner":"누군가","time":"오후 3시"}]} 끝'
    summary, c = extract.parse_result(raw)
    assert summary == "일정을 정했어요."
    assert (c[0].owner, c[0].who, c[0].time, c[0].due_date) == ("unclear", "화자 2", "09:05", "2026-11-14")
    assert (c[1].owner, c[1].time) == ("me", None)  # 모르는 값은 기본값으로
    assert extract.parse_result('[{"text":"옛 꼴"}]') == ("", [extract.Candidate("옛 꼴")])
