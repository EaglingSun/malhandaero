# 말한대로

> 말만 하세요. 기억은 제가 할게요.

통화·회의 녹음, 말로 한 메모, 사진에서 **내가 챙길 일**을 뽑아 날짜별로 관리하는 개인 비서 앱.
**PC**는 켜 두는 서버, **쓰는 건 폰**. AI는 내 PC에 로그인된 Claude Code를 그대로 쓰고(API 키 없음), 기록은 내 PC 밖으로 나가지 않아요.

## 설치 — 파일 하나만 받으세요

| | 받을 파일 | 하면 |
|---|---|---|
| **Windows** | [setup-windows.bat](https://github.com/EaglingSun/malhandaero/releases/download/v1.0.0/setup-windows.bat) | 더블클릭 → `C:\Users\이름\malhandaero`에 설치, 바탕 화면에 「말한대로 켜기」 |
| **Mac** | [setup-mac.command](https://github.com/EaglingSun/malhandaero/releases/download/v1.0.0/setup-mac.command) | 우클릭 → 열기 → 설치 뒤엔 `start.command` |

그다음은 **[셋업 가이드](docs/START.md)** 5단계(15분): PC 설치 → 구글 캘린더 → 폰에 앱으로 설치 → 할 일 넣기 → (선택) 집 밖에서도. 막힐 때·가족·팀과 같이 쓸 때·캘린더 상세도 같은 문서 뒷부분에 있어요. 앱 안에서는 바닥의 「시작 안내」.

Claude 구독(Pro 이상)이 없어도 할 일 관리 앱으로 그대로 써요. 다양한 AI 연결(Codex·GPT·Gemini 등)은 다음 버전에서.

## 되는 것

- **+ → 말하기** · 녹음 앱의 **텍스트 변환본 공유** → 할 일 + 회의록(논의·결정·확인할 것)
- 글 붙여넣기 · 텍스트 파일 · 사진 · AI 없이 직접 적기
- **오늘 · 나중 · 안 함** 하나만 누르면 끝. 못 끝낸 일은 다음 날로
- 하루 끝에 「오늘은 여기까지」 → 정리 글 · 오늘 한 줄 · **달력**
- **구글·네이버 캘린더** 양방향 · 폰 홈 화면 앱 · 공유 목록 등장
- 새 버전은 알아서. 필요한 기능은 게시글 댓글로

## 알아 둘 것

- 넣은 글과 사진은 챙길 것을 뽑을 때 AI(기본은 내 PC의 Claude Code)로 보내요. 회사 회의는 회사 보안 규정을 따르세요.
- 한 사람의 Claude Code 로그인으로 여러 명이 쓰는 공용 서버로 돌리지 마세요. 각자 PC·각자 로그인이 전제예요.
- 기록은 `data/` 폴더 하나(SQLite). 복사하면 백업, 지우면 초기화. 음성·사진 원본은 글로 바꾼 뒤 지워요.

## 문서

- [docs/START.md](docs/START.md) — 셋업 가이드 (그림 포함 한 파일: `docs/START.html`)
- [docs/DESIGN.md](docs/DESIGN.md) — 설계 · [docs/MINUTES_FORMAT.md](docs/MINUTES_FORMAT.md) — 회의록 형식 · [CLAUDE.md](CLAUDE.md) — Claude Code로 고치거나 더할 때 · [docs/HANDOFF.md](docs/HANDOFF.md) — 작업 이력

## 개발

```
pip install -r requirements-dev.txt
python -m pytest -q
```

| 위치 | 내용 |
|---|---|
| `server/app.py` | API와 날짜별 조회 규칙 |
| `server/extract.py` | 추출 지시문, 응답 해석, 회의록 |
| `server/llm.py` / `server/stt.py` | AI 호출 / 음성 인식 |
| `server/calsync.py` | 네이버·구글 캘린더 |
| `server/updater.py` | 자동 업데이트(git fast-forward → 필요 시 재설치) |
| `web/` | 화면 (빌드 없음, PWA) |
| `tools/` | 켜기·설치·자동 시작·`build_start_html.py` |
| `.claude/skills/meeting-minutes` | 회의록 형식의 Claude Code 스킬 |
