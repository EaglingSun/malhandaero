"""문서끼리, 문서와 코드가 어긋나지 않는지 본다. 기준은 docs/ARCHITECTURE.md 6절 「문서 지도」와 7절 「바꾸면 같이 고칠 곳」.

찾으려는 글귀를 못 찾아도 실패한다(조용히 넘어가지 않게). 고치는 법은 실패 글에 적는다.
"""
import importlib.util
import re
import sqlite3
from pathlib import Path
from urllib.parse import unquote

from server import db

ROOT = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


README = read("README.md")
CLAUDE = read("CLAUDE.md")
ARCH = read("docs/ARCHITECTURE.md")
DESIGN = read("docs/DESIGN.md")
START = read("docs/START.md")
POSTER = read("docs/POSTER.html")
STYLE = read("docs/STYLE.html")

# 지금 상태를 적는 문서들. docs/ARCHIVE.md는 옛 이름이 남는 지난 기록이라 뺀다.
CURRENT = {
    "docs/HANDOFF.md": read("docs/HANDOFF.md"),
    "README.md": README,
    "CLAUDE.md": CLAUDE,
    "docs/ARCHITECTURE.md": ARCH,
    "docs/DESIGN.md": DESIGN,
    "docs/START.md": START,
    "docs/MINUTES_FORMAT.md": read("docs/MINUTES_FORMAT.md"),
}

_spec = importlib.util.spec_from_file_location("build_start_html", ROOT / "tools" / "build_start_html.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)  # markdown이 없으면 여기서 멈춘다: pip install -r requirements-dev.txt


# ---- 문서에 적힌 경로가 실제로 있는가

PREFIXES = ("server/", "web/", "tools/", "tests/", "docs/", ".claude/", "evals/")
TOP_FILE = re.compile(r"^((setup|start|autostart)[\w-]*\.(bat|command)|(README|CLAUDE)\.md|requirements[\w-]*\.txt)$")


def paths_in(text: str) -> set[str]:
    found = set()
    # [글](경로) · [글](경로#제목) 링크. 바깥 주소와 문서 안 #링크는 뺀다
    links = [m.split("#")[0] for m in re.findall(r"\]\(([^)\s]+)\)", text) if "://" not in m and not m.startswith("#")]
    for span in re.findall(r"`([^`\n]+)`", text) + links:
        # 명령 안의 경로도 본다(`python tools/build_start_html.py`처럼 첫 낱말이 경로가 아닌 것)
        for part in span.replace("\\", "/").split():
            token = re.sub(r":\d+$", "", part).rstrip(".,")
            if any(c in token for c in "*{<…○"):
                continue
            if token.startswith(PREFIXES) or TOP_FILE.match(token):
                found.add(token)
    return found


def test_paths_in_docs_exist():
    total = 0
    missing = []
    for name, text in CURRENT.items():
        for p in sorted(paths_in(text)):
            total += 1
            if not (ROOT / p).exists():
                missing.append(f"{name}: {p}")
    assert total >= 30, f"문서에서 경로를 {total}개밖에 찾지 못했어요. 찾는 꼴이 바뀌었는지 보세요"
    assert not missing, "문서에 적힌 경로가 없어요(이름을 바꿨으면 문서도 고쳐요): " + ", ".join(missing)


# ---- 내려받기 주소의 버전과 파일 이름

def test_release_links_agree():
    pat = r"github\.com/EaglingSun/malhandaero/releases/download/(v[\d.]+)/([\w.-]+)"
    versions = set()
    for name, text in (("README.md", README), ("docs/POSTER.html", POSTER)):
        got = re.findall(pat, text)
        files = {fname for _, fname in got}
        assert files == {"setup-windows.bat", "setup-mac.command"}, \
            f"{name}: 설치 파일 주소가 Windows · Mac 하나씩이어야 해요. 지금 {sorted(files)}"
        for ver, fname in got:
            versions.add(ver)
            assert (ROOT / fname).exists(), f"{name}: 주소의 {fname} 파일이 저장소 최상위에 없어요"
    assert len(versions) == 1, f"README와 포스터의 릴리스 버전이 달라요: {versions}"


# ---- 5단계 이름과 순서 (기준: docs/START.md)

def test_five_steps_agree():
    heads = re.findall(r"^## [①-⑤] (.+?) — ", START, flags=re.M)
    rows = [re.sub(r" \(.*?\)", "", r) for r in re.findall(r"^\| [①-⑤] (.+?) \|", START, flags=re.M)]
    ol = re.search(r'<ol class="three five">(.*?)</ol>', POSTER, flags=re.S)
    assert ol, "포스터에서 5단계 목록을 찾지 못했어요"
    poster = re.findall(r"<strong>(.+?)</strong>", ol.group(1))
    assert len(heads) == 5, f"START.md의 ①~⑤ 제목을 찾지 못했어요: {heads}"
    assert rows == heads, f"START.md 맨 위 표 {rows} ≠ 제목 {heads}"
    assert poster == heads, f"포스터 {poster} ≠ START.md {heads}"
    # README는 단계 이름을 적지 않고 「5단계」라는 수만 적는다
    assert re.search(r"\[셋업 가이드\]\(docs/START\.md\)\*\* 5단계", README), "README에서 「셋업 가이드 5단계」 줄을 찾지 못했어요"


# ---- START.html은 START.md로 만든 것 (G-08)

def test_start_html_is_built_from_md():
    assert read("docs/START.html") == build.render(), (
        "docs/START.html이 START.md와 달라요. python tools/build_start_html.py 로 다시 만들어요. "
        f"START.md를 안 고쳤는데 실패하면 markdown 버전 차이일 수 있어요(지금 {build.markdown.__version__})"
    )


def test_start_anchors_resolve():
    ids = set(re.findall(r'<h\d id="([^"]+)"', build.render()))
    inner = re.findall(r"\]\(#([^)]+)\)", START)
    app = [unquote(a) for a in re.findall(r'href="/start#([^"]+)"', read("web/index.html"))]
    assert inner and app, "START.md 안의 #링크나 앱의 /start# 링크를 찾지 못했어요"
    broken = [a for a in inner + app if a not in ids]
    assert not broken, f"가리키는 제목이 없는 링크: {broken} (START.md 제목을 바꿨으면 링크도 고쳐요)"


# ---- 데이터 모델 (기준: server/db.py)

def test_data_model_matches_schema(tmp_path, monkeypatch):
    # SCHEMA만이 아니라 MIGRATIONS로 더한 칸까지 본다(G-02는 새 칸을 MIGRATIONS에만 적게 한다)
    monkeypatch.setenv("MALHAN_DATA", str(tmp_path))
    db.init()
    con = sqlite3.connect(tmp_path / "malhandaero.db")
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    real = {t: sorted(r[1] for r in con.execute(f"PRAGMA table_info({t})")) for t in tables}
    con.close()
    doc = {m.group(1): sorted(c.strip() for c in m.group(2).split(","))
           for m in re.finditer(r"^(\w+)\(([\w, ]+)\)$", ARCH, flags=re.M)}
    assert doc, "ARCHITECTURE.md 2절에서 표 정의를 찾지 못했어요"
    assert doc == real, (
        "ARCHITECTURE.md 2절 데이터 모델이 server/db.py와 달라요. "
        f"문서에만: { {t: sorted(set(c) - set(real.get(t, []))) for t, c in doc.items() if set(c) - set(real.get(t, []))} } "
        f"코드에만: { {t: sorted(set(c) - set(doc.get(t, []))) for t, c in real.items() if set(c) - set(doc.get(t, []))} }"
    )


# ---- 문서에 적힌 설정 이름이 코드에 있는가

def test_settings_in_docs_exist_in_code():
    src = "".join(p.read_text(encoding="utf-8") for d in ("server", "tools") for p in sorted((ROOT / d).glob("*.py")))
    code = set(re.findall(r"MALHAN_[A-Z0-9_]+", src))  # 낱말 단위로 비교한다(이름의 앞토막만 맞아도 통과하지 않게)
    names = set()
    for text in CURRENT.values():
        names |= set(re.findall(r"MALHAN_[A-Z0-9_]+", text))
    assert len(names) >= 8, f"문서에서 설정 이름을 {len(names)}개밖에 찾지 못했어요"
    gone = sorted(n for n in names if n not in code)
    assert not gone, f"문서에 있는데 코드에 없는 설정: {gone}"


# ---- 색 값 (기준: docs/STYLE.html)

def test_colors_agree():
    script = (ROOT / "tools" / "build_start_html.py").read_text(encoding="utf-8")
    for name in ("sky", "ink", "muted", "line", "mint", "mint-soft", "sun", "coral"):
        pat = rf"--{name}:\s*(#[0-9a-fA-F]{{3,6}})"
        base = re.search(pat, STYLE)
        assert base, f"STYLE.html에서 --{name} 색을 찾지 못했어요"
        # START.html을 만드는 스크립트는 --coral을 쓰지 않는다. 나머지 색은 세 곳 모두에 있어야 한다
        for where, text, must in (("POSTER.html", POSTER, True), ("build_start_html.py", script, name != "coral")):
            got = re.search(pat, text)
            assert got or not must, f"{where}에서 --{name} 색을 찾지 못했어요"
            if got:
                assert got.group(1).lower() == base.group(1).lower(), \
                    f"--{name}: STYLE.html {base.group(1)} ≠ {where} {got.group(1)}"
    loose = re.findall(r"background:[^;}]*#eaf6ff", script, flags=re.I)
    assert not loose, "build_start_html.py의 배경에 색 값을 직접 적지 말고 var(--sky)를 써요"


# ---- 문서 지도 · 결정 번호 · 규칙 번호

def test_every_doc_is_on_the_map():
    names = sorted(p.name for p in (ROOT / "docs").iterdir() if p.is_file() and p.suffix in (".md", ".html"))
    assert names, "docs/에서 문서를 찾지 못했어요"
    sec = re.search(r"^## 6\. 문서 지도\n(.*?)^## 7\. ", ARCH, flags=re.M | re.S)
    assert sec, "ARCHITECTURE.md에서 6절 「문서 지도」를 찾지 못했어요"
    off = [n for n in names if f"| `docs/{n}` |" not in sec.group(1)]
    assert not off, f"ARCHITECTURE.md 6절 「문서 지도」에 없는 문서: {off} (표에 한 줄 더하거나 기존 문서에 합쳐요)"


def test_decision_and_rule_numbers():
    lines = re.findall(r"^\|\s*D-.*$", ARCH, flags=re.M)  # 결정 표의 모든 줄을 먼저 모은다(꼴이 틀린 줄이 빠지지 않게)
    assert lines, "ARCHITECTURE.md 5절에서 결정 표를 찾지 못했어요"
    rows = []
    for line in lines:
        m = re.fullmatch(r"\| D-(\d\d) \|.*\| (.+?) \|", line)
        assert m, f"결정 줄의 꼴이 틀렸어요: {line[:60]}"
        rows.append(m.groups())
    assert [int(n) for n, _ in rows] == list(range(1, len(rows) + 1)), "결정 번호가 D-01부터 차례로 이어지지 않아요"
    bad = [f"D-{n}: {s}" for n, s in rows if not re.fullmatch(r"유효|바뀜 → D-\d\d", s)]
    assert not bad, f"결정의 상태는 「유효」나 「바뀜 → D-NN」으로 적어요: {bad}"
    ids = {n for n, _ in rows}
    for n, s in rows:
        m = re.fullmatch(r"바뀜 → D-(\d\d)", s)
        assert not m or (m.group(1) in ids and m.group(1) != n), f"D-{n}: 「{s}」가 가리키는 결정이 표에 없어요"
    rules = sorted(int(n) for n in re.findall(r"^- G-(\d\d) ", CLAUDE, flags=re.M))
    assert rules and rules == list(range(1, len(rules) + 1)), f"CLAUDE.md 규칙 번호가 겹치거나 비었어요: {rules}"
    # 다른 문서가 가리키는 G-NN이 CLAUDE.md에 있는가
    refs = {int(n) for text in (ARCH, CLAUDE, read(".claude/agents/reviewer.md")) for n in re.findall(r"G-(\d\d)", text)}
    assert refs - set(rules) == set(), f"없는 규칙을 가리켜요: {sorted(refs - set(rules))}"
