# CHANGELOG

## 1.1.0
- HT-07 변경: 규칙 = 행동을 지시 · 금지하는 문장. Rules 절 밖(Procedure · Output · Don't)과 procedure.md · pitfalls.md 로 옮긴 규칙에도 ID 를 붙이고, 옮겨도 ID 는 그대로 둔다
- templates/mapping.md: 이동 예시가 새 ID 를 `—` 로 비우던 것을 고침. 새 ID 칸은 ID 또는 `없음(사유: …)` (빈칸 · `—` 금지), 변경 유형은 다섯 가지만
- inventory.py --coverage: 새 ID 없는 행(「ID 없음」)과 다섯 가지 밖 변경 유형(「유형 오류」)을 표시하고 exit 1. 1.0.0 매핑표의 `—` 행은 이제 실패로 나온다 → `없음(사유: …)` 나 ID 로 고친다
- HT-10: --coverage 가 exit 0 일 때만 넘긴다 · 2단계 요약에 ID 줄 추가 · tests/test_coverage.py 추가

## 1.0.0
- 첫 공개판. 규칙(HT-01~18) · 모드 · 템플릿은 1.0.0-rc.2 와 같다. 이후 1.0.x 는 문서 오타만 고친다
- MIT 라이선스 추가
- inventory.py: `--file` 상대 경로를 `--root` 기준으로 푼다 · 프로젝트 상위 폴더 이름이 build 등이어도 목록에서 빠지지 않는다 · `--coverage` 는 mapping.md 의 첫 표만 읽는다
- 문서: 설치 안내를 저장소 받기 기준으로 · skill-creator 설치 명령과 hook 문구를 공식 문서에 맞춤

## 1.0.0-rc.2
- HT-10 변경: Eval 씨앗을 정리본이 아니라 mapping.md 전체 행에서 만든다 → 빼거나 옮긴 규칙의 회귀도 원본·정리본 비교에서 잡힌다
- templates/mapping.md: 행 번호(Mxx) · Eval 케이스 칸 추가 (빈칸 금지, 없으면 사유)
- templates/evals.json: expected_output 에 [규칙 ID][매핑 행], 이동 · 뺄 케이스 예시
- inventory.py --coverage evals/{대상}: 매핑 행 대비 케이스 커버리지 확인
- handoff: 원본·정리본 같은 케이스 세트, 이동 케이스는 rule 로드 경로를 만질 것, 넘기기 전 커버리지 100%

## 1.0.0-rc.1
- 모드: inventory · skill · agent · prompt(그 밖의 지시 파일) · claude-md · rules · style · memory
- HT-17 단계별 화면 요약 20줄 이내 (templates/summary.md)
- HT-18 매핑표 고정 위치 evals/{대상}/mapping.md + 변경 유형 (templates/mapping.md)
- Windows 대응: 줄 수는 inventory.py --file, 줄 번호는 Grep 도구 (wc -l · grep -n 의존 제거), .bak 확장자 규칙
- inventory.py: --extra (표준 위치 밖 지시 파일) · --file (단일 파일 줄 수) · --version
- VERSION · CHANGELOG 추가
