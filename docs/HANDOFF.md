# 말한대로 핸드오프 (2026-11-10 새벽, 7판 기준)

다음 작업자(사람이든 Claude든)가 이 문서만 읽고 이어갈 수 있게 적는다.

## 1. 한 줄 요약

녹음·말·사진에서 "내가 챙길 일"을 뽑아 날짜별로 관리하는 개인 비서 웹앱. 각자 PC에 서버를 켜고 휴대폰으로 접속한다.
사내 공모 「2026 슬기로운 AI 생활」(접수 마감 **11/18**)에 본체로 응모하는 것이 당면 목표다.

## 2. 지금 어디에 무엇이 있나

| 무엇 | 어디 |
|---|---|
| 코드 최신판 | **GitHub `EaglingSun/malhandaero` (비공개), `main` 가지. 7판.** 이것이 기준이다 |
| 예전 묶음 | 프로젝트 문서 `claude/malhandaero-src-01.txt`~`07.txt`는 6판 소스 묶음. 저장소가 생겼으므로 더 쓰지 않는다 |
| 실행 중인 곳 | 사용자의 집 Mac. Tailscale로 https 주소를 열어 휴대폰 2대(Android)가 접속 |
| 개발 계획 문서 | claude.ai 아티팩트 「말한대로 개발 계획」 https://claude.ai/artifact/9hymSQQhmXfwhpuEw14dua (11/9 밤 기준. 그 뒤 추가분 미반영) |
| 홍보 페이지 | 아티팩트 「말한대로 소개 페이지」 https://claude.ai/artifact/CR8DdiWzVDDpbBLp258iqD |
| 설계서, 설치 안내 | 소스 묶음 안의 `docs/DESIGN.md`, `INSTALL.md`, `README.md` |

### 코드 받는 법

`git clone https://github.com/EaglingSun/malhandaero.git` 한 줄이면 된다. 풀고 나서 `python -m pytest -q`가 40개 통과하면 온전한 것이다.

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
- `server/llm.py` AI 연결: `claude`(이 PC의 Claude Code를 `claude -p`로 호출, 기본) | `api`(Anthropic 키) | `fake`(흉내)
- `server/calsync.py` 캘린더 자동 넣기: 네이버(CalDAV + 애플리케이션 비밀번호), 구글(OAuth)
- `server/stt.py` 음성 인식(faster-whisper, 선택 설치) · `server/db.py` SQLite와 칸 추가(MIGRATIONS)
- `web/` 빌드 없는 화면(PWA, 공유 받기) · `tools/install.py`, `tools/run.py` 설치와 실행
- `tools/update.py` 켜기 전 자동 업데이트: `.git`이 없는 폴더면 먼저 저장소에 연결(adopt: init → fetch → checkout -f; data/·.env는 그대로) → `git fetch` → fast-forward만 → requirements 바뀌면 재설치 → manifest 바뀌면 폰 앱 재설치 안내. 실패해도 켜기는 막지 않는다. `run.sh`/`run.bat`/`켜기.command`가 먼저 부른다
- `말한대로 처음 설치.command` 파일 하나로 clone → 설치 → 켜기 (Mac)
- 시험: `python -m pytest -q` → 40개 통과. AI·네이버·구글은 흉내 서버로, 업데이트는 임시 git 저장소로 시험한다

지키는 규칙

- 사람이 하는 일은 말하기·고르기·체크뿐. 캘린더 등 바깥 연결이 실패해도 할 일 저장은 막지 않는다.
- 화면과 안내 문구는 쉬운 한국어. 못 한 일은 "못 했어요 + 사유"로 화면에 남긴다.
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
| 네이버 캘린더 연결(남편 쪽) | 5판 이전에 "인터넷 연결 확인" 오류. 인증서 묶음(certifi) 지정으로 수정했으나 **실제 네이버 서버에서 미확인**. 실패하면 문구의 대괄호 안 사유를 받을 것 |
| 회의 요약 | "넣은 것" 탭에만 보임. 사용자가 못 찾음 → **첫 화면에 오늘 넣은 회의 요약을 접힌 한 줄로 보여 주기로 약속함(미구현)** |
| 5판의 목록 중심 화면, QR 연결, 더블클릭 실행 | 헤드리스 브라우저와 자동 시험으로만 확인. 실제 기기 의견 아직 없음 |
| 음성 파일 변환 | 코드만 있음. Mac에 faster-whisper 미설치. 음성 파일을 공유하면 "못 했어요"로 남음 |
| Windows 설치·실행 | 한 번도 안 돌려 봄 |
| 자동 업데이트의 '새 판 받기' | 연결·설치는 실제 Mac에서 확인. 새 커밋이 생긴 뒤 켜서 fast-forward가 되는 것은 아직 시험 저장소로만 확인 |

## 5. 다음 할 일 (순서대로)

1. 사용자의 11/10 실사용 의견 받기 → 고치기. 새 기능보다 우선
2. 녹음 앱에서 실제로 공유 → "넣은 것"에 들어오고 뽑히는지 확인 (목록에 나오는 것까지는 확인됨)
3. 첫 화면에 오늘 넣은 회의 요약(접힌 한 줄)
4. Mac 로그인 시 자동 시작(launchd). 업데이트는 켤 때 알아서 하므로 launchd에서 `run.sh`만 부르면 된다
5. 앱 알림(웹 푸시): 아침 "오늘 할 일 N건", 정한 시각 알림. 요구 R16의 남은 절반
6. 개인/회사 나눠 보기(요구 R12. 지금은 표시만)
7. 개발 계획 문서 갱신(Claude Code 연결, 캘린더 자동, QR, 목록 중심 화면, 자동 업데이트 추가분). 저장소 올리기는 끝남
8. 팀원 1~2명 시험 사용과 전/후 수치 측정(11/12~16) → 공모 게시글과 사용 안내(11/16~17)
9. 공모 이후: 더하기(애드온) 틀 → 장보기 → 회의 챙김

## 6. 결정이 남은 것

- 응모 부문: ① 회의와 업무 기록(경쟁작 0건, 권장) vs ⑥ 업무 비서(11건)
- 동료가 써 볼 방법: 지금 구조(각자 PC + 본인 Claude Code 로그인)를 그대로 안내할지, 사내 서버 시험판을 둘지
- 사내 배포 시 Claude Code 구독 로그인 사용이 회사 계정 설정·약관상 괜찮은지 확인 필요
  (앱이 Claude 로그인을 직접 받지 않고, 각자 PC의 Claude Code를 부르는 방식만 쓴다. 공용 서버에서 한 사람 로그인으로 여러 명이 쓰게 하지 않는다)

## 7. 사용 환경 메모

- 서버: 집 Mac. `말한대로 켜기.command`로 실행. Tailscale 켜져 있으면 https 주소 자동. 덮개를 닫으면 끊김
- 사용자 본인은 구글 캘린더, 남편은 네이버 캘린더로 연결하려 함
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
| 7 | GitHub 저장소에 올림. 켤 때 자동 업데이트(`tools/update.py`, 압축 폴더 자동 연결 포함), `말한대로 처음 설치.command`, privacy.html, 업데이트 시험 5개 |
