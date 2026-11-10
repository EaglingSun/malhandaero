"""docs/POSTER.html 의 폰 화면 자리를 실제 캡처(docs/img/screens/*.png)로 채운다.

실행: python tools/shoot_screens.py && python tools/build_poster.py
그림은 파일 안에 base64 로 들어가 POSTER.html 하나만 올리면 된다. 녹음 앱 공유 시트(삼성 앱)는 우리 화면이 아니라
docs/img/screens/share.png 가 있을 때만 바꾸고, 없으면 그린 모형을 그대로 둔다.
"""
import base64
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTER = ROOT / "docs" / "POSTER.html"
SHOTS = ROOT / "docs" / "img" / "screens"

# 포스터 안 자리(aria-label 또는 바로 앞 h3 글귀) → 캡처 파일
SLOTS = [
    # (포스터 안 자리를 찾는 글귀, 캡처 파일, alt)
    ("구독 중인 Claude로, API 키 없이", "today.png", "오늘 화면: 캘린더 일정, 오늘 할 일, 끝낸 일"),   # 머리글 폰 (cta-note 바로 뒤)
    ("말하거나, 붙이거나, 찍거나", "add.png", "할 일 넣기 시트: 직접 적기와 말하기·글 붙여넣기·사진 찍기·파일 넣기"),
    ("회의록과 할 일을 추천해요", "minutes.png", "회의록 화면: 주제별 논의와 결정, 확인할 것, 맡긴 일"),
    ("오늘 일정이 할 일 위에", "calendar.png", "캘린더 일정 7건이 오늘 할 일 위에 보이는 화면"),
    ("「오늘은 여기까지」, 씨앗이 자라요", "month.png", "달력 화면: 날짜별 기분과 개수, 식물이 자라는 카드"),
]


def data_uri(p: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def block_end(s: str, start: int) -> int:
    """start 위치의 <div ...> 에 짝이 맞는 </div> 끝 위치."""
    depth, i = 0, start
    for m in re.finditer(r"<div\b|</div>", s[start:]):
        depth += 1 if m.group(0) == "<div" else -1
        if depth == 0:
            return start + m.end()
    raise ValueError("닫는 div를 찾지 못했어요")


def replace_after(s: str, anchor: str, img: str, cls: str, alt: str) -> str:
    i = s.index(anchor)
    j = s.index('<div class="ph"', i)
    k = block_end(s, j)
    tag = f'<img class="{cls}" src="{img}" alt="{alt}" width="300" loading="lazy">'
    return s[:j] + tag + s[k:]


def main() -> None:
    s = POSTER.read_text(encoding="utf-8")
    missing = [f for _, f, _ in SLOTS if not (SHOTS / f).exists()]
    if missing:
        raise SystemExit(f"캡처가 없어요: {missing} — 먼저 python tools/shoot_screens.py")
    # 이미 바꾼 포스터라면 img 를 다시 .ph 자리로 되돌리지 않고 src 만 갈아 끼운다
    for anchor, f, alt in SLOTS:
        uri = data_uri(SHOTS / f)
        i = s.index(anchor)
        nxt_img = s.find('<img class="shot-img', i)
        nxt_ph = s.find('<div class="ph"', i)
        if nxt_img != -1 and (nxt_ph == -1 or nxt_img < nxt_ph):
            s = s[:nxt_img] + re.sub(r'alt="[^"]*"', f'alt="{alt}"', re.sub(r'src="[^"]*"', f'src="{uri}"', s[nxt_img:], count=1), count=1)
        else:
            s = replace_after(s, anchor, uri, "shot-img", alt)
    if "shot-img {" not in s:
        s = s.replace("/* 화면 갤러리 */", ".shot-img { width: 100%; max-width: 300px; border-radius: 28px; border: 1.5px solid var(--line); box-shadow: 0 24px 60px rgba(60,120,170,.16); justify-self: center; display: block; }\n/* 화면 갤러리 */")
    POSTER.write_text(s, encoding="utf-8")
    print(f"{POSTER} ({POSTER.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
