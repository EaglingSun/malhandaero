# 핸드오프 — 포스터 띠 · 게시판 그림 자르기 · 말하기 보강 (2026-11-12, 클라우드 세션)

START HERE: 로컬(Windows) 세션에서 `git pull --rebase origin main` → `.venv\Scripts\python -m pytest -q` 실패 0 확인. 그다음 「이어서 할 일」 1번(게시글에 붙일 그림 만들기)부터.

## 상태 스냅샷
- `main` = `origin/main` = `9c40ab6`. 클라우드 작업 트리 깨끗. 시험 102 통과(linux).
- 로컬 세션 커밋(`b82bb44`~`3395b8f`: 좋아요 배너, START 정리, 「쓰는 방식 세 가지」 칸, 폰 깨짐 수정)은 클라우드 커밋 아래로 rebase해 합쳤다. 충돌 없음.
- 포스터 아티팩트 `https://claude.ai/artifact/CR8DdiWzVDDpbBLp258iqD` = `docs/POSTER.html`(`bd7d2de` 시점). 그 뒤 포스터 본문은 안 바뀜.
- 게시글은 아직 안 올림. 게시글 URL이 나오면 `MALHAN_POST_URL` 기본값(앱) · `POST_URL`(ai-docs-reader)에 넣는 일이 남아 있다.

## 이번 세션에서 바뀐 것 (전부 push 됨)
| 커밋 | 내용 |
|---|---|
| `883d0ea` | 말하기: 화면이 바뀌거나 전화가 오면(`visibilitychange`/`pagehide`) 그때까지 들은 말을 `keepalive`로 바로 보냄. 들은 말은 `localStorage(mh_mic_draft)`에 두었다가 앱이 꺼졌으면 다음 boot에 보냄(`micSendDraft`). `micIdle()`이 자기 자신을 부르던 버그(5b366d0에서 생김) 고침 → 이전엔 「다 말했어요」 눌러도 단추가 안 풀렸다. 결정 D-21, DESIGN 4장. |
| `659d797` `933bb8d` | `CLI_TIMEOUT` 240초 → `MALHAN_CLI_TIMEOUT` 기본 1800초(30분). 긴 회의록이 「Claude Code가 제때 답하지 않았어요」로 끊기던 것. `.env.example`에 줄 추가. |
| `bd7d2de` | 포스터 hero 훅 아래 `.gather` 띠: 점선 칩 6개(📅 3시 고객 미팅 · 📝 회의에서 맡은 일 · 📞 통화로 약속한 것 · 💬 메신저로 온 부탁 · 📷 안내문 사진 · 💭 아, 우유) → 민트 알약 「오늘 할 일, 한 화면」. 폰 폭에서 `.shot.wide` 1열. `tools/cut_poster.py` 새로 만듦. `.gitignore`에 `docs/img/poster/`. |
| `5952bcc` `9c40ab6` | `cut_poster.py`: 기본은 세 장(`01-top` 설치 칸 위 전부 / `02-install` / `03-bottom`), `--split`은 칸마다(기능 칸은 화면마다 → 14장), `--width`, `--scale`. |

## 건드리지 말 것 · 함정
- `docs/img/poster/`는 커밋하지 않는다(만든 그림, 3~4MB). 다시 만들면 된다.
- `cut_poster.py`는 playwright + chromium이 필요하다. Windows `.venv`에 없으면 `pip install playwright && playwright install chromium`. `tools/shoot_screens.py`와 같은 조건.
- `cut_poster.py`의 `NAMES` 순서는 지금 POSTER.html의 section 순서(hero · day · features · ways · pc · install · tools · close)와 맞춰 둔 것. 칸을 더하면 이름만 `secN`으로 떨어지고 동작은 한다.
- 설치 칸 그림(`02-install`)의 다운로드 단추는 그림이라 눌리지 않는다 → 게시글엔 그 아래에 링크를 글로 적는다(setup-windows.bat · setup-mac.command · 셋업 가이드).
- 포스터 `.gather` 칩 6개는 DESIGN.md의 실제 기능과 1:1이다(reviewer 확인). 칩을 더할 땐 앱에 없는 기능은 넣지 않는다.
- 말하기 `micFlush`는 `rec.abort()`로 끊고 `mic.on=false`를 먼저 둬서 `onend`가 다시 보내지 않게 한다. 순서를 바꾸면 두 번 보낸다.
- Mac 서버 폴더는 클라우드 세션에 연결된 `~/Downloads`에 없다(거기 `malhandaero*`는 옛 복사본). Mac을 볼 일이 있으면 설치 폴더를 먼저 알아낸다.

## 이어서 할 일
1. **게시글 그림**: 로컬에서 `python tools/cut_poster.py` → `docs/img/poster/01-top.png` `02-install.png` `03-bottom.png`. 게시판이 세로 긴 그림(900×6129, 3.2MB)을 못 받으면 `--scale 1`(크기 1/4) 또는 `--split`. 클라우드에서 만든 같은 세 장은 대화의 `poster-images.zip`에도 있다.
2. 게시글 올린 뒤 URL → `server/app.py`의 `MALHAN_POST_URL` 기본값, ai-docs-reader `app/main.py`의 `POST_URL` → 1.4.1 빌드·릴리스.
3. 아이폰에서 `https://todo.barreleye-neon.ts.net` 안 열리는 건 미해결. 아이폰에 Tailscale 앱 설치·같은 계정 로그인·Connected가 첫째 확인. Mac에서 `tailscale serve status`에 https 줄이 있는지도. 해결되면 START ⑤에 「아이폰도 Tailscale 앱 필요」 한 줄.
4. `1111_PA 회의.txt`(Mac)는 30분 제한 반영 후 「다시 뽑기」로 다시 돌려 본다. 또 실패하면 그때 로그를 본다.
5. 나머지는 `docs/HANDOFF.md` 3절.

## 실장 컨펌 대기
- 포스터 `.gather` 칩 문구(특히 「아, 우유」)와 순서 — 초안 그대로 커밋됨. 바꾸고 싶으면 `docs/POSTER.html` 220줄 근처.
