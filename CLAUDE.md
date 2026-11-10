# 말한대로 — Claude Code로 이 앱을 고치거나 더할 때

이 폴더를 Claude Code로 열면 이 파일을 먼저 읽는다. 사람이 읽어도 된다.

## 이 앱이 무엇인가
녹음·말·사진에서 "내가 챙길 일"을 뽑아 날짜별로 관리하는 개인 비서 웹앱. 각자 PC에 서버를 켜고 폰(PWA)으로 쓴다.
AI는 이 PC의 Claude Code(`claude -p`)를 부른다. 자료는 전부 `data/`(SQLite)에, 설정은 `.env`에.

## 구조 (파일별 설명은 README.md 「개발」 표, 설계는 docs/DESIGN.md, 이력은 docs/HANDOFF.md)
- `web/` 빌드 없는 화면(순수 HTML/JS/CSS, PWA). `app.js` 하나에 다 있다
- 최상위에는 사용자가 더블클릭하는 setup-*/start/autostart-* 파일만 둔다. 이들이 부르는 `.bat`·`.sh`·`.py`는 `tools/`에
- `.claude/skills/` Claude Code 스킬: `meeting-minutes`(회의록 형식, 기준은 `docs/MINUTES_FORMAT.md`) · `harness-tidy`(이 파일과 스킬 정리)
- `docs/prompts/` 앱이 화면에 내주는 설치 도우미 글(`/api/help/{topic}`이 읽는다). 지우거나 이름을 바꾸면 그 안내가 사라진다
- 세션 인계는 `docs/handoffs/` 최신 파일, 세션 일지는 `docs/dev-sessions/`, 판별 이력은 `docs/HANDOFF.md`

## 작업할 때 지킬 것
- G-01 **시험 먼저 돌린다**: `.venv/bin/python -m pytest -q` (Windows `.venv\Scripts\python -m pytest -q`). 고친 뒤에도 전부 통과해야 한다. 새 기능엔 시험을 붙인다.
- G-02 **DB 칸을 더할 때**는 `server/db.py`의 `MIGRATIONS`에 `(표, 칸, DDL)` 한 줄. 사용자가 이미 자료를 쌓고 있으니 표를 새로 만들지 않는다.
- G-03 **화면 문구는 쉬운 한국어**. '업데이트'·'버전'처럼 누구나 아는 외래어는 그대로. 못 한 일은 "못 했어요 + 사유"로 화면에 남긴다.
- G-04 **사람이 하는 일은 말하기·고르기·체크뿐**. 캘린더 같은 바깥 연결이 실패해도 할 일 저장은 막지 않는다.
- G-05 **`.bat` 파일은 ASCII만** (한글이 있으면 cmd가 줄을 깨뜨린다). `.env`와 `data/`는 절대 커밋하지 않는다.
- G-06 회의록 형식을 바꿀 때는 `docs/MINUTES_FORMAT.md`를 먼저 고치고 `server/extract.py` 지시문을 맞춘다. 수치는 `tests/test_minutes_sync.py`가 확인한다.
- G-07 커밋 메시지는 한국어 한 줄 + 끝에 `Co-Authored-By: Claude ...` 줄.
- G-08 `docs/START.md`를 고치면 `python tools/build_start_html.py`로 `docs/START.html`(그림 포함 한 파일)도 다시 만든다. 앱의 `/start`와 릴리스 첨부가 이 파일이다.

## 고친 것을 확인하는 법
- 서버를 켠 채라면 「말한대로 켜기」(`tools/run.bat`) / `start.command`를 껐다 켠다(코드가 새로 읽힌다). 화면만 고쳤으면 폰에서 새로고침.
- 화면 파일은 `?v=커밋` 버전이 붙어 캐시 문제가 없다. `manifest.webmanifest`를 바꾸면 폰 앱을 지우고 다시 설치해야 한다.

## 내가 고친 것을 남에게도 보내려면
- 이 저장소에 push 권한이 있으면 `main`에 커밋·push → 모두의 「업데이트」와 새벽 자동 업데이트로 퍼진다.
- 권한이 없으면 fork → PR. (저장소가 비공개인 동안은 관리자에게 collaborator 초대를 요청)
- **자동 업데이트와의 관계**: 고치다 만 파일이 있으면 업데이트가 건너뛴다(덮어쓰지 않음). 본인 커밋이 `main`에 쌓여 있으면 fast-forward가 안 돼 건너뛴다 → `git pull --rebase origin main`으로 받아 온다.
  나만 쓰는 수정은 가지(branch)에 두고, 받을 때만 `main`을 갱신하는 것이 편하다.

## 하지 않을 것
- G-09 음성·사진 원본을 남기는 것. 글로 바꾼 뒤 지운다.
