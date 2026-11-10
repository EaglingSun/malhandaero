# 핸드오프 — meeting-minutes skill을 .claude/skills로 옮기기 (2026-11-10)

START HERE: CWD `C:\Users\USER\malhandaero` → 첫 답변에 아래 「가치」 절을 가치 블록으로 인용하고 실장 텍스트 승인(하네스설계 ①)을 받은 뒤 「할 일 1」부터.

## 상태 스냅샷
- main = origin/main = `30e6d46`(harness-tidy 추가) + 이 일지·핸드오프 커밋. 작업 트리 깨끗.
- 확정: CLAUDE.md·docs/HANDOFF.md는 저장소에 둔다(클라우드 세션 개발용, 실장 결정). `.gitignore` 변경 없음.
- 확정: harness-tidy v1.1.0 = `.claude/skills/harness-tidy/`(버전은 `VERSION` 파일). 원래 중첩 `.git`은 이전 세션 scratchpad로 옮겨 둠(필요 없음).

## 가치 (다음 세션 가치 블록 초안)
**Before**: `skills/meeting-minutes/SKILL.md`는 Claude Code가 자동으로 찾지 않는 위치라, 저장소를 열고 「회의록 정리해줘」라고 해도 skill이 쓰이지 않는다.
**After**: `.claude/skills/meeting-minutes/`로 옮겨 로컬·클라우드 세션에서 회의록 요청 시 skill이 자동 호출된다.
**하네스설계**: ① 새 트리거가 생긴다 → 텍스트 승인 필요.

## 할 일
1. `git mv skills/meeting-minutes .claude/skills/meeting-minutes` (빈 `skills/` 정리)
2. 경로 언급 수정: `README.md:71`, `docs/MINUTES_FORMAT.md:4`, `CLAUDE.md:15`·`CLAUDE.md:23`, `skills/meeting-minutes/SKILL.md:9`의 상대 경로(`docs/MINUTES_FORMAT.md`는 저장소 루트 기준이라 그대로 둬도 됨 — 확인)
3. `docs/HANDOFF.md`의 옛 경로 언급(16판 행)은 이력이므로 고치지 않는다
4. `.venv\Scripts\python -m pytest -q` → 75 통과·2 실패(아래 환경 실패)면 정상
5. 한국어 한 줄 커밋 + Co-Authored-By → push(올라갈 커밋 목록 먼저 확인)

## 건드리지 말 것 · 함정
- **앱 추출은 skill로 바꾸지 않는 것을 권장**(실장 미결): `server/llm.py:277`에서 `claude -p`가 임시 폴더 cwd로 돌아 저장소 skill을 못 읽는다. 저장소 cwd로 바꾸면 CLAUDE.md·harness-tidy까지 읽혀 토큰이 늘고, codex·GPT·Gemini·Ollama 연결은 skill을 못 쓴다. 정본은 `server/extract.py` 지시문 + `docs/MINUTES_FORMAT.md`.
- `extract.py`를 고치면 `docs/MINUTES_FORMAT.md`와 skill도 함께 맞춘다(CLAUDE.md 규칙 6).

## 실장 컨펌 대기
- [ ] meeting-minutes 이동 승인(하네스설계 ①)
- [ ] 앱 추출을 skill로 바꿀지 — 권장: 바꾸지 않음
- [ ] `CLAUDE.md:39` `8. docs/START.md를 고치면…` 줄이 「하지 않을 것」 절 끝에 붙어 있음(다른 세션 커밋) → 「작업할 때 지킬 것」 7번 뒤로 옮길지

## 알려진 시험 실패 (이번 변경과 무관 · HEAD에서도 실패)
- `tests/test_api.py::test_audio_without_stt_fails_with_reason` — 오류 문구 불일치(이 PC STT 환경 추정)
- `tests/test_llm_openai.py::test_gemini_key_autodetect` — gemini 대신 codex 선택(이 PC에 codex CLI 있어서로 추정)
- 원인 미확인. 고치려면 시험이 PC 환경(PATH의 codex, STT 설치)에 기대지 않게 monkeypatch.
