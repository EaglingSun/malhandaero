# 말한대로 핸드오프 (2026-11-10 저녁, 42판 기준)

다음 작업자(사람이든 Claude든)가 이 문서만 읽고 이어갈 수 있게 적는다.

## 1. 한 줄 요약

녹음·말·사진에서 "내가 챙길 일"을 뽑아 날짜별로 관리하는 개인 비서 웹앱. 각자 PC에 서버를 켜고 휴대폰으로 접속한다.
사내 공모 「2026 슬기로운 AI 생활」(접수 마감 **11/18**)에 본체로 응모하는 것이 당면 목표다.

## 2. 지금 어디에 무엇이 있나

| 무엇 | 어디 |
|---|---|
| 코드 최신판 | **GitHub `EaglingSun/malhandaero` (비공개), `main` 가지. 42판.** 이것이 기준이다 |
| 예전 묶음 | 프로젝트 문서 `claude/malhandaero-src-01.txt`~`07.txt`는 6판 소스 묶음. 저장소가 생겼으므로 더 쓰지 않는다 |
| 실행 중인 곳 | 사용자의 집 Mac(Tailscale https, 폰 2대) + 11/10부터 Windows 노트북(시험용, Gemini) |
| 개발 계획 문서 | claude.ai 아티팩트 「말한대로 개발 계획」 https://claude.ai/artifact/9hymSQQhmXfwhpuEw14dua (11/9 밤 기준. 그 뒤 추가분 미반영) |
| 홍보 페이지 | 아티팩트 「말한대로 소개 페이지」 https://claude.ai/artifact/CR8DdiWzVDDpbBLp258iqD (11/10 12:15 갱신: 하루 마무리·오늘 한 줄·달력·식물 카드, 캘린더 가져오기, 익명) |
| 설계서, 설치 안내 | `docs/DESIGN.md`, **`docs/START.md`(셋업 가이드 — INSTALL.md를 흡수, 44판)**, `README.md`. 회의록 형식은 `docs/MINUTES_FORMAT.md`(지시문·내보내기·스킬의 기준) |

### 코드 받는 법

`git clone https://github.com/EaglingSun/malhandaero.git` 한 줄이면 된다. 풀고 나서 `python -m pytest -q`가 82개 통과하면 온전한 것이다.

아래는 저장소가 없던 때 쓰던 소스 묶음 푸는 법이다(참고용).
프로젝트 문서 `claude/malhandaero-src-01.txt` ~ `-07.txt` 일곱 개를 한 폴더에 내려받은 뒤 그 폴더에서 실행한다.

```
python3 - <<'EOF'
import base64, glob, pathlib
src = "".join("\n" + pathlib.Path(f).read_text(encoding="utf-8").split("\n", 1)[1] for f in sorted(glob.glob("malhandaero-src-*.txt")))
for part in src.split("\n=====8<===== ")[1:]:
    head, _, body = part.partition("\n")
    path, b64 = (head[:-9], True) if head.endswith(" (base64)") else (head, False)
    p = pathlib.Path("malhandaero") / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(base64.b64decode(body) if b64 else body.encode("utf-8"))
EOF
chmod +x malhandaero/*.sh malhandaero/*.command
```

각 묶음의 첫 줄은 설명이고, 그 아래로 `=====8<===== 경로` 줄마다 파일 하나가 이어진다.
`(base64)`가 붙은 구획은 그림 파일과 `.bat`(CRLF 줄바꿈 유지)이다. 풀고 나서 `python -m pytest -q`가 35개 통과하면 온전한 것이다.

## 3. 구조 (자세한 것은 docs/DESIGN.md)

- `server/app.py` 주소(API)와 날짜별 조회 규칙 · `extract.py` 추출 지시문과 해석 · `transcript.py` 화자 표기 해석
- `server/llm.py` AI 연결: `claude`(이 PC의 Claude Code를 `claude -p`로 호출, 기본) | `api`(Anthropic 키) | `gemini`·`ollama`·`openai`(OpenAI 호환, urllib) | `fake`(흉내). 자동 감지 순서: Anthropic 키 → Claude Code → Gemini 키
- `server/calsync.py` 캘린더 자동 넣기: 네이버(CalDAV + 애플리케이션 비밀번호), 구글(OAuth)
- `server/stt.py` 음성 인식: faster-whisper(선택 설치) 또는 Gemini가 직접 들음(`stt.engine()`) · `server/db.py` SQLite와 칸 추가(MIGRATIONS)
- `web/` 빌드 없는 화면(PWA, 공유 받기) · `tools/install.py`, `tools/run.py` 설치와 실행
- `server/updater.py`(+ 얇은 `tools/update.py`) 자동 업데이트: `.git`이 없는 폴더면 먼저 저장소에 연결(adopt: init → fetch → checkout -f; data/·.env는 그대로) → `git fetch` → fast-forward만 → requirements 바뀌면 재설치 → manifest 바뀌면 폰 앱 재설치 안내. 실패해도 켜기는 막지 않는다. 세 곳에서 부른다: ① 켜기 전(`run.sh`/`run.bat`/`켜기.command`) ② 화면 맨 아래 「업데이트」(`POST /api/update`) ③ 매일 04시 자동. ②③은 받은 뒤 서버를 `RESTART_CODE(3)`로 끝내고 `tools/run.py`의 감시 루프가 새 코드로 다시 켠다. 자료·설정은 그대로
- `말한대로 처음 설치.command`(Mac) / `말한대로 처음 설치.bat`(Windows) 파일 하나로 clone → 설치 → 켜기. **bat는 ASCII만**
- 시험: `python -m pytest -q` → 82개 통과. AI·네이버·구글은 흉내 서버로, 업데이트는 임시 git 저장소로 시험한다

지키는 규칙

- 사람이 하는 일은 말하기·고르기·체크뿐. 캘린더 등 바깥 연결이 실패해도 할 일 저장은 막지 않는다.
- 화면과 안내 문구는 쉬운 한국어. 단, '업데이트'·'버전'처럼 누구나 아는 외래어는 억지로 바꾸지 않는다('새 판'은 어색하다는 의견). 못 한 일은 "못 했어요 + 사유"로 화면에 남긴다.
- 음성·사진 원본은 글로 바꾼 뒤 지운다. DB 칸을 더할 때는 `db.MIGRATIONS`에 적는다(사용자가 이미 자료를 쌓고 있다).
- 커밋 메시지 끝에 Claude 공동 저자 줄을 붙인다.

## 4. 실제 기기에서 확인된 것 / 안 된 것

확인됨 (사용자가 Mac + Android에서 직접)

- 설치·실행(Mac), Claude Code 연결로 실제 뽑기, "누구 일인지" 구분
- Tailscale https 주소, 말하기 버튼(https에서), 홈 화면 설치(앱 서랍에 들어감)
- 구글 캘린더 연결과 일정 자동 등록
- 브라우저의 "공유 → 더보기"에 말한대로가 나옴
- **삼성 녹음 앱의 텍스트 공유 → 더보기 목록에 말한대로가 나옴** (11/10 아침, 6판 manifest로 폰 앱 재설치 후). 공유해서 실제로 뽑히는지는 다음 확인
- 7판 폴더(`~/Downloads/malhandaero-main`) 첫 켜기: 저장소 자동 연결 → 설치 → 실행 됨

확인 안 됨 / 문제 있음

| 항목 | 상태 |
|---|---|
| 캘린더 일정 가져오기(20판) | 구글은 실기기 확인(팀 공유 일정 보임). 네이버 REPORT 응답 꼴은 미확인 |
| 네이버 캘린더 연결(남편 쪽) | 5판 이전에 "인터넷 연결 확인" 오류. 인증서 묶음(certifi) 지정으로 수정했으나 **실제 네이버 서버에서 미확인**. 실패하면 문구의 대괄호 안 사유를 받을 것 |
| 5판의 목록 중심 화면, QR 연결, 더블클릭 실행 | 헤드리스 브라우저와 자동 시험으로만 확인. 실제 기기 의견 아직 없음 |
| 음성 파일 변환 | Mac: whisper 미설치 상태(설치 때 실패) → Gemini 키 넣으면 됨(30판). Windows: whisper 켜짐. **Gemini로 m4a 변환은 11/10 오후 구글 503(수요 폭주)로 미확인** — 503 풀린 뒤 「다시 뽑기」 한 번이 남음 |
| Windows 설치·실행 | **11/10 실기기 통과** (Tailscale 없이 폰 설치도 통과: Chrome 플래그 예외 등록 → 「설치」 뜸, 캡처 docs/img): 처음 설치.bat → clone → install(whisper 포함) → run → QR → 폰 접속 → Claude Code로 추출 ✓. bat에 한글 있으면 cmd가 줄을 깨뜨림(ASCII로 수정). Gemini 추출은 모델명(2.5→3.8)·503 겪음 |
| Gemini 연결(28~31판) | 키·모델·주소는 통하나 **11/10 오후 내내 503**으로 성공 응답을 못 봄. **결정: 1차 배포는 Claude Code 연동판으로.** Gemini는 코드에 남기되 문서에서 '실험적'으로 내림 |
| 켠 채 새 판 받기(9판) | 샌드박스 e2e(원격에 커밋 → `/api/update` → 새 코드로 재시작)는 통과. 폰에서 「업데이트」 버튼으로 9→10판 적용 확인(11/10 08:40) |

## 5. 다음 할 일 (순서대로)

0. **11/11 할 일**: 공모 게시글 초안(3단계 체험: GIF → 스킬 → 설치, 수치 자리) · GIF 1개 · 저장소 공개 결정(전용 계정 이전) · Mac: 업데이트 + `.env` 구글 두 줄 삭제(내장으로 통일) + whisper 재설치 + 자동 시작.command
1. 사용자의 11/10 실사용 의견 받기 → 고치기. 새 기능보다 우선 (08:40 배치·요약 목록 의견 반영 끝)
1-2. 13판 회의록·묶음 추출을 실제 회의록(입력 12, 37k자)으로 다시 뽑아 품질 보기 → 묶음 수·회의록 충실도 의견 반영
1-1. ~~faster-whisper 설치~~ 17판. Mac은 whisper 미설치 → `말한대로 설치.command` 한 번 더(또는 녹음 변환은 선택 사항으로 두고 텍스트 공유만 안내). Gemini STT 실기기 확인은 보류
1-3. ~~Windows 설치 검증~~ 11/10 통과. ~~배포 안내 한 장~~ docs/START.md. ~~가명 치환~~ 32판
1-4. 저장소 공개 결정: 공모 전용 계정/조직으로 이전 후 public (익명 유지) — 사내 코드 공개 규정 확인 후. 공개 시 README·privacy.html의 저장소 주소 바꾸기
2. ~~녹음 앱 공유~~ 11/10 확인 끝: 공유 → 넣기 → 뽑기까지 됨
3. ~~첫 화면 회의 요약~~ 8판 → 10판에서 의견 반영(목록형 요약, 할 일 아래 제목만). 폰에서 다시 보기
4. ~~Mac 로그인 시 자동 시작(launchd)~~ 35판. Mac·Windows 실기기 확인 남음
5. 앱 알림(웹 푸시): 아침 "오늘 할 일 N건", 정한 시각 알림. 요구 R16의 남은 절반
6. 개인/회사 나눠 보기(요구 R12. 지금은 표시만)
7. 개발 계획 문서 갱신(Claude Code 연결, 캘린더 자동, QR, 목록 중심 화면, 자동 업데이트 추가분). 저장소 올리기는 끝남
8. 팀원 1~2명 시험 사용과 전/후 수치 측정(11/12~16) → 공모 게시글과 사용 안내(11/16~17)
9. 공모 이후: **구글 캘린더 원클릭 연결**(데스크톱 앱형 OAuth 클라이언트 내장 + PC localhost에서 연결 → 리디렉션 고정, 미검증 앱 경고 1회·테스트 사용자 100명) → **폰 전용 라이트판**(정적 PWA + Gemini 직접 호출, 녹음도 Gemini가 들음, IndexedDB; 가족·네이버 캘린더 없음; 2~3일) → 더하기(애드온) 틀 → 맡긴 일 챙김 → 회의 음성 화자 분리(pyannote 등). 공모 안내엔 "녹음 파일 변환은 선택, 녹음 앱 텍스트 공유가 기본 경로"로

## 6. 결정이 남은 것

- 응모 부문: ① 회의와 업무 기록(경쟁작 0건, 권장) vs ⑥ 업무 비서(11건)
- ~~동료가 써 볼 방법~~ 11/10 결정: **각자 PC + 본인 Claude Code 로그인**으로 안내. 사내에 Pro 이상 구독자가 많아 문제 없음(사용자 판단). 공용 서버 시험판은 두지 않는다
  (앱이 Claude 로그인을 직접 받지 않고, 각자 PC의 Claude Code를 부르는 방식만 쓴다. 공용 서버에서 한 사람 로그인으로 여러 명이 쓰게 하지 않는다)

## 7. 사용 환경 메모

- 시험 PC: Windows 노트북(`말한대로 처음 설치.bat`로 설치, Claude Code 있음). `.env`의 `MALHAN_AI=gemini`·`MALHAN_STT=gemini` 줄은 지워 Claude Code로 되돌릴 것. 사용자 '테스트'(코드 1234)는 시험용
- Tailscale 테일넷 `barreleye-neon.ts.net`. 회사 Windows: `https://sun-pc.barreleye-neon.ts.net` (11/10 회사망에서 열림 확인). 집 Mac: `https://todo.barreleye-neon.ts.net` (11/10 사용자 언급)
- 서버: 집 Mac. `말한대로 켜기.command`로 실행. Tailscale 켜져 있으면 https 주소 자동. 덮개를 닫으면 끊김
- 사용자 본인은 구글 캘린더(올리기: Sun 기본 캘린더, 읽기: '팀 공유 일정' 공유 캘린더), 남편은 네이버 캘린더로 연결하려 함
- 구글 OAuth 클라이언트는 사용자가 만들어 `.env`에 넣어 둠. 리디렉션 주소에 Tailscale 주소가 들어 있으므로 기기 이름을 바꾸면 구글 쪽도 고쳐야 함
- 판을 바꿀 때(7판부터): 그냥 켜면 된다. 켜기가 새 판을 받고 requirements가 바뀌었으면 설치도 다시 한다
- 집 Mac: 지금 도는 것은 `~/Downloads/malhandaero-main`(7판, 저장소 연결됨, data/·.env 옮김). `~/Downloads/malhandaero 6` 이하 예전 폴더들은 더 안 쓴다(지워도 됨)
- 화면이 예전 모양이면 새로고침. manifest가 바뀐 판(6판)은 휴대폰에서 앱 삭제 후 재설치

## 8. 판별 변경 요약

| 판 | 내용 |
|---|---|
| 1 | 뼈대: 글·사진 넣기, 자동 추출, 고르기, 날짜별 관리, 하루 정리, 화자 지정, 캘린더 내보내기, Claude Code 연결, 설치 스크립트 |
| 2 | 회의 요약, 누구 일인지(남의 일 가져오기), 한 번에 넣기, 고치기, 시각 표시, `--remote` |
| 3 | 네이버·구글 캘린더 자동 넣기 |
| 4 | 더블클릭 실행(.command), Tailscale 자동, QR 연결(내 기기 / 가족 초대) |
| 5 | 목록 중심 화면(+ 버튼 뒤에 넣기), https 인증서 묶음, 연결 실패 사유 표시 |
| 6 | 공유로 받는 파일 종류 확대 |
| 41 | 구글 캘린더 원클릭: 데스크톱형 OAuth 클라이언트를 앱에 내장(`calsync.BUILTIN_GOOGLE_CLIENT_ID/SECRET`, 값은 42판에 내장(사용자 프로젝트의 '데스크톱 앱' 클라이언트, 동의 화면은 프로덕션 게시·미검증). **11/10 Windows 실기기에서 localhost 연결 성공.** 주의: `.env`에 예전 웹 클라이언트 ID가 남아 있으면 그게 우선돼 `deleted_client`가 남 → 두 줄 지우기. 동의 화면 게시용 공개 페이지는 `eaglingsun.github.io/malhandaero/`(별도 저장소 `EaglingSun/eaglingsun.github.io`: index·privacy·terms)). 내장 클라이언트일 땐 리디렉션이 localhost만 되므로 `/api/calendar/google/start`가 localhost가 아니면 `/?cal=local`로 돌려보내고 화면이 'PC에서 localhost로 한 번' 안내. `.env`에 본인 클라이언트가 있으면 그쪽 우선(어느 주소에서나). INSTALL.md·START.md 갱신 |
| 40 | 출품 버전 UI 단순화: 「휴대폰 연결」→「휴대폰에서 쓰기」(폰 주소 + 복사 + QR 하나). 초대 QR·같은 와이파이용 QR·코드 바꾸기·Tailscale 도우미는 「가족이나 팀과 같이 쓰고 싶다면」 접힘 안에. 공유 기능은 남기되 안내에선 '가이드 참고'로만. START.md도 '혼자 쓰기가 기본'으로. 그 밖에: 코드 바꾸기 API(`/api/settings/code`), 초대 QR via=lan, INSTALL.md Tailscale 초대 절, 가족 코드는 본인이 정함 |
| 39 | 켜질 때 창을 단순하게(폰 주소 하나·PC 주소·상태 한 줄·QR). **설정 도우미 글**: `docs/prompts/google-calendar.md`·`tailscale.md`를 `/api/help/{topic}`이 이 PC 값(주소·폴더·OS·리디렉션 URI)으로 채워 돌려줌 → 앱의 구글 칸·휴대폰 연결 칸의 「설정 도우미 글 복사」 → Claude/ChatGPT에 붙여넣어 한 단계씩 안내받음. 그 밖에 36~38판: 넣기 창 2×2, 캐시 버전, 매시간 새 버전 띠, Chrome으로 열기 띠, http 예외 등록 안내 |
| 38 | 업데이트 자동화: 한 시간마다 `git fetch`로 새 버전 확인(`_check_remote` → `UPDATE_AVAILABLE`, `/api/me`의 `update`) → 화면 아래 「새 버전이 있어요 · 지금 적용」 띠. `MALHAN_AUTO_UPDATE=now`면 처리 중 녹음 없을 때 즉시 자동 적용. 「업데이트」 버튼은 받을 게 없어도 직접 고친 코드가 있으면 재시작(`RESULT.local`). START.md에서 '같이 개발' 문단 제거, '새 버전은 알아서 와요'로 |
| 37 | `CLAUDE.md`(Claude Code가 폴더를 열면 읽는 개발 안내: 구조·규칙·시험·공유 방법·자동 업데이트와의 관계). 화면 파일 캐시 수정(index가 `?v=커밋` 부착, css·js no-cache). 넣기 창을 「직접 적기」/「AI가 대신 적어요」 2×2 타일로(36판) |
| 35 | 자동 시작 `tools/autostart.py install|remove|status`: Mac은 `~/Library/LaunchAgents/com.malhandaero.server.plist`(RunAtLoad+KeepAlive, `sh run.sh` 실행 → 업데이트 확인·caffeinate 포함, PATH에 claude 경로 포함, 로그 `data/server.log`), Windows는 시작 프로그램 폴더의 `말한대로.bat`(run.bat 최소화 창). 래퍼 `말한대로 자동 시작(해제).command`, `autostart.bat`. **실기기 미확인.** 쓰는 모양 세 가지(집 상시 서버 / +가족 / 회사 PC 근무 중)를 START.md에 정리 |
| 34 | 서버 이름(`MALHAN_LABEL`, 비우면 Mac/Windows): `/manifest.webmanifest`를 동적으로 내어 앱 이름을 「말한대로 · 집」처럼 붙임 → 한 폰에 서버 둘(집 Mac·회사 Windows)을 각각 앱으로 설치·구분. `/api/me`의 `label`, 화면 아래에 표시. **이름을 바꾸거나 처음 적용할 땐 폰에서 앱을 다시 설치**해야 홈 화면 이름이 바뀜 |
| 33 | AI 연결 확대: `codex`(이 PC의 Codex CLI `codex exec -s read-only -o 파일 -`, ChatGPT 구독, 사진은 `-i`), `gpt`(OpenAI API, 기본 gpt-5.4-mini, temperature 안 보냄). 자동 감지: Anthropic 키 → Claude Code → Codex → OPENAI_API_KEY → GEMINI_API_KEY. **AI 없음 모드**: 넣기 창에서 말하기·글·파일을 감추고 안내, 직접 적기·캘린더·하루 마무리(규칙 요약)는 그대로, 공유로 들어온 글은 `failed`+사유로 보관(연결 뒤 「다시 뽑기」) |
| 32 | 공개 준비: 문서·테스트·프롬프트 예시의 실명을 가명(무당이·슈구리, 팀 공유 일정)으로, privacy.html 문의를 Issues로. `docs/START.md` 배포 안내 한 장(준비물 → A 집 안 → B Tailscale → 쓰는 법 → 막히면). Gemini 503/429 재시도·예비 모델, reasoning_effort low, HTTP 제한 10분, 서버 창 `[llm]`/`[stt]` 시간 기록 |
| 31 | Gemini 기본 모델 `gemini-3.8-flash`(2.5-flash는 신규 사용자 불가 — Windows 실기기 404로 확인). 404에 "use models/X"가 오면 X로 한 번 자동 재시도(`llm.suggested_model`, stt `_ModelGone`). `.env.example`을 [1] Claude Code / [2] Gemini / [3] 그 밖에 + STT + 기타로 재구성, install.py의 .env 틀도 같은 꼴 |
| 30 | 녹음 파일을 Gemini가 직접 듣는 STT(`stt.engine()`: whisper 있으면 whisper, 없고 GEMINI_API_KEY 있으면 gemini, `MALHAN_STT`로 고정). ≤18MB inline_data, 넘으면 File API resumable 업로드 → ACTIVE 대기 → file_data. 화자 구분 시도('화자1:'). `MALHAN_GEMINI_STT_MODEL`. 혼자 쓰는 폰 전용 라이트판의 핵심 가정(오디오→Gemini) 검증용 |
| 29 | Windows 대비: `말한대로 처음 설치.bat`(git clone→install→run), bat 전부 **ASCII만**(chcp 뒤 멀티바이트가 있으면 cmd가 줄을 깨뜨림 — Windows 실기기에서 확인) + `chcp 65001`+`PYTHONUTF8=1`+CRLF(.gitattributes), `.env` utf-8-sig(메모장 BOM), Tailscale `Program Files` 경로 탐지, install.py .env 틀에 GEMINI_API_KEY 안내·방화벽 안내. **실기기 검증 전** |
| 28 | 구독 없는 사람용 AI 연결: `MALHAN_AI=gemini`(GEMINI_API_KEY, 기본 gemini-2.5-flash, 키만 있으면 자동 감지) · `ollama`(localhost:11434, 기본 qwen3:8b, `<think>` 제거) · `openai`(OpenAI 호환 아무 서버). `llm._run_openai` — 표준 라이브러리 urllib로 chat/completions, 사진 읽기는 image_url data URL. 오류 문구 읽기 좋게(키 틀림·한도·모델 없음·Ollama 꺼짐). INSTALL.md 「Claude 구독이 없다면」 표 |
| 27 | 「달력」 탭(`GET /api/month?ym=`): 날마다 마친·남은 수, 기분 이모지, 마무리 여부, 하루 점수 0~5(넣음 1 · 마침 1/3건부터 2 · 마무리 1 · 한 줄 1 — `day_score`). 이달 활용 지수(지난 날 점수 합 ÷ 만점, 0~100), 함께한 날, 연속 일수, 마친·남은 합계. 칸을 누르면 그날 「오늘」로. `.env`의 `MALHAN_POST_URL`을 정하면 「공모 글에 좋아요 누르러 가기」 버튼(`/api/me`·`/api/month`의 `post_url`). 할 일의 캘린더 태그 클래스 `cal`→`synced`(설정 상자 `.cal` 스타일과 충돌해 태그가 늘어나던 문제) |
| 26 | 「오늘 한 줄」(쓰고 싶은 사람만): 하루 마무리 카드의 「오늘 한 줄도 남길래요」로 켬(`POST /api/settings/diary`, `addon_settings` addon='diary', `/api/me`의 `diary`). 기분 이모지 5개(다시 누르면 해제) + 문구 칩(누르면 입력칸에 덧붙임) + 직접 입력(≤200자). `POST /api/day/note?date=` → `day_logs.note/mood`(마무리 글이 없어도 저장, 마무리를 써도 유지). `/api/day`에 `note`, `mood`. 「오늘은 여기까지」 때 `summary_prompt(..., note)`로 들어가 마무리 글에 사실대로 한 문장 녹임(이모지는 글에 안 넣음). 한 일이 없어도 한 줄만 있으면 마무리 가능 |
| 25 | 「중복 일정 정리」 제거(일회성, 수동 정리로). 캘린더 태그는 글자만(✓ 그림이 폰에서 엉뚱한 자리에 그려짐). 「하루 정리 / 정리해 줘」 → 「하루 마무리 / 오늘은 여기까지 / 마무리 다시 쓰기」 |
| 24 | 일정 중복 원인 수정: ① 연결 끊기가 할 일의 일정 번호를 지워 재연결 시 전부 다시 올라가던 것 → 끊어도 번호 보관(종류가 바뀔 때만 끊음) ② 올릴 캘린더를 같은 것으로 골라도 다시 올리던 것 → 실제로 바뀔 때만, 예전 캘린더에서 지우고 새 데로 옮김 ③ ~~중복 일정 정리~~ 25판에서 제거. 네이버는 UID가 항목 번호라 PUT이 덮어써 중복이 안 생김 |
| 23 | 올릴 캘린더 선택(`POST /api/calendar/target`; 구글 write_calendar_id, 네이버 calendar_url. 바꾸면 예전 cal_ref를 끊고 앞으로 할 일을 새 캘린더에 올림). 캘린더 일정 「숨기기 / 다시 보기」(`calendar_hidden` 표, `/api/calendar/events/hide|unhide`) |
| 22 | 내가 올린 일정이 「캘린더 일정」에 되돌아오던 문제(설명이 근거 문장이면 표식이 없었음): 할 일의 cal_ref와 대조해 거르고, 구글엔 extendedProperties.private.malhandaero 표식. 동기화된 할 일 카드에 「캘린더 ✓」 태그(가져온 것은 「캘린더에서」) |
| 21 | 읽는 캘린더 선택: 「캘린더 연결」에 "일정을 가져올 캘린더" 목록(구글 calendarList, 네이버 캘린더 목록). 올리는 캘린더는 그대로. 구글은 `calendarlist.readonly` 권한이 추가돼 **기존 연결은 구글을 한 번 다시 연결해야 목록이 보임** (`/api/calendar/sources`, `/api/calendar/source`) |
| 20 | 캘린더 → 할 일: 연결된 캘린더의 그날 일정을 「캘린더 일정」으로 보여 주고 「할 일로」 한 번에 가져옴(`GET /api/calendar/events`, `POST /api/calendar/events/import`). 가져온 할 일은 `addon='calendar'`+`cal_ref`로 원본 일정을 가리키되 **캘린더 쪽은 건드리지 않음**(고쳐도·지워도). 말한대로가 넣은 일정·취소 일정은 목록에서 제외. 네이버 REPORT, 구글 events.list. 실제 서버 미확인 |
| 19 | 수치 집계 `GET /api/stats?days=30`(넣은 것 수·종류, 넣고 목록까지 중앙값 초, 뽑힌 내 일·안 함 비율·맡긴 일·직접 적음·회의당 내 일). 넣은 것 탭 맨 아래 한 줄. `inputs.done_at` 칸 추가 — 공모 글 수치(DESIGN 10장)는 여기서 뽑는다 |
| 18 | 음성 파일 입력은 화자 분리가 없음을 전제로: 지시문에 1인칭 다짐만 me, 부탁·지시는 other. 넣은 것 상세에 안내 한 줄. 회의는 녹음 앱 텍스트 공유 권장. 화자 분리(diarization)는 로드맵 |
| 17 | 음성 인식(faster-whisper)을 설치 3/4단계에 포함(`requirements-stt.txt`, 모델 미리 받기, 실패해도 설치는 계속). 업데이트가 stt 묶음·install.py 변경 시에도 재설치. `MALHAN_STT=0`로 뺌 |
| 16 | 처리 중 자동 새로고침에 펼친 카드가 닫히던 문제(펼침 상태 기억·복원, 넣은 것 상세 유지). 처리 중 문구를 앱 말투로("꼼꼼히 듣고 정리하는 중이에요 ☕ 긴 회의는 몇 분"). `docs/MINUTES_FORMAT.md`(회의록 표준 형식), `skills/meeting-minutes/SKILL.md`(Claude Code 스킬) |
| 15 | Claude Code 모델 선택: 지시문 1만 자 초과(회의록)는 `--model opus`, 짧은 글은 Claude Code 기본. `MALHAN_CLAUDE_MODEL(_LONG)`, `MALHAN_LONG_CHARS`. 「처음부터 다시 뽑기」 |
| 14 | 회의록 v2: 참석자·안건·다음 일정, 결정 모음, 대화 중계체 금지·주제당 3~5줄. 「모두 안 함」 한 번에 + 되돌리기(`/api/items/restore`) |
| 13 | 회의록 구조화: 추출이 `minutes`(주제별 논의·결정, 확인할 것)와 `details`(상위 할 일의 세부)를 함께 냄. 조각 12k→60k자(회의 1~2시간을 한 번에). 내 일 ≤5건 묶기, 이름 붙은 일은 `other`. 화면: 들은 이야기 ▸ 회의록·맡긴 일, 「회의록 복사 / 파일로 받기」(`/api/inputs/{id}/minutes.md`), 「모두 안 함」(`/api/items/skip-all`). DB 칸 inputs.minutes, items.details |
| 12 | 업데이트 재시작이 처리 중 녹음을 끊던 문제: ① 켤 때 '처리 중'에 멈춘 입력을 처음부터 다시 돌림(`resume_pending`) ② 처리 중이면 업데이트 후 바로 끄지 않고 끝난 뒤 다시 켬(`_restart_when_idle`) |
| 11 | 문구: '새 판' → '업데이트'/'버전' (사용자 의견: '새 판 확인'이 어색함) |
| 10 | 사용자 의견: 요약을 줄글 → 항목 목록('- ' 줄, 예전 줄글은 화면에서 문장 단위로 나눔). 「들은 이야기」를 할 일 목록 아래·하루 정리 위로 옮기고 제목만 한 줄씩 |
| 9 | 켠 채로 새 판 받기: 화면 「새 판 확인」 버튼 + 매일 04시 자동 확인 → 받으면 스스로 다시 켬(`tools/run.py` 감시 루프). 판 번호 표시. updater를 `server/`로 이동 |
| 8 | 첫 화면에 「들은 이야기 요약」(그날 넣은 회의·통화 요약, 접힌 한 줄 → 누르면 펼침, 넣은 것으로 이동). `/api/day`에 `briefs` |
| 7 | GitHub 저장소에 올림. 켤 때 자동 업데이트(`tools/update.py`, 압축 폴더 자동 연결 포함), `말한대로 처음 설치.command`, privacy.html, 업데이트 시험 5개 |
