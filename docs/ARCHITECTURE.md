# 말한대로 구조

코드가 어떻게 짜여 있는지, 어떤 결정 위에 서 있는지, 문서를 어디서 고치는지를 이 한 파일에 둔다.
무엇을 만드는지(요구 · 화면 · 날짜 규칙)는 `docs/DESIGN.md`, 파일별 설명은 `README.md` 「개발」 표.

## 1. 한눈에

```
폰 (설치형 웹앱, Chrome)  /  PC 브라우저
   │  같은 와이파이 http (Chrome 예외 등록)  또는  Tailscale https (선택)
내 PC 서버 (FastAPI, uvicorn)  ← tools/run.py 가 감독, 업데이트 뒤 다시 켬
   ├─ 저장      server/db.py       SQLite data/
   ├─ 추출      server/extract.py  지시문 · 응답 해석 · 회의록
   ├─ AI        server/llm.py      claude(기본) | codex | api | gpt | gemini | ollama | openai | fake
   ├─ 음성 인식 server/stt.py      faster-whisper(로컬) | gemini | 없음
   ├─ 캘린더    server/calsync.py  구글(OAuth) · 네이버(CalDAV)
   └─ 업데이트  server/updater.py  git fast-forward → 필요 시 재설치 → 다시 켬
```

- 화면은 `web/`의 빌드 없는 PWA. 서버가 `/`, `/start`(`docs/START.html`), `/manifest.webmanifest`, `/sw.js`와 `/api/*`를 낸다.
- 입력 한 건의 상태(`inputs.status`): `received → transcribing → extracting → extracted` (실패하면 `failed` + 사유). `ready`는 「처리 중」 조회에만 남아 있고 넣는 코드는 없다. 단계별 규칙은 `docs/DESIGN.md` 3장.

## 2. 데이터 모델

`server/db.py`의 `SCHEMA`와 같아야 한다(`tests/test_docs_sync.py`가 확인). 칸을 더할 때는 `MIGRATIONS`에 한 줄(G-02).

```
users(id, name, token, created_at)
inputs(id, user_id, kind, title, source_name, received_date, media_path, transcript, speakers, me_speaker, status, error, summary, minutes, done_at, created_at)
items(id, user_id, input_id, text, quote, due_text, due_date, scope, status, plan_date, plan_time, owner, who, done_at, addon, record_id, cal_ref, cal_pin, details, created_at, updated_at)
day_logs(user_id, date, summary, note, mood, created_at)
calendar_links(user_id, provider, mode, config, status, updated_at)
calendar_hidden(user_id, ref, created_at)
addon_settings(user_id, addon, enabled, options)
records(id, user_id, addon, type, input_id, data, date, status, created_at)
```

- `items.status`: `new` `todo` `later` `skipped` `done` `other`(남의 일). `items.owner`: `me` `unclear` `other`.
- JSON을 글로 넣는 칸: `inputs.speakers`(배열) · `inputs.minutes`(`{topics, questions}`) · `items.details`(세부 항목 배열) · `calendar_links.config` · `addon_settings.options` · `records.data`.
- `addon_settings`는 「오늘 한 줄」을 켰는지(`addon='diary'`)를 담는 데 쓴다. `records`는 더하기(애드온) 자리만 잡아 둔 표로, 쓰는 코드가 아직 없다.

## 3. 바깥 연결

| 연결 | 동작 |
|---|---|
| AI | `MALHAN_AI`로 고른다. 비우면 Anthropic 키 → Claude Code → Codex → OpenAI 키 → Gemini 키 순으로 있는 것을 쓴다(`llm.mode()`). 없으면 `none` — 직접 적기 · 캘린더 · 하루 마무리는 그대로 된다 |
| 음성 인식 | faster-whisper가 깔려 있으면 그것, 없고 Gemini 키가 있으면 Gemini(`stt.engine()`). `MALHAN_STT`로 고정 |
| 구글 캘린더 | 앱에 내장한 데스크톱형 OAuth 클라이언트. PC의 localhost에서만 연결을 받는다. `.env`에 본인 클라이언트가 있으면 그쪽이 우선 |
| 네이버 캘린더 | CalDAV + 애플리케이션 비밀번호 |
| 폰 접속 | 기본은 같은 와이파이 http. 설치 · 공유 · 마이크는 폰 Chrome에 주소를 예외 등록해 푼다. 회사 밖 · 같이 쓸 사람(팀원 · 가족)은 Tailscale https |

## 4. 켜기와 업데이트

- `setup-windows.bat` / `setup-mac.command`가 받아서 설치하고 바로 켠다. 그 뒤로는 바탕 화면 「말한대로 켜기」(`tools/run.bat`) / `start.command`.
- 켜면 PC 브라우저가 localhost로 한 번 열린다(자동 시작은 열지 않는다). 포트가 쓰이는 중이면 켜지지 않고 안내한다.
- 업데이트는 세 곳에서 부른다: 켜기 전(`tools/update.py`), 화면의 「업데이트」(`POST /api/update`), 매일 새벽 4시. 한 시간마다 새 버전이 있는지 확인해 「지금 적용」 띠를 띄운다.
- 받는 순서: `git fetch` → fast-forward만 → requirements가 바뀌면 재설치 → manifest가 바뀌면 폰 앱 재설치 안내.
- 처음 한 번, `.git`이 없는 폴더면 저장소에 연결한다(init → fetch → 강제 checkout). 이때만 폴더의 코드 파일을 저장소 것으로 덮어쓴다. `data/` · `.env`는 그대로.
- 켜져 있는 동안 받았으면 서버를 `RESTART_CODE(3)`로 끝내고 `tools/run.py`가 새 코드로 다시 켠다. 처리 중인 입력이 있으면 끝날 때까지 기다린다.
- 추적 중인 파일을 고치다 만 것이 있으면 건너뛴다(덮어쓰지 않음). 인터넷이 안 되거나 받지 못해도 지금 코드로 켠다. 재설치가 실패했을 때만 켜지 않고 멈춘다.
- `MALHAN_LABEL`이 앱 이름에 붙어 PC 두 대가 폰에 두 앱으로 깔린다.

## 5. 결정

읽는 때와 더하는 때는 `CLAUDE.md` G-10 · G-11. 바뀐 결정은 지우지 않고 상태를 「바뀜 → D-NN」으로 적는다. 판 번호의 내용은 `docs/ARCHIVE.md` 1절.

| 번호 | 결정 (이전에 다르게 했으면 괄호 안에) | 이유 | 언제 | 상태 |
|---|---|---|---|---|
| D-01 | 각자 PC에 설치하고 각자 Claude Code 로그인을 쓴다. 한 로그인으로 여러 명이 쓰는 공용 서버로 운영하지 않는다. 가족 · 팀 초대 기능은 남기되 AI가 PC 주인의 구독을 쓴다는 주의와 함께 안내한다 | 구독 약관 | 11/10 | 유효 |
| D-02 | AI 기본은 이 PC의 Claude Code(`claude -p`). 다른 AI 연결은 코드에 두되 안내는 다음 버전에서 (이전: Gemini 등 여러 AI를 같이 안내) | API 키 없이 쓰게 · Gemini는 11/10 내내 503 | 11/10 | 유효 |
| D-03 | 음성 · 사진 원본은 글로 바꾼 뒤 지운다(G-09) | 개인정보 | 초기 | 유효 |
| D-04 | 표를 새로 만들지 않고 `MIGRATIONS`로 칸만 더한다(G-02) | 사용자가 이미 자료를 쌓고 있다 | 초기 | 유효 |
| D-05 | 화면 문구는 쉬운 한국어. '업데이트' · '버전'은 그대로(G-03) (이전: '새 판') | '새 판'이 어색하다는 사용자 의견 | 11판 | 유효 |
| D-06 | 바깥 연결(캘린더 · 업데이트)이 실패해도 할 일 저장과 켜기는 막지 않는다(G-04) | 사람이 하는 일은 말하기 · 고르기 · 체크뿐 | 초기 | 유효 |
| D-07 | 이월은 일괄 작업이 아니라 조회 규칙이다(`docs/DESIGN.md` 4장) | 며칠 앱을 안 열어도 어긋나지 않는다 | 초기 | 유효 |
| D-08 | 캘린더에서 가져온 할 일은 고치거나 지워도 캘린더 쪽을 건드리지 않는다 | 기록에 이유는 없다(공유 캘린더의 일정을 지키려는 것으로 보인다) | 20판 | 유효 |
| D-09 | 회의는 녹음 앱의 텍스트 공유가 기본 경로다. 음성 파일 변환은 선택 | 음성 파일에는 화자 구분이 없다 | 18판 | 유효 |
| D-10 | 안내는 혼자 쓰기가 기본이다. 가족 · 팀 공유는 접힌 곳에 둔다 (이전: 초대 QR을 「휴대폰 연결」 첫 화면에) | 출품 버전을 단순하게 | 40판 | 유효 |
| D-11 | 더하기(애드온)는 본체가 안정된 뒤에 만든다. 지금은 자리만(`docs/DESIGN.md` 11장) | 공모는 본체로 응모 | 11/10 | 유효 |
| D-12 | 최상위에는 더블클릭하는 영문 이름 파일만 둔다. `.bat`은 ASCII만(G-05) (이전: `말한대로 처음 설치.bat` 같은 한글 이름) | 한글이 있으면 cmd가 줄을 깨뜨린다 | 29판 · 11/10 | 유효 |
| D-13 | 개발용 파일(`CLAUDE.md` · `.claude/` · `docs/handoffs/` · `docs/dev-sessions/` · `docs/reports/` · `evals/`)도 저장소에 둔다 (이전: `.gitignore`로 빼려다 취소) | 클라우드 세션에서 이어서 개발 | 11/10 | 유효 |
| D-14 | 기록은 이 PC의 `data/`에만 저장한다. AI로 가는 때는 둘이다: 할 일을 뽑을 때(넣은 글 · 사진, 이미 적어 둔 할 일, 최근 「안 함」으로 넘긴 일)와 하루 마무리 글을 쓸 때(그날 할 일, 오늘 한 줄과 기분). whisper가 없고 Gemini 키가 있으면 녹음도 Gemini로 간다 | 안내 문구는 저장 위치와 AI로 가는 것을 함께 쓴다 | 11/10 | 유효 |
| D-15 | 문서는 6절 표의 역할대로 나눈다. 포스터는 홍보, START는 설치 · 운영. 중요하지 않은 지난 기록은 `docs/ARCHIVE.md`로 (이전: INSTALL.md와 START.md 두 벌, HANDOFF.md에 이력까지) | 같은 내용이 여러 벌이면 어긋난다 | 11/10 | 유효 |
| D-16 | 구글 캘린더는 앱에 내장한 데스크톱형 클라이언트로 PC의 localhost에서 연결한다 (이전: 사용자가 구글 클라우드에서 웹 클라이언트를 만들어 `.env`에) | 받는 사람이 버튼 하나로 연결 | 41~42판 | 유효 |
| D-17 | 로그인 코드는 설치 때 본인이 정한다 (이전: 기본값 1234) | 회사 와이파이에서 남이 들어오지 못하게 | 11/10 | 유효 |
| D-18 | 커밋 전 검수는 서브에이전트 `reviewer`에 맡긴다(G-12) | 쓴 쪽은 자기 글의 어긋남을 못 본다 | 11/10 | 유효 |
| D-19 | 캘린더에 넣을지는 기본 규칙(시각 있는 일만 / 모든 일) 위에 항목별 「캘린더에 넣기 / 빼기」(`items.cal_pin`)가 우선한다 | 시각 있는 일은 거의 다 넣지만, 시각 없는 일은 넣을 것과 안 넣을 것이 갈린다 | 11/11 | 유효 |
| D-20 | 지난 날짜 화면에서 끝냄 체크/해제는 그 날짜 기준(`done_date`)으로 남는다 (이전: 해제하면 오늘 할 일로) | 어제 한 일을 어제 한 일로 고칠 수 있어야 한다 | 11/11 | 유효 |
| D-21 | 말하기는 화면이 바뀌거나 전화가 오면 그때까지 들은 말을 바로 보내고(`keepalive`), 들은 말은 `localStorage`에 두었다가 앱이 꺼졌으면 다음에 열 때 보낸다 | 안드로이드는 화면이 가려지면 음성 인식을 끊고 자료를 버린다 | 11/11 | 유효 |

## 6. 문서 지도

`docs/` 바로 아래의 문서는 모두 이 표에 있어야 한다(시험이 확인). 새 문서를 만들기 전의 규칙은 `CLAUDE.md` G-11.

| 문서 | 역할 | 이 문서가 기준인 내용 |
|---|---|---|
| `README.md` | 저장소 첫 화면 | 앱 한 줄 소개, 설치 파일 주소, 파일별 설명(「개발」 표) |
| `docs/POSTER.html` | 홍보 — 앱의 가치 | 홍보 문구와 실제 화면 캡처(`docs/img/screens/`, `tools/shoot_screens.py`로 찍고 `tools/build_poster.py`로 넣음) |
| `docs/STYLE.html` | 디자인 덱 — 포스터의 색 · 글꼴 · 부품 견본 | 색 값(`:root`) |
| `docs/START.md` | 설치 · 운영 안내 | 5단계 이름과 순서, 안 될 때, 설정(`.env`) 안내 |
| `docs/START.html` | START.md를 그림까지 넣어 만든 한 파일. 앱의 `/start` | 없음 — 손으로 고치지 않는다(G-08) |
| `docs/DESIGN.md` | 설계 — 무엇을 왜 만드는가 | 약속 표, 입력 종류, 처리 규칙, 날짜 규칙, 화면, 더하기 |
| `docs/ARCHITECTURE.md` | 구조 · 결정 · 문서 지도 | 이 파일 전부 |
| `docs/MINUTES_FORMAT.md` | 회의록 형식 | 회의록 규칙과 수치(G-06) |
| `docs/HANDOFF.md` | 남은 일 — 다음 할 일, 아직 확인하지 못한 것, 남은 결정 | 그 세 가지 |
| `docs/ARCHIVE.md` | 지난 기록 — 판별 변경, 끝난 일, 적을 때의 환경 메모. 다른 문서에서 덜어낸 것을 덧붙이는 곳 | 없음 — 지금 상태의 기준으로 쓰지 않는다 |
| `CLAUDE.md` | Claude Code로 고칠 때의 규칙 | G-NN 규칙 |

폴더: `docs/handoffs/` 세션 인계(최신 파일이 현재 상태) · `docs/dev-sessions/` 세션 일지 · `docs/reports/` 점검 보고 · `docs/prompts/` 앱이 내주는 도우미 글 · `docs/img/` START의 그림 · `docs/img/screens/` 포스터용 실제 화면 캡처

## 7. 바꾸면 같이 고칠 곳

| 바꾼 것 | 같이 고칠 곳 | 시험이 확인하나 |
|---|---|---|
| DB 표 · 칸 | 2절 데이터 모델 | 예 (`MIGRATIONS`로 더한 칸까지) |
| `MALHAN_*` 설정 이름 | `docs/START.md`, `.env.example` | 문서에 적힌 이름이 코드에 있는지만. 새 설정을 문서에 적었는지는 사람이 본다 |
| 파일 이름 · 위치 | `README.md` 「개발」 표, `CLAUDE.md`, 이 파일 | 예 (문서 속 경로가 실제로 있는지) |
| 설치 파일 · 릴리스 버전 | `README.md`와 `docs/POSTER.html`의 내려받기 주소 | 예 |
| 5단계 이름 · 순서 | `docs/START.md`, `docs/POSTER.html` (`README.md`는 단계 수만) | 예 |
| `docs/START.md` | `python tools/build_start_html.py` (G-08) | 예 |
| 포스터의 색 | `docs/STYLE.html`, `tools/build_start_html.py` | 예 |
| 홍보 문구(약속) | `docs/DESIGN.md` 1장 약속 표 | 아니오 |
| AI로 가는 것(무엇이 언제) | 5절 D-14, `docs/DESIGN.md` 8장, `docs/START.md`와 `README.md`의 「알아 둘 것」, 포스터의 「내 PC에만」 카드 | 아니오 |
| 업데이트 동작 | 4절, `docs/START.md` 「업데이트」, `CLAUDE.md` 「내가 고친 것을 남에게도 보내려면」 | 아니오 |
| 화면 구성 · 문구 | `docs/DESIGN.md` 6장, `docs/START.md`, 포스터의 화면 캡처(`python tools/shoot_screens.py && python tools/build_poster.py`로 다시 찍음) | 아니오 |
| 회의록 형식 | `docs/MINUTES_FORMAT.md` 먼저 (G-06) | 예 (`tests/test_minutes_sync.py`) |
| 결정을 새로 내리거나 바꿈 | 5절 표 | 번호 형식만 |
