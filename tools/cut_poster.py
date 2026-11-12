"""docs/POSTER.html을 게시판에 붙일 그림으로 잘라 docs/img/poster/에 둔다.

    python tools/cut_poster.py            # 폭 900px, 2배 선명도
    python tools/cut_poster.py --width 760

칸(section)마다 한 장, 맨 끝 footer는 마지막 칸에 붙인다. 게시판은 그림을 순서대로 붙이면 되므로 파일 이름 앞에 번호를 둔다.
playwright와 Chrome이 필요하다(tools/shoot_screens.py와 같다).
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
POSTER = ROOT / "docs" / "POSTER.html"
OUT = ROOT / "docs" / "img" / "poster"

NAMES = ["hero", "day", "features", "ways", "pc", "install", "tools", "close"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=900)
    ap.add_argument("--scale", type=int, default=2)
    a = ap.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright가 없어요: pip install playwright && playwright install chromium")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            print(f"브라우저를 켜지 못했어요: {e}\n  playwright install chromium 을 한 번 해 주세요.")
            return 1
        pg = b.new_page(viewport={"width": a.width, "height": 900}, device_scale_factor=a.scale)
        pg.goto(POSTER.resolve().as_uri())
        pg.wait_for_timeout(600)
        # 칸 사이 여백은 그림마다 반으로 나눠 넣는다 (붙였을 때 간격이 비슷하게)
        pg.add_style_tag(content=".wrap{gap:0} .wrap>section,.wrap>footer{padding:28px 0}")
        pg.wait_for_timeout(200)
        secs = pg.query_selector_all("main.wrap > section")
        if not secs:
            print("section을 찾지 못했어요. docs/POSTER.html의 <main class=\"wrap\"> 안에 <section>이 있는지 봐 주세요."); return 1
        n = 0

        def shot(name, y, h):
            nonlocal n
            n += 1
            f = OUT / f"{n:02d}-{name}.png"
            pg.screenshot(path=str(f), clip={"x": 0, "y": y, "width": a.width, "height": h}, full_page=True)
            print(f)

        pad = 14
        for i, sec in enumerate(secs):
            name = NAMES[i] if i < len(NAMES) else f"sec{i}"
            box = sec.bounding_box()
            gal = sec.query_selector(".gal")
            if gal:   # 기능 칸은 너무 길어서 제목 한 장 + 화면마다 한 장으로 나눈다
                gb = gal.bounding_box()
                shot(name, box["y"], gb["y"] - box["y"])
                for j, sh in enumerate(gal.query_selector_all(":scope > .shot")):
                    b2 = sh.bounding_box()
                    shot(f"{name}-{j+1}", b2["y"] - pad, b2["height"] + pad * 2)
                continue
            h = box["height"]
            if i == len(secs) - 1:   # 마지막 칸은 footer까지 한 장에
                fb = pg.query_selector("main.wrap > footer").bounding_box()
                h = fb["y"] + fb["height"] - box["y"]
            shot(name, box["y"], h)
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
