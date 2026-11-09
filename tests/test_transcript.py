from server import transcript


def test_inline_speakers():
    text = "화자 1: 금요일까지 보내 주실 수 있나요?\n화자 2: 네, 제가 금요일까지 보내겠습니다.\n화자 1: 감사합니다."
    assert transcript.speakers(text) == ["화자 1", "화자 2"]
    turns = transcript.parse_turns(text)
    assert len(turns) == 3 and turns[1].text.startswith("네, 제가")


def test_header_style_with_time():
    text = "참석자 1 00:03\n안녕하세요.\n회의 시작하겠습니다.\n\n참석자 2 00:10\n네, 자료는 제가 준비할게요."
    turns = transcript.parse_turns(text)
    assert [t.speaker for t in turns] == ["참석자 1", "참석자 2"]
    assert turns[0].text == "안녕하세요. 회의 시작하겠습니다."


def test_bracket_and_me_label():
    text = "[나] 토요일에 전화할게.\n[상대방] 응 알았어."
    assert transcript.speakers(text) == ["나", "상대방"]
    assert transcript.guess_me(["상대방", "나"]) == "나"


def test_plain_text_has_no_speakers():
    assert transcript.speakers("우유 사야 해. 그리고 내일까지 독후감 써야 돼.") == []
    assert transcript.speakers("메모: 우유 사기\n메모: 전화하기") == []  # 한 명뿐이면 화자 분리로 보지 않는다


def test_chunks_cover_everything():
    text = "\n".join(f"{i}번째 줄입니다." for i in range(3000))
    parts = transcript.chunks(text, size=2000, overlap=100)
    assert len(parts) > 1 and all(len(p) <= 2100 for p in parts)
    assert "0번째 줄" in parts[0] and "2999번째 줄" in parts[-1]
    long_line = "가" * 5000
    parts = transcript.chunks(long_line, size=2000, overlap=100)
    assert all(len(p) <= 2000 for p in parts) and sum(len(p) for p in parts) >= 5000
