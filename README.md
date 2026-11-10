# 말한대로

> 말만 하세요. 기억은 제가 할게요.

녹음·말·사진에서 **내가 챙길 일**을 뽑아 날짜별로 관리해 주는 개인 비서 앱입니다.
내 PC에 켜 두고 폰으로 씁니다. AI는 내 PC의 Claude Code가 직접 부르고, 기록은 내 PC 밖으로 나가지 않아요.

## 설치 — 파일 하나만 받으세요

| | 받을 파일 | 하면 |
|---|---|---|
| **Windows** | [말한대로 처음 설치.bat](https://raw.githubusercontent.com/EaglingSun/malhandaero/main/%EB%A7%90%ED%95%9C%EB%8C%80%EB%A1%9C%20%EC%B2%98%EC%9D%8C%20%EC%84%A4%EC%B9%98.bat) (링크 우클릭 → 다른 이름으로 저장) | 더블클릭 → `C:\Users\이름\malhandaero`에 설치, 바탕 화면에 「말한대로 켜기」 바로가기 |
| **Mac** | [말한대로 처음 설치.command](https://raw.githubusercontent.com/EaglingSun/malhandaero/main/%EB%A7%90%ED%95%9C%EB%8C%80%EB%A1%9C%20%EC%B2%98%EC%9D%8C%20%EC%84%A4%EC%B9%98.command) (링크 우클릭 → 다른 이름으로 저장) | 우클릭 → 열기 → 설치 뒤엔 `말한대로 켜기.command` |

준비물은 Python·Git·**Claude Code(Pro 이상 구독)** 세 가지. 처음부터 끝까지는 **[docs/START.md](docs/START.md)** 한 장을 따라 하면 돼요(설치 10분 → 폰에 앱으로 넣기 3분).
이 목록의 나머지 파일은 설치가 알아서 쓰는 것들이라 따로 받을 필요 없어요.

**Claude 구독이 없어도** 설치하면 **할 일 관리 앱으로 그대로 써요** — 직접 적기, 오늘·나중·안 함, 캘린더 연결, 하루 마무리, 달력, 폰 앱 설치까지 전부. 녹음·글에서 AI가 대신 뽑아 주는 것만 쉬고, 나중에 Claude Code를 로그인하면 그때부터 바로 돼요.

## 되는 것

- **+ → 말하기**: 말한 것이 할 일로
- 녹음 앱의 **텍스트 변환본을 「공유」** → 할 일 + **회의록**(주제별 논의·결정·확인할 것). 복사하거나 .md로 받기
- 글 붙여넣기 · 텍스트 파일 · 사진으로 넣기, AI 없이 **직접 적기**
- 뽑힌 할 일은 **오늘 · 나중 · 안 함** 하나만 누르면 끝. 못 끝낸 일은 다음 날로 넘어감
- 하루 끝에 「오늘은 여기까지」 → 정리 글, 오늘 한 줄(기분·메모). **달력**에서 지난날 돌아보기
- **캘린더 연결**(구글 버튼 하나 · 네이버): 날짜 정한 일은 올리고, 회의는 가져오기
- 폰 홈 화면에 앱으로 설치, 공유 목록에 등장
- **새 버전은 알아서**: 켤 때·새벽에 받고, 그 사이 나오면 화면에 「지금 적용」 띠

## AI 연결

`.env`의 `MALHAN_AI`로 고르거나, 비워 두면 되는 것을 씁니다(`server/llm.py`).

| 방식 | 조건 | 비용 |
|---|---|---|
| `claude` **(기본)** | 이 PC에 Claude Code 설치·로그인 | 본인 구독 안에서 |
| `codex` | ChatGPT 구독 + Codex CLI 로그인 | 본인 구독 안에서 |
| `api` / `gpt` / `gemini` / `ollama` | `.env`에 키 또는 로컬 모델 (실험적) | 쓴 만큼 / 없음 |
| 없음 | — | 직접 적기·캘린더·하루 마무리는 그대로, 뽑기만 쉼 |

각자 자기 PC에서 자기 로그인으로 쓰는 것이 전제입니다. 한 사람의 로그인으로 여러 사람이 쓰는 공용 서버로 돌리지 마세요.

## 더 알아보기

- [docs/START.md](docs/START.md) — 한 장 안내 (설치 → 폰 → 캘린더 → 막히면)
- [INSTALL.md](INSTALL.md) — 자세한 설치, 집 밖에서 쓰기(Tailscale), 가족·팀원 폰 들이기, 안 될 때
- [docs/DESIGN.md](docs/DESIGN.md) — 설계 · [CLAUDE.md](CLAUDE.md) — Claude Code로 고치거나 더할 때

## 알아 둘 것

- 녹음 글과 사진은 챙길 것을 뽑을 때 AI(기본은 내 PC의 Claude Code)로 보냅니다. 회사 회의는 회사 보안 규정을 따르세요.
- 음성·사진 원본은 글로 바꾼 뒤 지웁니다. 글은 「넣은 것」에서 직접 지울 때까지 남습니다.
- 자료는 `data/` 폴더의 SQLite 파일 하나. 이 폴더를 복사하면 백업, 지우면 초기화. 업데이트는 `data/`·`.env`를 건드리지 않아요.

## 개발

```
pip install -r requirements-dev.txt
python -m pytest -q
```

| 위치 | 내용 |
|---|---|
| `server/app.py` | API와 날짜별 조회 규칙 |
| `server/extract.py` | 추출 지시문, 응답 해석, 회의록 |
| `server/llm.py` / `server/stt.py` | AI 호출 / 음성 인식 (바꿀 때 이 파일만) |
| `server/calsync.py` | 네이버·구글 캘린더 |
| `server/updater.py` | 자동 업데이트(git fast-forward → 필요 시 재설치) |
| `web/` | 화면 (빌드 없음, PWA) |
| `tools/` | 켜기·설치·자동 시작 |
| `docs/MINUTES_FORMAT.md` | 회의록·할 일 형식 기준. `skills/meeting-minutes`는 같은 형식의 Claude Code 스킬 |
