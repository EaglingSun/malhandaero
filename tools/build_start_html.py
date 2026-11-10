"""docs/START.md → docs/START.html (그림을 안에 심은 파일 하나). 릴리스에 올리거나 메일로 보내도 캡처가 보인다.

실행: python tools/build_start_html.py   (pip install markdown 필요)
"""
import base64
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "START.md"
OUT = ROOT / "docs" / "START.html"

CSS = """
:root { --ink:#223244; --muted:#64788c; --line:#dce8f2; --mint:#12b58a; --mint-soft:#dff7ef; --sun:#ffe066; }
* { box-sizing:border-box } body { margin:0; background:linear-gradient(#eaf6ff,#fff 520px); color:var(--ink); font-family:"Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",sans-serif; font-size:17px; line-height:1.7; word-break:keep-all; }
main { max-width:860px; margin:0 auto; padding:40px 20px 60px; }
h1 { font-size:34px; margin:0 0 6px } h2 { font-size:24px; margin:44px 0 10px; padding-top:18px; border-top:1.5px solid var(--line) } h2:first-of-type { border:0; padding-top:0 }
p { margin:8px 0 } ol, ul { padding-left:24px } li { margin:6px 0 }
code { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:14.5px; background:#f1f6fa; padding:1px 6px; border-radius:6px }
table { border-collapse:collapse; width:100%; margin:12px 0; font-size:15.5px } th,td { border:1px solid var(--line); padding:8px 12px; text-align:left; vertical-align:top } th { background:#f4f8fb }
blockquote { margin:14px 0; padding:12px 16px; background:var(--mint-soft); border-radius:14px } blockquote p { margin:0 }
img { max-width:280px; width:100%; border:1.5px solid var(--line); border-radius:18px; display:block }
td img { max-width:260px }
strong { color:#0f8f6c }
hr { border:0; height:0; margin:0 }
.top { color:var(--muted); font-size:14px; margin-bottom:24px }
@media (max-width:600px) { main { padding:24px 14px 48px } h1 { font-size:28px } table { font-size:14px } }
"""


def embed_images(html: str) -> str:
    def rep(m):
        p = ROOT / "docs" / m.group(1)
        data = base64.b64encode(p.read_bytes()).decode()
        mime = "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/png"
        return f'src="data:{mime};base64,{data}"'
    return re.sub(r'src="(img/[^"]+)"', rep, html)


def main() -> None:
    body = markdown.markdown(SRC.read_text(encoding="utf-8"), extensions=["tables"])
    body = embed_images(body)
    OUT.write_text(
        "<!DOCTYPE html>\n<html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>말한대로 시작하기</title><style>{CSS}</style></head><body><main>"
        "<p class=\"top\">말한대로 · 시작 안내</p>"
        f"{body}</main></body></html>",
        encoding="utf-8",
    )
    print(f"{OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
