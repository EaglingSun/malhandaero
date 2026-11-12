# 말한대로

> 말만 하세요. 기억은 제가 할게요.

통화·회의 녹음, 말로 한 메모, 사진에서 **내가 챙길 일**을 뽑아 날짜별로 관리하는 개인 비서 앱.
**PC**는 켜 두는 서버, **쓰는 건 폰**. AI는 내 PC에 로그인된 Claude Code를 쓰고(API 키 없음), 기록은 내 PC에만 저장돼요.

## 설치 — 파일 하나만 받으세요

| | 받을 파일 | 하면 |
|---|---|---|
| **Windows** | [setup-windows.bat](https://github.com/EaglingSun/malhandaero/releases/download/v1.0.0/setup-windows.bat) | 더블클릭하면 `C:\Users\이름\malhandaero`에 설치되고, 바탕 화면에 「말한대로 켜기」가 생겨요 |
| **Mac** | [setup-mac.command](https://github.com/EaglingSun/malhandaero/releases/download/v1.0.0/setup-mac.command) | 우클릭 → 열기를 누르면 설치돼요. 그 뒤엔 `start.command`로 켜요 |

그다음은 **[셋업 가이드](docs/START.md)** 5단계(15분)를 따라 하면 돼요. 막힐 때, 팀원·가족과 같이 쓸 때, 캘린더 상세도 같은 문서 뒷부분에 있어요. 앱 안에서는 맨 아래 「시작 안내」로 열어요.

Claude 구독(Pro 이상)이 없어도 할 일 관리 앱으로 쓸 수 있어요. Codex·GPT·Gemini 같은 다른 AI 연결은 다음 버전에서 안내할 예정이에요.

## 되는 것

- **+ → 말하기**나 녹음 앱의 **텍스트 변환 → 공유**로 넣으면 할 일과 회의록(논의·결정·확인할 것)이 만들어져요
- 글 붙여넣기, 텍스트 파일, 사진으로도 넣고, AI 없이 직접 적을 수도 있어요
- 할 일마다 **오늘 · 나중 · 안 함** 하나만 누르면 돼요. 못 끝낸 일은 다음 날로 넘어가요
- 하루를 마칠 때 「오늘은 여기까지」를 누르면 정리 글이 만들어지고, 지난날은 **달력**에서 봐요
- **구글·네이버 캘린더**에 할 일을 올리고 일정을 가져와요. 폰 홈 화면에 앱으로 깔면 녹음 앱의 공유 목록에 나와요
- 새 기능은 앱의 「업데이트」 버튼으로 받아요(PC를 켤 때와 새벽에도 받아요). 필요한 기능은 게시글 댓글로 알려 주세요

## 알아 둘 것

- AI(기본은 내 PC의 Claude Code)에는 할 일을 뽑을 때와 하루 마무리 글을 쓸 때만 보내요. 이때 넣은 글·사진, 내 할 일 목록, 오늘 한 줄이 가요. 회사 회의는 회사 보안 규정을 따르세요.
- 한 사람의 Claude Code 로그인으로 여러 명이 쓰는 공용 서버로 돌리지 마세요. 각자 PC·각자 로그인이 전제예요.
- 기록은 `data/` 폴더 하나(SQLite)에 있어요. 복사하면 백업이고, 지우면 처음 상태가 돼요. 음성·사진 원본은 글로 바꾼 뒤 지워요.

## 문서

- [docs/START.md](docs/START.md) — 설치 · 운영 안내 (그림 포함 한 파일: `docs/START.html`) · `docs/POSTER.html` — 소개 페이지
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 구조 · 결정 · 문서 지도(어느 문서가 무엇의 기준인지) · [docs/DESIGN.md](docs/DESIGN.md) — 설계
- [CLAUDE.md](CLAUDE.md) — Claude Code로 고치거나 더할 때 · [docs/MINUTES_FORMAT.md](docs/MINUTES_FORMAT.md) — 회의록 형식 · [docs/HANDOFF.md](docs/HANDOFF.md) — 남은 일 · [docs/ARCHIVE.md](docs/ARCHIVE.md) — 지난 기록

## 개발

```
pip install -r requirements-dev.txt
python -m pytest -q
```

| 위치 | 내용 |
|---|---|
| `server/app.py` | API와 날짜별 조회 규칙 |
| `server/extract.py` | 추출 지시문, 응답 해석, 회의록 |
| `server/llm.py` / `server/stt.py` | AI 호출(claude/codex/api/gpt/gemini/ollama/fake) / 음성 인식 |
| `server/transcript.py` | 화자 표기 해석 |
| `server/calsync.py` | 네이버·구글 캘린더 |
| `server/db.py` | SQLite 스키마와 `MIGRATIONS`(칸 추가) |
| `server/updater.py` | 자동 업데이트(git fast-forward → 필요 시 재설치) |
| `web/` | 화면 (빌드 없음, PWA). `app.js` 하나에 다 있다 |
| `tools/` | 켜기(`run.py`)·설치(`install.py`)·자동 시작(`autostart.py`)·켜기 전 업데이트(`update.py`)·`build_start_html.py`(시작 안내 HTML)·`shoot_screens.py`+`build_poster.py`(포스터용 실제 화면 캡처)·`cut_poster.py`(포스터를 게시판에 붙일 그림으로 자름)·`shoot_gif.py`(말하기→할 일 움직이는 그림)·`cut_board.py`(공모 게시글에 넣는 조각으로 자름, 설치 단추는 한 장씩) |
| `tests/` | pytest. AI·캘린더·업데이트는 흉내 서버/임시 git으로 시험. `tests/test_docs_sync.py`는 문서 속 경로·설정 이름·데이터 모델·5단계 이름이 맞는지 본다 |
| `.claude/skills/` · `.claude/agents/` | Claude Code 스킬 `meeting-minutes`(회의록 형식) · `harness-tidy`(CLAUDE.md와 스킬 정리), 검수 서브에이전트 `reviewer` |
