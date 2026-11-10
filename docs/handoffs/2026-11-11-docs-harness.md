# 핸드오프 — 문서 정리와 문서 관리 하네스 (2026-11-11)

START HERE: CWD `C:\Users\USER\malhandaero` → 먼저 `.venv\Scripts\python -m pytest -q`가 실패 0인지 확인한다. 이어서 할 일은 `docs/HANDOFF.md` 3절이고, 그중 이번 세션이 남긴 것은 아래 「이어서 할 일」 1 · 2번이다. 기능을 고치기 전에 `docs/ARCHITECTURE.md` 5절(결정)을 읽는다(G-10).

## 상태 스냅샷
- `main` = `origin/main` = `5d2f3c7` + 이 일지 · 핸드오프 커밋. 작업 트리 깨끗.
- 시험: 93 통과 · 5 건너뜀 · 0 실패(Windows). `tests/test_docs_sync.py` 10개는 결함 21건을 넣어 모두 실패하는 것을 확인했다.
- 문서 구성은 `docs/ARCHITECTURE.md` 6절 「문서 지도」가 기준이다. `docs/HANDOFF.md`는 이제 남은 일만 적는 문서이고, 판별 변경 표 같은 지난 기록은 `docs/ARCHIVE.md`에 있다.
- 포스터 정리본을 비공개 아티팩트로 올렸다: https://claude.ai/artifact/RgQHa91DyKTMo3z1TUbYiH (폰 확인용). 옛 아티팩트 `CR8DdiWzVDDpbBLp258iqD`는 건드리지 않았다.
- 병렬 세션: 확인된 것 없음(push 직전 `origin/main`에 다른 커밋 없었음).

## 확정된 것
- 결정은 `docs/ARCHITECTURE.md` 5절 표(D-01~18) 한 곳. 바뀐 결정은 지우지 않고 「바뀜 → D-NN」.
- 규칙 G-10(고치기 전 결정 · 설계 읽기) · G-11(끝낼 때 7절 표대로 문서 맞추기) · G-12(커밋 전 검수는 `reviewer` 서브에이전트). 사용자 문서를 고치면 문체 점검을 거친다(G-03).
- 지금 개발에 필요 없어진 내용은 지우지 않고 `docs/ARCHIVE.md` 끝에 옮긴다. 그 문서는 다듬지 않는다.
- 포스터는 문구와 모형 내용만 실제에 맞췄다. 배치 · 색 · 글꼴은 그대로다. 색을 바꿀 때는 `docs/STYLE.html` → `docs/POSTER.html` → `tools/build_start_html.py` 순서.

## 건드리지 말 것 · 함정
- `docs/START.md`를 고치면 `python tools/build_start_html.py`를 꼭 돌린다. 안 돌리면 `test_start_html_is_built_from_md`가 실패한다. `markdown` 버전이 달라도 실패할 수 있다(실패 글에 버전이 나온다, `requirements-dev.txt`는 `>=3.5,<4`).
- START의 ①~⑤ 제목을 바꾸면 포스터 5단계 카드의 제목과 `web/index.html`의 `/start#⑤-…` 링크도 맞춰야 한다(시험이 확인).
- `docs/` 바로 아래에 `.md` · `.html`을 더하면 `ARCHITECTURE.md` 6절 표에 한 줄을 더해야 시험이 통과한다.
- `.claude/agents/reviewer.md`는 이번 세션에 새로 만든 파일이라 다음 세션부터 불러진다. 문체 기준인 `~/.claude/rules/sun-writing-style.md`는 이 PC에만 있고, 클라우드 세션은 RV-06의 다섯 가지 요약으로 본다.
- 포스터 문구 · 문체를 고친 마지막 변경(커밋 `5d2f3c7`에 포함)은 서브에이전트 재검토를 거치지 않았다. 화면 캡처도 실패해 「하루 끝」 모형(고치기 전보다 4px 아래)과 5단계 카드 높이를 눈으로 보지 못했다.

## 이어서 할 일
1. 클라우드 세션 검토: `docs/POSTER.html` · `docs/START.md`를 먼저 본다(위 함정 마지막 줄).
2. 코드 안의 낡은 안내 글 정리 — `docs/HANDOFF.md` 3절 8번(`--remote`, 「휴대폰 연결」, 「.env 첫 줄」, 입력이 끊기면 코드 1234, `--local`이 열린 주소를 닫지 않음). 기능 변경이라 이번에는 손대지 않았다.
3. 나머지는 `docs/HANDOFF.md` 3절 순서대로.

## 실장 컨펌 대기
- [ ] `docs/ARCHIVE.md` 3절의 개인 환경(Tailscale 주소, 가족 캘린더, 개인 캘린더 이름)을 지울지. 지워도 git 이력에는 남는다
- [ ] `server/calsync.py:262`의 구글 OAuth 클라이언트 비밀값 — 데스크톱형이라 의도한 것인지(저장소가 공개로 바뀐 뒤)
- [ ] 옛 포스터 아티팩트(`CR8DdiWzVDDpbBLp258iqD`)를 정리본으로 덮어쓸지 — 공모 게시글이 그 주소를 가리키면 옛 문구가 보인다
- [ ] 「말하기」는 Chrome 음성 인식이라 말이 구글 서버를 거친다. 포스터 · START의 「기록은 내 PC에만」 옆에 적을지
- [ ] 아이폰에서 설치 · 공유가 되는지 확인(지금 포스터는 「Android 폰 + Chrome 기준」)
- [ ] 이 저장소를 관리대상으로 등재할지 — `sun-repos.md` 표 1줄 + `settings.json` `additionalDirectories`에 `C:/Users/USER/malhandaero` (앞 핸드오프에서 이월)
- [ ] 앱 추출을 skill로 바꿀지 — 권장: 바꾸지 않음 (앞 핸드오프에서 이월)

## 남은 일 후보
- 하네스 후보 — `.bat` ASCII 검사(G-05)를 pytest로
- 하네스 후보 — 상태 값(`inputs.status` 흐름, `RESTART_CODE`)과 `--local` 같은 실행 옵션을 문서와 비교하는 시험(지금은 사람이 본다, `ARCHITECTURE.md` 7절)
- harness-tidy Eval 넘김 — `evals/claude-md/mapping.md` M15~M20의 Eval 칸은 「넘김 승인 뒤 작성」
