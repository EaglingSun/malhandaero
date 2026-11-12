# 핸드오프 — 포스터 상단 네 칸 · 게시글 조각 · cut_board (2026-11-12, 로컬 세션)

START HERE: CWD `C:\Users\USER\malhandaero` → `git status`와 `git log --oneline origin/main..HEAD`로 아직 push하지 않은 로컬 커밋을 확인한다. 실장이 push를 정하면 아래 「이어서 할 일」 1번(원격의 `1804c79`와 합치기)부터. 같은 날 클라우드 세션의 핸드오프는 `docs/handoffs/2026-11-12-poster-images.md`.

## 상태 스냅샷
- 로컬 `main` = `origin/main`(받은 시점 `9c609b2`) + 로컬 커밋 `a8098aa`(포스터 · 조각) · `650d19c`(cut_board) + 이 일지 · 핸드오프 커밋. **push하지 않았다.**
- `origin/main`은 그사이 `1804c79`(게시글용 움직이는 그림, `tools/shoot_gif.py`)로 앞서갔다. `README.md`와 `docs/ARCHITECTURE.md`를 같이 고쳐서 합칠 때 그 두 파일에서 충돌이 날 수 있다(같은 줄인지는 확인하지 않았다).
- 시험: 104 통과 · 5 건너뜀 · 0 실패(Windows, 로컬 커밋 기준).
- 게시글 조각 7장: `docs/img/board/`(커밋됨). 같은 파일이 앞 세션 임시 폴더 `…\a11f8a58-…\scratchpad\board\slices`에도 있다.
- 초안 아티팩트(비공개, 저장소 포스터와 같은 내용): https://claude.ai/artifact/9McncVWHJQj2Yu6JSiENf2
- 포스터 아티팩트 `CR8DdiWzVDDpbBLp258iqD`는 아직 옛 문구(`bd7d2de` 시점)다.
- 병렬 세션: 클라우드 세션이 같은 날 `origin/main`에 커밋 중이다(`9c609b2`, `1804c79`).

## 확정된 것
- 포스터 상단 띠: 네 칸(캘린더 일정 / 오늘 일정이 할 일 위에 · 회의에서 맡은 일 / 녹음 앱에서 바로 공유 · 통화로 한 약속 / 녹음 앱에서 바로 공유 · 머릿속 할 일 / 말 한마디로) + 「메신저 부탁 · 그 밖의 요청은 말하거나 사진을 찍으면 알아서 추가돼요」 + 「↓ 전부 「오늘 할 일」 한 화면에」.
- 둘째 칸 제목: 「아침 회의부터 퇴근길 통화까지, 다 이 앱 하나로 관리해요」. 이 제목과 「녹음 앱에서 바로 공유」, 메신저 한 줄은 실장이 정한 문구다.
- 게시글 조각은 `docs/img/board/`에 커밋한다. 포스터를 고치면 `python tools/cut_board.py`를 다시 돌린다.
- `docs/img/poster/`는 폴더만 남기고(`.gitkeep`) 그 안의 `*.png`만 커밋에서 뺀다.

## 건드리지 말 것 · 함정
- `tools/cut_board.py`는 playwright와 Chrome이 필요하다. 이 PC의 `.venv`에는 playwright가 없어 시스템 `python`으로 돌린다.
- 조각의 단추 줄 높이가 114px에서 77px로 줄었다(`2a-windows` 269×77, `2b-mac` 195×77, `2c-guide` 246×77, `2d-blank` 390×77). 게시글 HTML에 조각 크기를 적어 두었으면 맞춘다.
- 조각 경계 세 곳에 옆 요소의 옅은 그림자가 걸쳐 있다. 게시판이 조각 사이에 틈을 넣으면 보일 수 있다.
- 마지막 버전의 조각(「할 일 위에」로 고친 뒤)은 코드 확인만 했다. 눈 확인은 그 앞 버전까지 했고, `1-top.png`는 축소해서만 봤다.
- `cut_board.py`의 「포스터에서 요소를 찾지 못했어요」 경로는 실제로 실패시켜 보지 않았다. 마지막 시험 3개를 더한 뒤 reviewer를 다시 돌리지 않았다.
- 포스터 칸 순서나 설치 단추 수를 바꾸면 `cut_board.py`가 「못 했어요」로 멈춘다(단추 3개, 한 줄이 전제).

## 이어서 할 일
1. push(실장 결정 뒤): `git pull --rebase origin main`으로 `1804c79`를 받고, `README.md` 57줄 · `docs/ARCHITECTURE.md`에서 충돌이 나면 두 설명(`shoot_gif.py`, `cut_board.py`)을 다 남긴다 → 전체 시험 → push. push하면 GitHub Pages 포스터와 모두의 자동 업데이트에 반영된다.
2. 포스터 아티팩트 `CR8DdiWzVDDpbBLp258iqD`를 새 포스터로 다시 올릴지(실장 결정).
3. 게시글 올리기 → URL을 `server/app.py`의 `MALHAN_POST_URL` 기본값과 ai-docs-reader `POST_URL`에(앞 핸드오프 2번).
4. 나머지는 `docs/handoffs/2026-11-12-poster-images.md` 「이어서 할 일」 3~5번과 `docs/HANDOFF.md` 3절.

## 실장 컨펌 대기
- [ ] push 여부
- [ ] 옛 포스터 아티팩트를 새 내용으로 덮어쓸지
- [ ] 「알아서 추가돼요」 — 받은 뒤 사람이 「넣기」를 눌러야 해서 바로 추가되는 것으로 읽힐 수 있다(reviewer 지적, 실장 문구라 그대로 둠)
- [ ] 상단에서 빠진 「다른 AI가 쓴 회의록 파일도 공유」 문구를 다른 칸에 살릴지

## 남은 일 후보
- 하네스 후보 — `docs/img/board/` 조각이 지금 `docs/POSTER.html`로 자른 것과 같은지 확인하는 시험(playwright가 있을 때만)
