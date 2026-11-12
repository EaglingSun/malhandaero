"""tools/cut_board.py: 화면에서 읽은 자리로 게시글 조각 7장의 경계를 정하는 계산."""
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("cut_board", ROOT / "tools" / "cut_board.py")
cut_board = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cut_board)


def box(l, t, r, b):
    return {"l": l, "t": t, "r": r, "b": b}


def layout(**over):
    m = {
        "btns": [box(20, 4530, 259, 4582), box(279, 4530, 449, 4582), box(469, 4530, 700, 4582)],
        "note": box(20, 4596, 600, 4620),
        "steps": box(20, 4300, 1080, 4506),
        "reader": box(20, 4684, 1080, 5100),
        "close": box(20, 5164, 1080, 5340),
        "footer": box(20, 5404, 1080, 5430),
        "sw": 1100,
    }
    m.update(over)
    return m


def test_boxes_cover_range_without_gap_or_overlap():
    boxes = cut_board.boxes_from(layout(), 5448)
    assert len(boxes) == len(cut_board.NAMES) == 7
    top, win, mac, guide, blank, reader, close = boxes
    assert top == (0, 0, 1100, 4518)  # 5단계 카드 아래와 단추 위의 가운데
    # 단추 줄 네 조각은 높이가 같고 가로로 이어진다
    assert {b[1] for b in (win, mac, guide, blank)} == {4518}
    assert {b[3] for b in (win, mac, guide, blank)} == {4589}  # 단추 아래와 안내 글 위의 가운데
    assert (win[0], win[2], mac[2], guide[2], blank[2]) == (0, 269, 459, 710, 1100)
    assert reader[1] == 4589 and close[1] == reader[3] == 5132
    assert close[3] == 5372  # 마무리 상자와 응모작 표기 줄 사이. 표기 줄은 빠진다


def test_each_button_sits_inside_its_own_piece():
    m = layout()
    boxes = cut_board.boxes_from(m, 5448)
    for btn, piece in zip(m["btns"], boxes[1:4]):
        assert piece[0] <= btn["l"] and btn["r"] <= piece[2]
        assert piece[1] <= btn["t"] and btn["b"] <= piece[3]


def test_wrapped_buttons_are_refused():
    m = layout()
    m["btns"][2] = box(20, 4600, 251, 4652)  # 셋째 단추가 다음 줄로 내려감
    with pytest.raises(ValueError, match="한 줄"):
        cut_board.boxes_from(m, 5448)


@pytest.mark.parametrize("count", [2, 4])
def test_wrong_button_count_is_refused(count):
    m = layout()
    m["btns"] = (m["btns"] + [box(720, 4530, 900, 4582)])[:count]
    with pytest.raises(ValueError, match="3개"):
        cut_board.boxes_from(m, 5448)


def test_note_beside_buttons_cuts_row_below_at_next_section():
    # 안내 글이 단추와 같은 줄이면 그 아래 경계는 단추와 다음 칸 사이의 가운데
    boxes = cut_board.boxes_from(layout(note=box(720, 4540, 1080, 4570)), 5448)
    assert {b[3] for b in boxes[1:5]} == {4633}
    assert boxes[5][1] == 4633


def test_range_past_image_bottom_is_refused():
    # 읽은 자리가 찍은 그림보다 아래면(그림이 덜 찍혔으면) 자르지 않는다
    with pytest.raises(ValueError, match="순서"):
        cut_board.boxes_from(layout(), 5000)
