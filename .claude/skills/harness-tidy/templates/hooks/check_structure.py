#!/usr/bin/env python3
"""PreToolUse hook: STRUCTURE.md 허용 목록 밖 쓰기를 막는다 (G-05).

등록: .claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {"matcher": "Write|Edit|MultiEdit",
       "hooks": [{"type": "command",
                  "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/check_structure.py\""}]}
    ]
  }
}
한계: Bash 의 mkdir · 스크립트가 만드는 파일은 잡지 못한다. 세션 끝에 git status 로 보완한다.
"""
import json
import os
import re
import sys
from pathlib import Path

data = json.load(sys.stdin)
path = data.get("tool_input", {}).get("file_path", "")
if not path:
    sys.exit(0)

root = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
try:
    rel = Path(path).resolve().relative_to(root)
except ValueError:
    sys.exit(0)  # 프로젝트 밖 경로는 판단하지 않는다

structure = root / "STRUCTURE.md"
if not structure.exists():
    sys.exit(0)  # 도입 전에는 막지 않는다

m = re.search(r"<!-- allowed:start -->(.*?)<!-- allowed:end -->",
              structure.read_text(encoding="utf-8"), re.S)
allowed = {l.strip().strip("/") for l in m.group(1).splitlines() if l.strip()} if m else set()

top = rel.parts[0]
if top in allowed:
    sys.exit(0)

print(f"G-05: '{top}' 는 STRUCTURE.md 허용 목록에 없습니다. "
      "트리를 먼저 제안하고 승인받은 뒤 목록에 추가하세요.", file=sys.stderr)
sys.exit(2)  # 2 = 차단, 메시지는 Claude 에게 전달됨
