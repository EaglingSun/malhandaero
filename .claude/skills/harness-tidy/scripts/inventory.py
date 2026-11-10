#!/usr/bin/env python3
"""harness-tidy inventory — 하네스 목록(L0)과 대상 주변 후보(L1)를 스크립트로 뽑는다.

LLM 이 본문을 읽지 않고 파일 메타데이터만 본다. 표준 라이브러리만 쓴다.

사용:
  python inventory.py                          # L0: 프로젝트 하네스 목록
  python inventory.py --include-user           # ~/.claude 까지 포함
  python inventory.py --changed-since main     # main 이후 바뀐 파일만 (증분)
  python inventory.py --near .claude/skills/deck-script/SKILL.md   # L1: 대상 주변 후보
  python inventory.py --out docs/reports/2026-11-03-harness-tidy/inventory.md
  python inventory.py --json                   # 기계 처리용
"""
import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

LIMITS = {"skill": 40, "command": 40, "agent": 40, "prompt": 40, "claude-md": 50, "rule": 30}
VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".claude/worktrees"}
ID_RE = re.compile(r"^\s*-\s*([A-Z]{1,6})-(\d{2,3})\b", re.M)
REF_RE = re.compile(r"(?<![\w`])@([~\w./\\-]+\.\w+)")
QUOTE_RE = re.compile(r"[「“\"]([^」”\"\n]{2,30})[」”\"]")
PATHLIKE_RE = re.compile(r"[\w.\-*]+/[\w.\-*/]+|[\w\-]+\.(?:js|ts|py|md|json|ps1|docx|pptx)\b")
ID_CELL_RE = re.compile(r"^[A-Z]{1,6}-\d{2,3}(\s*[,·]\s*[A-Z]{1,6}-\d{2,3})*$")
CHANGE_KINDS = ("유지", "수정", "묶음", "이동", "뺄")


def read(p):
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="utf-8", errors="replace")


def split_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    fm_raw, body = text[3:end], text[end + 4:]
    fm, key = {}, None
    for line in fm_raw.splitlines():
        if re.match(r"^\s+-\s+", line) and key:
            fm.setdefault(key, [])
            if isinstance(fm[key], list):
                fm[key].append(line.strip()[2:].strip().strip("'\""))
            continue
        m = re.match(r"^([\w-]+)\s*:\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip().strip("'\"")
            fm[key] = val if val else []
    return fm, body.lstrip("\n")


def strip_code(text):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def walk(base, pattern):
    if not base.exists():
        return []
    out = []
    for p in base.glob(pattern):
        rel = p.relative_to(base).as_posix()
        if any(f"/{d}/" in f"/{rel}/" for d in SKIP_DIRS):
            continue
        if p.is_file():
            out.append(p)
    return sorted(out)


def discover(root, include_user, memory, extra=()):
    found = []  # (kind, scope, path)
    def add(kind, scope, paths):
        found.extend((kind, scope, p) for p in paths)

    for name in ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md"):
        add("claude-md", "project", walk(root, f"**/{name}"))
    add("claude-md", "project", walk(root / ".claude", "CLAUDE.md"))
    add("rule", "project", walk(root / ".claude/rules", "**/*.md"))
    add("skill", "project", walk(root / ".claude/skills", "*/SKILL.md"))
    add("command", "project", walk(root / ".claude/commands", "**/*.md"))
    add("agent", "project", walk(root / ".claude/agents", "**/*.md"))
    add("style", "project", walk(root / ".claude/output-styles", "**/*.md"))
    if include_user:
        home = Path.home() / ".claude"
        add("claude-md", "user", walk(home, "CLAUDE.md"))
        add("rule", "user", walk(home / "rules", "**/*.md"))
        add("skill", "user", walk(home / "skills", "*/SKILL.md"))
        add("command", "user", walk(home / "commands", "**/*.md"))
        add("agent", "user", walk(home / "agents", "**/*.md"))
        add("style", "user", walk(home / "output-styles", "**/*.md"))
    for pat in extra or ():
        add("prompt", "project", [p for p in walk(root, pat) if p.suffix == ".md"])
    if memory:
        mp = Path(memory).expanduser()
        if mp.exists():
            add("memory", "user", [mp])
    seen, uniq = set(), []
    for k, s, p in found:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            uniq.append((k, s, p))
    return uniq


def settings_summary(root, include_user):
    files = [root / ".claude/settings.json", root / ".claude/settings.local.json"]
    if include_user:
        files.append(Path.home() / ".claude/settings.json")
    rows = []
    for f in files:
        if not f.exists():
            continue
        try:
            data = json.loads(read(f))
        except json.JSONDecodeError as e:
            rows.append({"path": str(f), "error": f"JSON 오류: {e}"})
            continue
        hooks = data.get("hooks", {}) or {}
        n_hooks = sum(len(h.get("hooks", [])) for evs in hooks.values() for h in (evs or []))
        perm = data.get("permissions", {}) or {}
        rows.append({
            "path": str(f),
            "hooks": {ev: len(v or []) for ev, v in hooks.items()},
            "hook_commands": n_hooks,
            "allow": len(perm.get("allow", []) or []),
            "deny": len(perm.get("deny", []) or []),
            "outputStyle": data.get("outputStyle", ""),
            "agent": data.get("agent", ""),
        })
    mcp = root / ".mcp.json"
    if mcp.exists():
        try:
            servers = list((json.loads(read(mcp)).get("mcpServers") or {}).keys())
        except json.JSONDecodeError:
            servers = ["(JSON 오류)"]
        rows.append({"path": str(mcp), "mcp_servers": servers})
    return rows


def analyze(kind, scope, path, root):
    text = read(path)
    fm, body = split_frontmatter(text)
    lines = text.splitlines()
    body_lines = body.splitlines()
    nonempty = [l for l in body_lines if l.strip()]
    long_lines = [l for l in nonempty if len(l) > 100 and not l.lstrip().startswith(("|", "```"))]
    ids = ID_RE.findall(body)
    refs = []
    for ref in REF_RE.findall(strip_code(body)):
        target = (path.parent / ref).expanduser() if not ref.startswith("~") else Path(ref).expanduser()
        if not target.exists() and not (root / ref).exists():
            refs.append(ref)
    flags = []
    limit = LIMITS.get(kind)
    if limit and len(body_lines) > limit:
        flags.append(f"줄 초과({len(body_lines)}>{limit})")
    if kind == "agent" and not fm.get("tools"):
        flags.append("tools 생략=전부 상속")
    if kind == "command":
        flags.append("skill 이전 후보")
    if kind in ("skill", "agent") and not fm.get("description"):
        flags.append("description 없음")
    if refs:
        flags.append("끊긴 @참조: " + ", ".join(refs[:3]))
    if kind == "memory" and (len(lines) > 200 or len(text.encode("utf-8")) > 25_000):
        flags.append("MEMORY 한도 근접/초과")
    name = fm.get("name") or (path.parent.name if kind == "skill" else path.stem)
    try:
        shown = path.relative_to(root).as_posix()
    except ValueError:
        shown = str(path).replace(str(Path.home()), "~")
    return {
        "kind": kind, "scope": scope, "path": shown, "abs": str(path.resolve()), "name": name,
        "lines": len(lines), "body_lines": len(body_lines),
        "desc_chars": len(fm.get("description", "")) if isinstance(fm.get("description"), str) else 0,
        "paths": fm.get("paths") if isinstance(fm.get("paths"), list) else ([fm["paths"]] if fm.get("paths") else []),
        "tools": fm.get("tools", ""), "skills": fm.get("skills") if isinstance(fm.get("skills"), list) else [],
        "ids": len(ids), "id_prefixes": sorted({p for p, _ in ids}),
        "prose": round(len(long_lines) / len(nonempty), 2) if nonempty else 0.0,
        "flags": flags,
    }


def name_conflicts(rows):
    by = {}
    for r in rows:
        if r["kind"] in ("skill", "command", "agent"):
            by.setdefault((r["kind"] if r["kind"] == "agent" else "skill", r["name"]), []).append(r["path"])
    return {f"{k[0]}:{k[1]}": v for k, v in by.items() if len(v) > 1}


def changed_files(root, ref):
    def run(args):
        try:
            return subprocess.run(args, cwd=root, capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
        except FileNotFoundError:
            return []
    names = set(run(["git", "diff", "--name-only", f"{ref}...HEAD"]))
    names |= set(run(["git", "diff", "--name-only"]))
    names |= set(run(["git", "ls-files", "--others", "--exclude-standard"]))
    return {(root / n).resolve() for n in names if n}


def near(target, rows, root):
    tpath = (root / target) if not Path(target).is_absolute() else Path(target)
    text = read(tpath)
    _, body = split_frontmatter(text)
    terms = {t.strip() for t in QUOTE_RE.findall(body) if len(t.strip()) >= 2}
    pathlike = set(PATHLIKE_RE.findall(body))
    stem = tpath.parent.name if tpath.name == "SKILL.md" else tpath.stem
    tabs = str(tpath.resolve())
    hits = []
    for r in rows:
        if r["abs"] == tabs:
            continue
        other = read(Path(r["abs"]))
        matched = sorted(t for t in terms if t in other)
        mentions = stem in other
        glob_hit = [g for g in r["paths"] for p in pathlike if fnmatch.fnmatch(p, g) or fnmatch.fnmatch(p, g.rstrip("/*") + "/*")]
        if matched or mentions or glob_hit:
            lines = []
            for i, line in enumerate(other.splitlines(), 1):
                if any(t in line for t in matched[:10]):
                    lines.append(i)
            hits.append({
                "path": r["path"], "kind": r["kind"],
                "shared_terms": len(matched), "examples": matched[:5], "lines": lines[:10],
                "mentions_target": mentions, "paths_overlap": sorted(set(glob_hit))[:3],
            })
    hits.sort(key=lambda h: (-(h["shared_terms"] + 5 * bool(h["paths_overlap"])), h["path"]))
    return {"target": target, "terms": len(terms), "candidates": hits}


def coverage(evals_dir):
    """mapping.md 행 대비 evals.json 케이스 커버리지 (HT-10 · HT-18).
    rc.2 형식: 'Eval 케이스' 칸의 id 를 evals.json id 와 대조.
    rc.1 이전 형식(칸 없음): 행의 새 ID 가 evals.json expected_output 의 [ID] 에 있는지로 대조."""
    d = Path(evals_dir)
    mp, ep = d / "mapping.md", d / "evals.json"
    if not mp.exists():
        return {"error": f"{mp} 없음"}
    cases = {}
    if ep.exists():
        try:
            for e in json.loads(read(ep)).get("evals", []):
                cases[str(e.get("id"))] = e.get("expected_output", "")
        except json.JSONDecodeError as e:
            return {"error": f"evals.json JSON 오류: {e}"}
    tagged = set(re.findall(r"\[([A-Z]{1,6}-\d{2,3}|M\d{2,3})\]", " ".join(cases.values())))
    header, rows = None, []
    for line in read(mp).splitlines():
        if not line.strip().startswith("|"):
            if header is not None:
                break  # 첫 표만 매핑표다 (뒤따르는 표는 다른 기록)
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        rows.append(dict(zip(header, cells)))
    col = next((h for h in (header or []) if "Eval" in h), None)
    idcol = next((h for h in (header or []) if "새 ID" in h), None)
    rowcol = next((h for h in (header or []) if h == "행"), None)
    kindcol = next((h for h in (header or []) if "변경 유형" in h), None)
    result = {"mapping_rows": len(rows), "covered": 0, "excused": 0, "missing": [], "broken_ids": [],
              "no_id": [], "bad_kind": [], "mode": "rc.2" if col else "rc.1-fallback"}
    for r in rows:
        label = r.get(rowcol) or r.get(idcol) or "?"
        kind = r.get(kindcol, "")
        rid = r.get(idcol, "") if idcol else ""
        if idcol and not (ID_CELL_RE.match(rid) or rid.startswith("없음(사유")):
            result["no_id"].append(f"{label} ({kind})")
        if kindcol and kind not in CHANGE_KINDS:
            result["bad_kind"].append(f"{label} ({kind})")
        if col:
            val = r.get(col, "")
            if val.startswith("없음"):
                result["excused"] += 1
                continue
            ids = [x.strip() for x in re.split(r"[,\s]+", val) if x.strip()]
            if not ids:
                result["missing"].append(f"{label} ({kind})")
                continue
            bad = [i for i in ids if i not in cases]
            if bad:
                result["broken_ids"].append(f"{label}: {', '.join(bad)}")
            else:
                result["covered"] += 1
        else:
            if rid and rid not in ("—", "-") and rid in tagged:
                result["covered"] += 1
            else:
                result["missing"].append(f"{label} ({kind})")
    n = result["mapping_rows"]
    result["coverage_pct"] = round(100 * (result["covered"] + result["excused"]) / n, 1) if n else 0.0
    return result


def coverage_ok(c):
    """넘김(HT-13) 가능 여부: 커버리지 100% · 깨진 id 0 · ID 없음 0 · 변경 유형 오류 0."""
    return (c.get("coverage_pct") == 100.0 and not c.get("broken_ids")
            and not c.get("no_id") and not c.get("bad_kind"))


def to_markdown(rows, settings, conflicts, near_result, changed_only):
    out = ["# 하네스 인벤토리 (L0)", ""]
    if changed_only:
        out += [f"- 증분: {changed_only} 이후 바뀐 파일만", ""]
    out += ["| 종류 | 범위 | 경로 | 본문 줄 | ID | 긴 줄 비율 | paths · tools · skills | 표시 |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        extra = []
        if r["paths"]:
            extra.append("paths: " + ", ".join(r["paths"][:2]))
        if r["tools"]:
            extra.append(f"tools: {r['tools']}")
        if r["skills"]:
            extra.append("skills: " + ", ".join(r["skills"][:3]))
        ids = f"{r['ids']} ({'/'.join(r['id_prefixes'])})" if r["ids"] else "0"
        out.append(f"| {r['kind']} | {r['scope']} | {r['path']} | {r['body_lines']} | {ids} | {r['prose']} | {' · '.join(extra)} | {' · '.join(r['flags'])} |")
    if conflicts:
        out += ["", "## 이름 충돌 (같은 이름은 우선순위 높은 쪽만 쓰인다)", ""]
        out += [f"- {k}: {', '.join(v)}" for k, v in conflicts.items()]
    if settings:
        out += ["", "## 실행 · 설정 계층 (목록만)", ""]
        for s in settings:
            out.append(f"- `{s['path']}`: " + ", ".join(f"{k}={v}" for k, v in s.items() if k != "path"))
    if near_result:
        out += ["", f"# 대상 주변 후보 (L1): {near_result['target']}", "",
                f"- 대상에서 뽑은 인용 표현 {near_result['terms']}개로 하네스를 grep 했다. Claude 는 아래 후보만 읽는다.", "",
                "| 경로 | 종류 | 겹친 표현 수 | 예 | 줄 | 대상 이름 언급 | paths 겹침 |", "|---|---|---|---|---|---|---|"]
        for h in near_result["candidates"]:
            out.append(f"| {h['path']} | {h['kind']} | {h['shared_terms']} | {' · '.join(h['examples'])} | {', '.join(map(str, h['lines']))} | {'O' if h['mentions_target'] else ''} | {', '.join(h['paths_overlap'])} |")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="harness-tidy inventory (L0 목록 · L1 대상 주변)")
    ap.add_argument("--root", default=".", help="프로젝트 루트 (기본: 현재 폴더)")
    ap.add_argument("--include-user", action="store_true", help="~/.claude 사용자 범위 포함")
    ap.add_argument("--memory", help="auto memory MEMORY.md 경로 (선택)")
    ap.add_argument("--changed-since", metavar="REF", help="git REF 이후 바뀐 파일만 표시")
    ap.add_argument("--near", metavar="TARGET", help="L1: 이 대상 파일과 겹치는 후보만 추림")
    ap.add_argument("--out", help="결과 파일 경로 (기본: 표준 출력)")
    ap.add_argument("--json", action="store_true", help="JSON 으로 출력")
    ap.add_argument("--extra", action="append", metavar="GLOB", help='표준 위치 밖 지시 파일 (예: "harness/**/*.md"), 여러 번 지정 가능')
    ap.add_argument("--file", metavar="PATH", help="파일 하나의 전체 · 본문 줄 수만 출력 (wc -l 대신, OS 무관)")
    ap.add_argument("--version", action="store_true", help="harness-tidy 판 출력")
    ap.add_argument("--coverage", metavar="DIR", help="evals/{대상} 의 mapping.md 대비 evals.json 커버리지 확인")
    a = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if a.version:
        print(VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else "unknown")
        return
    if a.coverage:
        c = coverage(a.coverage)
        if a.json or "error" in c:
            print(json.dumps(c, ensure_ascii=False, indent=2))
        else:
            print(f"커버리지 {c['coverage_pct']}%  (매핑 {c['mapping_rows']}행 · 케이스 {c['covered']} · 사유 {c['excused']} · 누락 {len(c['missing'])} · 깨진 id {len(c['broken_ids'])})  [{c['mode']}]")
            print(f"새 ID  ID 없음 {len(c['no_id'])} · 변경 유형 오류 {len(c['bad_kind'])}  (새 ID 칸: ID 또는 '없음(사유: …)' · 유형: {' · '.join(CHANGE_KINDS)})")
            for m in c["missing"]:
                print(f"  누락  {m}")
            for b in c["broken_ids"]:
                print(f"  깨짐  {b}")
            for m in c["no_id"]:
                print(f"  ID 없음  {m}")
            for m in c["bad_kind"]:
                print(f"  유형 오류  {m}")
        sys.exit(0 if coverage_ok(c) else 1)
    if a.file:
        fp = Path(a.root) / a.file
        text = read(fp)
        _, body = split_frontmatter(text)
        print(f"{fp.as_posix()}\t전체 {len(text.splitlines())}줄\t본문 {len(body.splitlines())}줄")
        return

    root = Path(a.root).resolve()
    found = discover(root, a.include_user, a.memory, a.extra)
    rows = [analyze(k, s, p, root) for k, s, p in found]
    conflicts = name_conflicts(rows)
    near_result = near(a.near, rows, root) if a.near else None
    shown = rows
    if a.changed_since:
        ch = changed_files(root, a.changed_since)
        shown = [r for r in rows if Path(r["abs"]) in ch]
    settings = settings_summary(root, a.include_user)

    if a.json:
        result = json.dumps({"rows": shown, "conflicts": conflicts, "settings": settings, "near": near_result}, ensure_ascii=False, indent=2)
    else:
        result = to_markdown(shown, settings, conflicts, near_result, a.changed_since)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(result, encoding="utf-8")
        print(f"wrote {a.out} ({len(shown)} files)")
    else:
        print(result)


if __name__ == "__main__":
    main()
