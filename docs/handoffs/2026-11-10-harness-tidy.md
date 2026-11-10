# 핸드오프 — 배포 전 개발 하네스 정리 (2026-11-10)

START HERE: CWD `C:\Users\USER\malhandaero` → 완결 세션이라 이어받을 작업은 없다. 새 기능을 더할 때는 `CLAUDE.md`(G-01~09)를 읽고 `.venv\Scripts\python -m pytest -q`가 실패 0인지부터 확인한다.

## 상태 스냅샷
- `main` = `origin/main` = `93432a1` + 이 일지·핸드오프 커밋. 작업 트리 깨끗.
- 시험: 83 통과 · 5 건너뜀 · 0 실패(Windows. 건너뛰는 5개는 sh 흉내 실행 파일 시험).
- 하네스: `CLAUDE.md` 본문 37줄(G-01~09) · `.claude/skills/meeting-minutes` 26줄(MM-01~11) · `.claude/skills/harness-tidy` 1.1.0.
- 앞 핸드오프 `2026-11-10-meeting-minutes-skill.md`의 할 일 1~5는 모두 끝났다. 그 문서의 「CLAUDE.md:39 규칙 8 위치」 건도 반영됨(G-08).
- 병렬 세션: 확인된 것 없음(push 직전 `origin/main`에 다른 커밋 없었음).

## 확정된 것
- 회의록 형식의 기준은 `docs/MINUTES_FORMAT.md` 한 곳. skill은 그 문서를 읽고, 앱은 `server/extract.py` 지시문을 쓴다. 두 곳의 수치 6가지는 `tests/test_minutes_sync.py`가 확인한다.
- 파일별 설명은 `README.md` 「개발」 표 한 곳. `CLAUDE.md` 구조 절에는 코드로 알 수 없는 약속만 둔다.
- `docs/dev-sessions/` · `docs/handoffs/` · `docs/reports/` · `evals/`는 저장소에 둔다(모든 설치 PC에 내려가지만 앱 동작과 무관).

## 건드리지 말 것 · 함정
- `MINUTES_FORMAT.md`나 `extract.py` 지시문의 수치 글귀를 바꾸면 `test_minutes_sync.py`의 정규식도 같이 고친다. 못 찾아도 실패하게 되어 있다.
- 시험에서 AI·STT 자동 감지를 다룰 때는 `_claude_bin` · `_codex_bin` · `stt.engine`을 모두 막는다. 개발 PC에 codex CLI·faster-whisper가 깔려 있다.
- `CLAUDE.md.bak` · `SKILL.md.bak`은 이 PC에만 있다(`.gitignore`의 `*.bak`). 정리 전 원본이 필요하면 git 이력(`377a23b`)을 본다.
- `evals/*/mapping.md`의 Eval 칸은 전부 「넘김 승인 뒤 작성」이다. Eval 씨앗(`evals.json`)은 없다.

## 실장 컨펌 대기
- [ ] 앱 추출을 skill로 바꿀지 — 권장: 바꾸지 않음(`server/llm.py`가 임시 폴더 cwd로 `claude -p`를 돌려 저장소 skill을 읽지 않는다)
- [ ] 이 저장소를 관리대상으로 등재할지 — `sun-repos.md` 표 1줄 + `settings.json` `additionalDirectories`에 `C:/Users/USER/malhandaero`

## 남은 일 후보
- 하네스 후보 — 클라우드 세션 시작 때 `requirements-dev.txt` 설치(SessionStart hook)
- 하네스 후보 — `.bat` ASCII 검사(G-05)를 pytest나 hook으로. `.env` · `data/`는 `.gitignore`가 막고 있다
- harness-tidy Eval 넘김(skill-creator) — 승인받으면 매핑표에서 씨앗을 만든다
- `AGENTS.md` 없음 — Codex로 개발하게 되면 `CLAUDE.md`를 가리키는 한 줄
