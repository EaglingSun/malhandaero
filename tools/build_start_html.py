"""docs/START.md → docs/START.html (그림을 안에 심은 파일 하나). 릴리스에 올리거나 메일로 보내도 캡처가 보인다.

실행: python tools/build_start_html.py   (markdown은 requirements-dev.txt에 있다)
색 값은 docs/STYLE.html의 :root가 기준이다. START.md를 고치고 다시 만들지 않으면 tests/test_docs_sync.py가 실패한다.
모양(카드 · 번호 · 버튼)은 여기서 입힌다. START.md에는 내용만 적는다.
"""
import base64
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "START.md"
OUT = ROOT / "docs" / "START.html"

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Jua&family=Gowun+Dodum&display=swap" rel="stylesheet">'
)

CSS = """
:root { --sky:#eaf6ff; --ink:#223244; --muted:#64788c; --line:#dce8f2; --mint:#12b58a; --mint-soft:#dff7ef; --sun:#ffe066;
  --font-display:"Jua","Gowun Dodum","Apple SD Gothic Neo","Malgun Gothic",sans-serif;
  --font-body:"Gowun Dodum","Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",sans-serif; }
* { box-sizing:border-box } body { margin:0; background:linear-gradient(var(--sky),#fff 520px); background-color:#fff; color:var(--ink); font-family:var(--font-body); font-size:17px; line-height:1.7; word-break:keep-all; overflow-wrap:anywhere; -webkit-font-smoothing:antialiased; }
main { max-width:980px; margin:0 auto; padding:36px 18px 64px; display:flex; flex-direction:column; gap:18px; }
.top { align-self:flex-start; margin:0; font-family:var(--font-display); font-size:16px; color:var(--mint); background:#fff; border:1.5px solid var(--mint); padding:3px 14px; border-radius:999px }
.intro h1 { font-family:var(--font-display); font-weight:400; font-size:40px; line-height:1.2; margin:0 0 10px }
.intro p { margin:4px 0; font-size:18px }
.intro td a { text-decoration:none }
.toc { display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin-top:12px }
.toc b { font-family:var(--font-display); font-weight:400; color:var(--muted); margin-right:2px }
.toc a { background:#fff; border:1.5px solid var(--line); border-radius:999px; padding:3px 13px; font-size:15px; font-weight:400; color:var(--ink); text-decoration:none }
.card, h1.more { scroll-margin-top:12px }
h1.more { font-family:var(--font-display); font-weight:400; font-size:28px; margin:22px 0 0 }
.card { background:#fff; border:1.5px solid var(--line); border-radius:22px; padding:22px 24px 20px; box-shadow:0 10px 30px rgba(60,120,170,.08) }
.card h2 { font-family:var(--font-display); font-weight:400; font-size:25px; line-height:1.3; margin:0 0 12px; display:flex; align-items:center; flex-wrap:wrap; gap:4px 10px }
.card h2 small { font-family:var(--font-body); font-size:15px; color:var(--muted) }
.card.sub h2 { font-size:21px }
.num { flex:none; width:36px; height:36px; border-radius:50%; background:var(--sun); display:inline-grid; place-items:center; font-size:20px }
p { margin:8px 0 } ul { padding-left:22px; margin:8px 0 } li { margin:7px 0 }
ol { list-style:none; counter-reset:step; padding-left:0; margin:10px 0 }
ol > li { counter-increment:step; position:relative; padding-left:36px }
ol > li::before { content:counter(step); position:absolute; left:0; top:2px; width:25px; height:25px; border-radius:50%; background:var(--mint-soft); color:#0f8f6c; font-family:var(--font-display); font-size:14px; display:grid; place-items:center }
li > ul { list-style:none; padding-left:0; margin:4px 0 2px }
li > ul > li { position:relative; padding-left:14px; margin:3px 0; color:#4a5d70; font-size:16px }
li > ul > li::before { content:"·"; position:absolute; left:2px; color:var(--mint); font-weight:700 }
li > ul > li.dl { padding-left:0 } li > ul > li.dl::before { content:none }
main > * { min-width:0; max-width:100% }
a { color:#0f8f6c; font-weight:700 }
a.btn { display:inline-block; margin:4px 0; background:var(--mint); color:#fff; font-family:var(--font-display); font-weight:400; font-size:18px; padding:10px 24px; border-radius:999px; text-decoration:none; box-shadow:0 8px 18px rgba(18,181,138,.28) }
code { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:14.5px; background:#f1f6fa; padding:1px 6px; border-radius:6px; color:var(--ink) }
table { border-collapse:collapse; width:100%; margin:12px 0; font-size:15.5px } th,td { border:1px solid var(--line); padding:8px 12px; text-align:left; vertical-align:top } th { background:#f4f8fb }
blockquote { margin:14px 0; padding:12px 16px; background:#fff8d9; border-left:5px solid var(--sun); border-radius:14px } blockquote p { margin:2px 0 }
p.ok { margin:14px 0 6px; padding:10px 14px; background:var(--mint-soft); border-radius:14px }
img { max-width:280px; width:100%; border:1.5px solid var(--line); border-radius:18px; display:block }
td img { max-width:260px }
strong { color:#0f8f6c }
@media (max-width:600px) { main { padding:24px 12px 48px } .intro h1 { font-size:30px } .card { padding:18px 16px 16px; border-radius:18px } .card h2 { font-size:22px } table { font-size:14px } th,td { padding:7px 8px } }
"""

STEPS = "①②③④⑤"


def embed_images(html: str) -> str:
    def rep(m):
        p = ROOT / "docs" / m.group(1)
        data = base64.b64encode(p.read_bytes()).decode()
        mime = "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/png"
        return f'src="data:{mime};base64,{data}"'
    return re.sub(r'src="(img/[^"]+)"', rep, html)


def slug(value: str, separator: str) -> str:
    """제목의 id를 GitHub와 같은 꼴로 만든다(START.md 안의 #링크와 앱의 /start#… 링크가 그대로 통하게)."""
    return re.sub(r"\s", separator, re.sub(r"[^\w\s-]", "", value).strip().lower())


def decorate(body: str) -> str:
    """제목마다 카드로 감싸고, 단계 번호 · 받기 버튼 · 확인 줄에 모양을 입힌다. 제목의 id는 그대로 둔다."""
    body = body.replace("<hr />", "")
    body = re.sub(r'<a (href="[^"]+")>([^<]*설치 파일 받기)</a>', r'<a class="btn" \1>\2</a>', body)
    body = body.replace('<li><strong><a class="btn"', '<li class="dl"><strong><a class="btn"')
    body = body.replace("<p><strong>됐는지 확인</strong>", '<p class="ok"><strong>됐는지 확인</strong>')
    # 목차: 맨 위 단계 표의 이름은 그 단계로, 「더 자세히」의 절은 표 아래 한 줄로
    step_ids = dict((sym, hid) for hid, sym in re.findall(rf'<h2 id="([^"]*)">([{STEPS}]) ', body))
    subs = re.findall(rf'<h2 id="([^"]*)">([^{STEPS}<][^<]*)</h2>', body)
    body = re.sub(
        rf"<td>([{STEPS}]) ([^<]*)</td>",
        lambda m: f'<td><a href="#{step_ids[m.group(1)]}">{m.group(1)} {m.group(2)}</a></td>',
        body,
    )
    linked = len(re.findall(r'<td><a href="#', body))
    if len(step_ids) != len(STEPS) or linked != len(STEPS) or not subs:
        # 조용히 목차가 빠진 채 만들어지지 않게 멈춘다
        raise ValueError(f"목차를 만들지 못했어요: 단계 제목 {len(step_ids)}개, 표의 단계 링크 {linked}개, 「더 자세히」 절 {len(subs)}개")
    toc = '<nav class="toc"><b>더 자세히</b>' + "".join(f'<a href="#{hid}">{title}</a>' for hid, title in subs) + "</nav>"
    out = []
    for part in re.split(r"(?=<h[12] )", body):
        part = part.strip()
        if not part:
            continue
        step = re.match(rf'(<h2 id="[^"]*">)([{STEPS}]) (.*?)</h2>', part)
        if step:
            title, _, note = step.group(3).partition(" — ")
            small = f" <small>{note}</small>" if note else ""
            head = f'{step.group(1)}<span class="num">{STEPS.index(step.group(2)) + 1}</span> {title}{small}</h2>'
            out.append(f'<section class="card step">{head}{part[step.end():]}</section>')
        elif part.startswith("<h2 "):
            out.append(f'<section class="card sub">{part}</section>')
        elif not out:
            out.append(f'<section class="intro">{part}{toc}</section>')
        else:
            out.append(re.sub(r'<h1 (id="[^"]*")>', r'<h1 \1 class="more">', part, count=1))
    return "\n".join(out)


def render() -> str:
    body = markdown.markdown(
        SRC.read_text(encoding="utf-8"),
        extensions=["tables", "toc"],
        extension_configs={"toc": {"slugify": slug}},
    )
    body = decorate(embed_images(body))
    return (
        "<!DOCTYPE html>\n<html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>말한대로 셋업 가이드</title>{FONTS}<style>{CSS}</style></head><body><main>"
        "<p class=\"top\">말한대로 · 시작 안내</p>"
        f"{body}</main></body></html>"
    )


def main() -> None:
    OUT.write_text(render(), encoding="utf-8", newline="\n")
    print(f"{OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
