# harness-tidy 설치 (판: VERSION 파일 참고)

## 1. 받기
- 이 저장소를 Skill 자리에 받는다: `git clone --branch v1.0.0 https://github.com/EaglingSun/harness-tidy.git {자리}`
- 개인 공통 (모든 프로젝트): `~/.claude/skills/harness-tidy/`
  - Windows: `%USERPROFILE%\.claude\skills\harness-tidy\`
- 프로젝트 전용: `{프로젝트}/.claude/skills/harness-tidy/`
- 폴더 안에 SKILL.md 가 바로 보여야 한다 (harness-tidy/harness-tidy/ 처럼 두 겹이면 안 됨)

## 2. 함께 쓰는 공식 기능
- skill-creator: Claude Code 에서 `/plugin install skill-creator@claude-plugins-official`
- claude-md-management: Claude Code 에서 `/plugin install claude-md-management@claude-plugins-official`
- /doctor prompt-audit: Claude Code 내장 (v2.1.283 이상)
- 설치 후 Claude Code 재시작

## 3. (선택) 프로젝트 템플릿 배치
- 건너뛰어도 된다: CLAUDE.md 모드가 @ 참조 경로가 없으면 복사할지 묻는다
- 참조 검사기를 쓴다면 templates/claude-md.md 의 `@.claude/templates/*.md` 는 설치 후 프로젝트 기준 경로다 → 대상 `harness-tidy/templates/**` 로 범위를 좁혀 참조 허용
- templates/*.md → `{프로젝트}/.claude/templates/`
- templates/structure.md → `{프로젝트}/STRUCTURE.md` (기존 최상위 항목을 허용 목록에 먼저 모두 추가)
- templates/hooks/check_structure.py → `{프로젝트}/.claude/hooks/` (hook 은 마지막에 등록)

## 4. 사용
| 요청 | 모드 | 1단계 결과 |
|---|---|---|
| "하네스 정리" · "하네스 인벤토리" | inventory | 전체 목록 · 공유 관계 · Top 3 · 순서 |
| "{스킬명} 정리해줘" | skill | 검토 문서 · rule 이동 후보 |
| "{에이전트명} 에이전트 정리해줘" | agent | 검토 문서 · tools · skills preload 제안 |
| "CLAUDE.md 정리해줘" | claude-md | 검토 문서 · 이동 분류 |
| "{rule} 정리해줘" | rules | 검토 문서 · 하류 반영 표 |
| "리뷰어 프롬프트 정리해줘" (harness/reviewer.md) | prompt | 검토 문서 · 이 파일을 읽는 곳 |
| "출력 스타일 정리해줘" | style | 검토 문서 · 이동 분류 |
| "메모리 정리해줘" | memory | 승격 후보 표 (읽기 전용) |

- 처음이면 inventory 부터. 규칙을 공유하는 대상이 여럿이면 상류(CLAUDE.md · rule)부터

## 5. 인벤토리 스크립트 (Python 3.8+, 표준 라이브러리만)
```bash
python ~/.claude/skills/harness-tidy/scripts/inventory.py                    # L0 목록
python .../inventory.py --include-user --memory <MEMORY.md 경로>               # 사용자 범위 · 메모리 포함
python .../inventory.py --near .claude/skills/deck-script/SKILL.md           # L1 대상 주변 후보
python .../inventory.py --changed-since main                                 # 증분
python .../inventory.py --out docs/reports/<날짜>-harness-tidy/inventory.md  # 파일로 저장
python .../inventory.py --coverage evals/deck-script                         # 매핑 행 대비 Eval 커버리지 · 새 ID · 변경 유형 (하나라도 어긋나면 exit 1)
```
- 잡는 것: 줄 초과 · ID 유무 · 긴 줄(줄글) 비율 · agent tools 생략 · description 없음 · 끊긴 @참조 · skill/command 이름 충돌 · commands 이전 후보 · MEMORY 한도 · hooks/permissions/MCP 목록
- 비용 단계: L0 스크립트(기본) → L1 대상 주변(정리 때) → L2 전체 의미 비교(prompt-audit, 요청·정기 점검 때만)
- 검토 문서를 다시 돌릴 때는 "결정 칸은 유지"를 붙인다

## 6. Windows 확인
- Python: `python --version` 이 안 되면 `py --version` → 이하 명령의 `python` 을 `py` 로
- 한글 파일명 출력이 PowerShell 콘솔에서 깨지면 `--out` 으로 파일에 저장해서 본다
- 줄 수: `python scripts/inventory.py --file .claude/skills/x/SKILL.md` (wc -l 대신)
- 줄 번호: Claude Code 의 Grep 도구 (셸 명령 불필요). 사람이 볼 때는 `Select-String -Path <파일> -Pattern <표현>`
- .bak: `Copy-Item SKILL.md SKILL.md.bak` — 확장자는 맨 끝 (`.bak.md` 금지: rules · agents 폴더에서 다시 로드됨)
- hook: settings.json 의 `python` 을 PC 에 맞게 (`py`) 바꾸고, 허용 목록 밖 경로에 Write 를 시켜 차단되는지 한 번 확인
- 판 확인: `python scripts/inventory.py --version`

## 파일
- SKILL.md — 규칙 HT-01~18
- VERSION · CHANGELOG.md — 판과 변경 이력
- scripts/inventory.py — L0 목록 · L1 대상 주변 후보 · 증분
- modes.md — inventory · skill · agent · prompt · claude-md · rules · style · memory 모드 절차
- placement.md — 규칙을 둘 곳 (hook · CLAUDE.md · rule · style · skill · agent · MCP), 로드 판정, 중복 처리
- handoff.md — 공식 기능(skill-creator · claude-md-improver · /doctor prompt-audit)으로 넘기는 절차
- templates/ — summary(화면 요약) · mapping(매핑표) · review(검토 문서) · 규칙 포맷 · skill · agent · CLAUDE.md · 종료 리포트 · 구조 · why.md · evals.json(judge) · trigger-eval.json(트리거·위임) · hook
