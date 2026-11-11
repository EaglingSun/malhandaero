# 말한대로 지난 기록

지금 개발에 꼭 필요하지는 않지만 남겨 두는 기록이다. 끝난 일, 판별 변경, 적을 때의 환경 메모를 모은다.
적을 때의 사실이라 지금과 다를 수 있다. 지금 상태는 `docs/HANDOFF.md`와 `docs/handoffs/`의 최신 파일, 결정은 `docs/ARCHITECTURE.md` 5절.
다른 문서에서 덜어낸 내용은 여기 끝에 날짜와 함께 덧붙인다. 이 문서는 줄이거나 다듬지 않는다.

## 1. 판별 변경 요약 (41판까지. 그 뒤는 `git log`)

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

## 2. 끝난 일과 확인된 것 (2026-11-10 저녁까지)

확인됨 (사용자가 Mac + Android에서 직접)

- 설치·실행(Mac), Claude Code 연결로 실제 뽑기, "누구 일인지" 구분
- Tailscale https 주소, 말하기 버튼(https에서), 홈 화면 설치(앱 서랍에 들어감)
- 구글 캘린더 연결과 일정 자동 등록
- 브라우저의 "공유 → 더보기"에 말한대로가 나옴
- **삼성 녹음 앱의 텍스트 공유 → 더보기 목록에 말한대로가 나옴** (11/10 아침, 6판 manifest로 폰 앱 재설치 후). 공유해서 실제로 뽑히는지는 다음 확인
- 7판 폴더(`~/Downloads/malhandaero-main`) 첫 켜기: 저장소 자동 연결 → 설치 → 실행 됨

| 항목 | 상태 |
|---|---|
| Windows 설치·실행 | **11/10 실기기 통과** (Tailscale 없이 폰 설치도 통과: Chrome 플래그 예외 등록 → 「설치」 뜸, 캡처 docs/img): 처음 설치.bat → clone → install(whisper 포함) → run → QR → 폰 접속 → Claude Code로 추출 ✓. bat에 한글 있으면 cmd가 줄을 깨뜨림(ASCII로 수정). Gemini 추출은 모델명(2.5→3.8)·503 겪음 |
| Gemini 연결(28~31판) | 키·모델·주소는 통하나 **11/10 오후 내내 503**으로 성공 응답을 못 봄. **결정: 1차 배포는 Claude Code 연동판으로.** Gemini는 코드에 남기되 문서에서 '실험적'으로 내림 |
| 켠 채 새 판 받기(9판) | 샌드박스 e2e(원격에 커밋 → `/api/update` → 새 코드로 재시작)는 통과. 폰에서 「업데이트」 버튼으로 9→10판 적용 확인(11/10 08:40) |

끝난 할 일

- 1-1. ~~faster-whisper 설치~~ 17판. Mac은 whisper 미설치 → `말한대로 설치.command` 한 번 더(또는 녹음 변환은 선택 사항으로 두고 텍스트 공유만 안내). Gemini STT 실기기 확인은 보류
- 1-3. ~~Windows 설치 검증~~ 11/10 통과. ~~배포 안내 한 장~~ docs/START.md. ~~가명 치환~~ 32판
- 1-4. ~~저장소 공개 결정~~ 저장소는 지금 공개 상태다(11/10 밤 확인). 아래는 공개 전에 적은 계획: 공모 전용 계정/조직으로 이전 후 public (익명 유지) — 사내 코드 공개 규정 확인 후. 공개 시 README·privacy.html의 저장소 주소 바꾸기
- 2. ~~녹음 앱 공유~~ 11/10 확인 끝: 공유 → 넣기 → 뽑기까지 됨
- 3. ~~첫 화면 회의 요약~~ 8판 → 10판에서 의견 반영(목록형 요약, 할 일 아래 제목만). 폰에서 다시 보기
- 4. ~~Mac 로그인 시 자동 시작(launchd)~~ 35판. Mac·Windows 실기기 확인 남음
- ~~동료가 써 볼 방법~~ 11/10 결정(`docs/ARCHITECTURE.md` 5절 D-01): **각자 PC + 본인 Claude Code 로그인**으로 안내. 사내에 Pro 이상 구독자가 많아 문제 없음(사용자 판단). 공용 서버 시험판은 두지 않는다
  (앱이 Claude 로그인을 직접 받지 않고, 각자 PC의 Claude Code를 부르는 방식만 쓴다. 공용 서버에서 한 사람 로그인으로 여러 명이 쓰게 하지 않는다)

## 3. 사용 환경 메모 (2026-11-10 저녁)

파일 이름은 적을 때의 이름이다. 지금은 `말한대로 처음 설치.bat` → `setup-windows.bat`, `말한대로 처음 설치.command` → `setup-mac.command`, `말한대로 켜기.command` → `start.command`.

- 시험 PC: Windows 노트북(`말한대로 처음 설치.bat`로 설치, Claude Code 있음). `.env`의 `MALHAN_AI=gemini`·`MALHAN_STT=gemini` 줄은 지워 Claude Code로 되돌릴 것. 사용자 '테스트'(코드 1234)는 시험용
- Tailscale 테일넷 `barreleye-neon.ts.net`. 회사 Windows: `https://sun-pc.barreleye-neon.ts.net` (11/10 회사망에서 열림 확인). 집 Mac: `https://todo.barreleye-neon.ts.net` (11/10 사용자 언급)
- 서버: 집 Mac. `말한대로 켜기.command`로 실행. Tailscale 켜져 있으면 https 주소 자동. 덮개를 닫으면 끊김
- 사용자 본인은 구글 캘린더(올리기: Sun 기본 캘린더, 읽기: '팀 공유 일정' 공유 캘린더), 남편은 네이버 캘린더로 연결하려 함
- 구글 OAuth 클라이언트는 사용자가 만들어 `.env`에 넣어 둠. 리디렉션 주소에 Tailscale 주소가 들어 있으므로 기기 이름을 바꾸면 구글 쪽도 고쳐야 함
- 판을 바꿀 때(7판부터): 그냥 켜면 된다. 켜기가 새 판을 받고 requirements가 바뀌었으면 설치도 다시 한다
- 집 Mac: 지금 도는 것은 `~/Downloads/malhandaero-main`(7판, 저장소 연결됨, data/·.env 옮김). `~/Downloads/malhandaero 6` 이하 예전 폴더들은 더 안 쓴다(지워도 됨)
- 화면이 예전 모양이면 새로고침. manifest가 바뀐 판(6판)은 휴대폰에서 앱 삭제 후 재설치

## 4. 그 밖

| 무엇 | 어디 |
|---|---|
| 예전 묶음 | 프로젝트 문서 `claude/malhandaero-src-01.txt`~`07.txt`는 6판 소스 묶음. 저장소가 생겼으므로 더 쓰지 않는다 |
| 실행 중인 곳 | 사용자의 집 Mac(Tailscale https, 폰 2대) + 11/10부터 Windows 노트북(시험용, Gemini) |
| 개발 계획 문서 | claude.ai 아티팩트 「말한대로 개발 계획」 https://claude.ai/artifact/9hymSQQhmXfwhpuEw14dua (11/9 밤 기준. 그 뒤 추가분 미반영) |

`git clone https://github.com/EaglingSun/malhandaero.git` 한 줄이면 된다. 풀고 나서 `pip install -r requirements-dev.txt` 뒤 `python -m pytest -q`가 실패 없이 끝나면 온전한 것이다
(2026-11-10 밤 Windows 기준 83개 통과 · 5개 건너뜀 — 건너뛰는 5개는 sh 흉내 실행 파일을 쓰는 시험이라 Mac·Linux에서만 돈다).
저장소가 없던 때의 소스 묶음(6판) 푸는 법은 더 쓰지 않아 뺐다. 필요하면 이 파일의 git 이력에 있다.

홍보 페이지의 원본 기록 (옛 HANDOFF 2절, 2026-11-10): 아티팩트 「말한대로 소개 페이지」 https://claude.ai/artifact/CR8DdiWzVDDpbBLp258iqD (11/10 12:15 갱신: 하루 마무리·오늘 한 줄·달력·식물 카드, 캘린더 가져오기, 익명). 지금 기준은 저장소의 `docs/POSTER.html`이다.

단계 기록 (`docs/DESIGN.md` 9장에서 옮김, 2026-11-10)

| 단계 | 내용 | 상태 |
|---|---|---|
| M0~M3 | 뼈대, 추출, 날짜 관리, 화자 지정, 하루 정리, 음성 변환, 말하기, PWA·공유, 로그인 코드 | 완료 |
| 배포 준비 | 캘린더(구글 원클릭·네이버), 자동 업데이트, 설치 파일 하나(Windows/Mac), 폰 http 설치 경로, 달력·오늘 한 줄, PC 화면, 셋업 가이드 | 완료 (11/10 1차 배포, 릴리스 v1.0.0) |

`docs/START.md`에서 덜어낸 안내 (2026-11-11, 분량 줄이기 — 꼭 필요한 셋업과 주의사항만 남김). 내용은 덜어낼 때 기준으로 맞는 것이다.

- ④ 하루 마무리: 하루를 마칠 땐 「오늘은 여기까지」를 누르고, 지난날은 「달력」에서 봐요.
- 캘린더: 「일정을 가져올 캘린더」에서 공유 캘린더 등 다른 캘린더를 고를 수 있어요(올리는 캘린더는 그대로). 안 볼 일정은 「숨기기」를 눌러요. 같은 와이파이의 `http://10.x…` 주소로는 구글이 연결을 받지 않아요.
- 본인 구글 클라이언트 6단계(START에는 한 문단으로 줄여 남김): ① console.cloud.google.com에서 프로젝트 ② API 및 서비스 → 라이브러리에서 "Google Calendar API" 사용 ③ OAuth 동의 화면: 외부, 앱 이름 "말한대로", 앱 게시로 프로덕션 ④ 사용자 인증 정보 → OAuth 클라이언트 ID(웹 애플리케이션) ⑤ 승인된 리디렉션 URI에 `http://localhost:8000/api/calendar/google/callback`과 `https://내PC이름.○○○.ts.net/api/calendar/google/callback` ⑥ `.env`에 `MALHAN_GOOGLE_CLIENT_ID=…`, `MALHAN_GOOGLE_CLIENT_SECRET=…`을 적고 다시 켜기.
- 업데이트: 안 받으려면 `tools\run.bat --no-update`. 보자마자 바로 적용하게 하려면 `.env`에 `MALHAN_AUTO_UPDATE=now`.
- PC가 두 대일 때: PC 두 대(집·회사)면 각 `.env`에 `MALHAN_LABEL=집` / `MALHAN_LABEL=회사` → 폰에 「말한대로 · 집」「말한대로 · 회사」 두 앱으로 나란히 깔려요.
- 안 될 때: 뽑힌 내용이 엉뚱해요 → `.env`에 `MALHAN_AI=fake`가 있으면 흉내 모드. 지우고 다시 켜요. / "8000번 포트를 쓰는 중" → 이미 켜져 있어요. 열린 창을 쓰거나 닫고 다시 켜요.
