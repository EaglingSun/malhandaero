"""docs/POSTER.html을 공모 게시글에 차례로 넣을 조각으로 잘라 docs/img/board/에 둔다.

    python tools/cut_board.py              # 폭 1100px, 조각 7장
    python tools/cut_board.py --out 폴더   # 다른 폴더에

조각: 1-top / 2a-windows · 2b-mac · 2c-guide · 2d-blank (설치 단추 줄) / 3-reader / 4-close
설치 단추 셋은 게시글에서 링크를 걸 수 있게 한 장씩 따로 자른다. 단추 자리는 화면에서 읽으므로
포스터 높이가 바뀌어도 맞는다. 맨 아래 응모작 표기 줄은 뺀다.
세 장으로 크게 자르는 것은 tools/cut_poster.py다. playwright와 Chrome이 필요하다(tools/shoot_screens.py와 같다).
"""
import argparse
import io
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
POSTER = ROOT / "docs" / "POSTER.html"
OUT = ROOT / "docs" / "img" / "board"
W = 1100
NAMES = ["1-top", "2a-windows", "2b-mac", "2c-guide", "2d-blank", "3-reader", "4-close"]

JS = """() => {
  const box = e => { const r = e.getBoundingClientRect(); return {l: r.left, t: r.top + scrollY, r: r.right, b: r.bottom + scrollY}; };
  const row = document.querySelector('#start .cta-row');
  return {
    btns: [...row.querySelectorAll('a.cta')].map(box),
    note: box(row.querySelector('.cta-note')),
    steps: box(document.querySelector('#start ol')),
    reader: box(document.querySelector('section.reader')),
    close: box(document.querySelector('section.close')),
    footer: box(document.querySelector('footer')),
    sw: document.documentElement.scrollWidth,
  };
}"""


def boxes_from(m: dict, height: int) -> list[tuple[int, int, int, int]]:
    """화면에서 읽은 자리(m)로 조각 7장의 (왼쪽, 위, 오른쪽, 아래)를 정한다."""
    btns = m["btns"]
    if len(btns) != 3:
        raise ValueError(f"설치 칸의 단추가 {len(btns)}개예요(3개여야 해요)")
    top_b = min(x["t"] for x in btns)
    bot_b = max(x["b"] for x in btns)
    if bot_b - top_b >= 90:
        raise ValueError("설치 단추 셋이 한 줄에 있지 않아요")
    note = m["note"]
    # 단추 줄 위: 5단계 카드와 단추 사이의 가운데. 아래: 단추와 그다음 것(안내 글 또는 다음 칸) 사이의 가운데
    row_top = round((m["steps"]["b"] + top_b) / 2)
    below = note["t"] if note["t"] >= bot_b else m["reader"]["t"]
    row_bottom = round((bot_b + below) / 2)
    x_mac = round((btns[0]["r"] + btns[1]["l"]) / 2)
    x_guide = round((btns[1]["r"] + btns[2]["l"]) / 2)
    x_blank = round(btns[2]["r"] + (btns[1]["l"] - btns[0]["r"]) / 2)
    reader_bottom = round((m["reader"]["b"] + m["close"]["t"]) / 2)
    end = round((m["close"]["b"] + m["footer"]["t"]) / 2)
    if not (0 < row_top < row_bottom < reader_bottom < end <= height and 0 < x_mac < x_guide < x_blank < W):
        raise ValueError("조각 자리가 순서대로가 아니에요. 포스터 구성이 바뀌었는지 보세요")
    boxes = [
        (0, 0, W, row_top),
        (0, row_top, x_mac, row_bottom),
        (x_mac, row_top, x_guide, row_bottom),
        (x_guide, row_top, x_blank, row_bottom),
        (x_blank, row_top, W, row_bottom),
        (0, row_bottom, W, reader_bottom),
        (0, reader_bottom, W, end),
    ]
    area = sum((r - l) * (b - t) for l, t, r, b in boxes)
    if area != W * end:
        raise ValueError(f"조각 넓이 합 {area}이 자른 범위 {W * end}와 달라요")
    return boxes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, default=OUT)
    a = ap.parse_args()
    try:
        from PIL import Image
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        print(f"필요한 것이 없어요({e.name}): pip install playwright pillow && playwright install chromium")
        return 1
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            print(f"브라우저를 켜지 못했어요: {e}\n  playwright install chromium 을 한 번 해 주세요.")
            return 1
        pg = b.new_page(viewport={"width": W, "height": 900}, device_scale_factor=1)
        pg.goto(POSTER.as_uri())
        pg.wait_for_timeout(1200)
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        try:
            m = pg.evaluate(JS)
        except Exception as e:
            b.close()
            print(f"못 했어요: 포스터에서 설치 칸 · 도구 칸 · 마무리 칸 중 찾지 못한 것이 있어요({str(e).splitlines()[0]})")
            return 1
        shot = pg.screenshot(full_page=True)
        b.close()
    im = Image.open(io.BytesIO(shot)).convert("RGB")
    if im.size[0] != W or m["sw"] != W:
        print(f"못 했어요: 화면 폭이 {W}이 아니에요(그림 {im.size[0]}, 화면 {m['sw']})")
        return 1
    try:
        boxes = boxes_from(m, im.size[1])
    except ValueError as e:
        print(f"못 했어요: {e}")
        return 1
    if m["note"]["t"] < max(x["b"] for x in m["btns"]):
        print("알림: 단추 옆 안내 글이 같은 줄에 있어요. 2d 조각에 글이 들어가요")
    a.out.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        (a.out / f"{name}.png").unlink(missing_ok=True)
    for name, box in zip(NAMES, boxes):
        f = a.out / f"{name}.png"
        im.crop(box).save(f, optimize=True)
        print(f"{f}  {box[2] - box[0]}x{box[3] - box[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
