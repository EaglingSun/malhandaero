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
    summary, c, minutes = extract.parse_result(raw)
    assert summary == "일정을 정했어요."
    assert (c[0].owner, c[0].who, c[0].time, c[0].due_date) == ("unclear", "화자 2", "09:05", "2026-11-14")
    assert (c[1].owner, c[1].time) == ("me", None)  # 모르는 값은 기본값으로
    empty = {"attendees": [], "topics": [], "questions": [], "next": []}
    assert minutes == empty
    assert extract.parse_result('[{"text":"옛 꼴"}]') == ("", [extract.Candidate("옛 꼴")], empty)


def test_parse_minutes_and_details_then_markdown():
    raw = ('{"summary":"- 일정 확정","items":[{"text":"LCT 테스트 계획 확정하기","owner":"me","details":["요구사항 받기","기한 정하기", 3]},'
           '{"text":"리스트 받아 오기","owner":"other","who":"승렬"}],'
           '"minutes":{"attendees":["김선숙","박승렬"],"topics":[{"topic":"RT 일정","points":["다음 주 월요일 시작"],"decisions":["CT 30% 비중"]},{"topic":"","points":[],"decisions":[]},"잡음"],'
           '"questions":["GTest 범위는 어디까지?"],"next":["11/16 RT 시작"]}}')
    summary, c, m = extract.parse_result(raw)
    assert c[0].details == ["요구사항 받기", "기한 정하기", "3"] and c[1].details == []
    assert [t["topic"] for t in m["topics"]] == ["RT 일정"] and m["questions"] == ["GTest 범위는 어디까지?"]
    md = extract.minutes_markdown("주간 회의", "2026-11-10", summary, m,
                                  [{"text": c[0].text, "status": "new", "details": c[0].details, "who": "", "due_text": "내일"},
                                   {"text": c[1].text, "status": "other", "details": [], "who": "승렬", "due_text": ""}])
    assert md.startswith("# 주간 회의\n\n일시: 2026-11-10\n참석: 김선숙, 박승렬\n\n안건: 1. RT 일정\n")
    assert "## 1. RT 일정\n- 다음 주 월요일 시작\n- **결정** CT 30% 비중" in md and "## 결정 사항\n- CT 30% 비중" in md
    assert "## 할 일\n- [ ] LCT 테스트 계획 확정하기 (나 · 내일)\n    - 요구사항 받기\n" in md and "\n- [ ] 리스트 받아 오기 (승렬)\n" in md and "## 다음 일정\n- 11/16 RT 시작" in md


def test_meeting_prompt_asks_for_grouping_and_minutes():
    ctx = extract.Context(today=date(2026, 11, 10), kind="meeting", me_speaker="화자 1")
    p = extract.build_prompt("화자 1: 네\n화자 2: 네", ctx)
    assert "5개를 넘기지 않는다" in p and "details" in p and '"minutes"' in p and '반드시 owner "other"' in p and "대화 중계는 쓰지 않고" in p
    assert '"minutes"' not in extract.build_prompt("우유 사기", extract.Context(today=date(2026, 11, 10), kind="memo"))


def test_audio_prompt_explains_missing_speakers():
    p = extract.build_prompt("제가 금요일까지 보낼게요. 자료는 보내 주세요.", extract.Context(today=date(2026, 11, 10), kind="call", from_audio=True))
    assert "누가 말했는지 표시가 없고" in p and "1인칭" in p


def test_summary_prompt_carries_note_only_when_given():
    base = extract.summary_prompt(date(2026, 11, 10), ["a"], [], [])
    assert "오늘 한 줄" not in base
    with_note = extract.summary_prompt(date(2026, 11, 10), ["a"], [], [], "비가 왔다")
    assert "오늘 한 줄:\n비가 왔다" in with_note and "해석이나 조언을 보태지 않는다" in with_note
