---
name: harness-tidy
description: Claude Code 하네스(CLAUDE.md · rules · skills · commands · subagents · output styles · auto memory · 그 밖의 지시 파일)를 인벤토리로 훑고, 대상별로 템플릿 기준 압축·배치 정리를 한 뒤 Eval·점검은 공식 기능으로 넘긴다. "하네스 정리", "하네스 인벤토리", "{스킬명} 정리해줘", "에이전트 정리해줘", "리뷰어 프롬프트 정리해줘", "CLAUDE.md 정리해줘", "rules 정리해줘", "규칙 압축" 요청 시 사용. 새 스킬 작성·Eval 실행 자체는 skill-creator.
---

# harness-tidy (판: VERSION 파일)

## Input
- 대상: CLAUDE.md · rule · skill(command 포함) · agent · output style · auto memory · 그 밖의 지시 파일(예: harness/reviewer.md). 없으면 inventory
- 템플릿: 프로젝트 .claude/templates/ 우선, 없으면 이 스킬의 templates/

## Rules
- HT-01 수정 전에 원본을 {파일}.bak 으로 복사한다 (확장자는 맨 끝: SKILL.md.bak. .bak.md 는 다시 로드되므로 금지)
- HT-02 1단계는 대상 파일을 고치지 않고 검토 문서(templates/review.md)만 쓴다. 결정 칸(유지·수정·뺄)을 받은 뒤 2단계로 간다
- HT-03 원본 줄 번호는 Grep 도구(줄 번호 출력) 결과로만 적고 원문 인용을 함께 둔다. 셸 명령(grep -n 등)에 기대지 않는다
- HT-04 한 줄에 규칙이 여러 개면 나누고, 검사 방식·대상이 같은 규칙은 한 줄로 묶는다. 나누고 묶은 내역을 남긴다
- HT-05 원본에 없는 규칙은 추가하지 않는다. 표현을 바꾸면 원문을 함께 남긴다
- HT-06 매핑되지 않은 원본 문장은 [확인필요]로 표시하고 묻는다
- HT-07 규칙(행동을 지시 · 금지하는 문장 — Rules 절 밖 · procedure.md · pitfalls.md 로 옮긴 것 포함)은 ID({약어}-NN)를 붙인 한 줄 명령형. 옮겨도 ID 는 그대로 둔다. 금지어 "~하면 좋다" "가능하면" "적절히". 원본의 이유는 (이유: …) 또는 why.md#{ID} 로 보존한다
- HT-08 정규식·카운트로 판정 가능한 규칙은 (lint), 나머지는 (judge)
- HT-09 줄 수는 `python scripts/inventory.py --file {경로}` 의 본문 줄 수로 잰다. 상한: skill·agent·prompt 40 · CLAUDE.md 50 · rule 30. 넘으면 묶기 → 이동 → 외부 참조 순으로 줄인다
- HT-10 Eval 씨앗은 정리본이 아니라 mapping.md 전체 행(유지·수정·묶음·이동·뺄)에서 만든다. 이동은 옮긴 곳이 로드되는 경로를 만지는 케이스, 뺄은 사유를 적고 필요 시 케이스. (lint) → forbidden.txt · (judge) → evals.json · 트리거 → trigger-eval.json. 커버리지 · 새 ID 는 inventory.py --coverage 로 확인하고 exit 0 일 때만 넘긴다
- HT-11 한 번에 한 대상만 처리한다. 다른 대상과 규칙을 공유하면 상류(CLAUDE.md · rule)부터 정리하자고 제안한다
- HT-12 Eval 실행·전후 비교·트리거 최적화·전체 점검은 handoff.md 대로 공식 기능에 넘긴다
- HT-13 넘기기 전에 승인을 받는다. 넘길 기능이 없으면 설치 안내와 넘김 프롬프트만 출력하고 멈춘다
- HT-14 1단계에서 `inventory.py --near {대상}` 으로 주변 후보(L1)를 뽑고 그 후보만 읽어, 규칙마다 바깥 위치(경로:줄)와 자동 로드 여부를 적는다. 전체 의미 비교(L2)는 요청 시에만
- HT-15 한 규칙은 한 곳에만 둔다. 둘 곳은 placement.md 로 정하고, 같은 맥락에서 자동 로드되는 곳에 이미 있으면 빼고 참조(agent 는 skills: preload)로 바꾼다
- HT-16 매번 반드시 지켜져야 하는 (lint) 규칙은 hook 전환 후보로 표시한다 (지시는 요청일 뿐 보장이 아니다)
- HT-17 화면 출력은 단계마다 20줄 이내 요약(templates/summary.md)이다. 결정이 필요한 항목만 나열하고 유지는 개수만, 전체 표는 파일로 둔다
- HT-18 매핑표는 evals/{대상}/mapping.md 에 저장하고, 행마다 변경 유형(유지·수정·묶음·이동·뺄)을 적는다. 뺄·묶음 행도 지우지 않는다

## Modes (상세: modes.md)
- inventory(L0 스크립트) · skill · agent · prompt · claude-md · rules · style · memory — 대상 종류로 고른다

## Output
- 화면: templates/summary.md 형식 (HT-17)
- 파일: docs/reports/{날짜}-harness-tidy/{약어}-규칙-검토.md · evals/{대상}/mapping.md · 정리본 · Eval 씨앗

## Don't
- 승인 전 대상 수정 · .bak 없는 덮어쓰기 · 원본에 없는 규칙 추가 · 기억으로 줄 번호 쓰기 · Eval 실행기 신규 작성

## Refs
- modes.md · placement.md · handoff.md · templates/ · scripts/inventory.py · VERSION · CHANGELOG.md
