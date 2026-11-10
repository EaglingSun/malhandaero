# STRUCTURE

## 허용 최상위 항목 (hook 이 읽음, 한 줄에 하나)
<!-- allowed:start -->
.claude
evals
docs
tmp
CLAUDE.md
STRUCTURE.md
README.md
<!-- allowed:end -->

## 트리와 용도
evals/
  {스킬명}/
    evals.json         # (judge) 규칙 씨앗 케이스 (skill-creator 형식)
    trigger-eval.json  # 트리거 질의 {query, should_trigger}
    fixtures/      # 실제 실패 로그 · 입력
  results/         # 날짜별 실행 결과
tmp/               # 임시 파일, 작업 후 삭제

## 새 작업 시작 프롬프트
1단계 — 구조 제안만 (파일 생성 금지)
- STRUCTURE.md 와 기존 폴더를 먼저 확인하고 재사용할 위치를 찾는다
- 만들 폴더·파일을 트리로 제안한다 (경로 + 용도 1줄), 이름은 소문자 케밥케이스
- 제안 후 멈추고 승인을 기다린다
2단계 — 승인된 트리 안에서만 작업
- 트리에 없는 파일·폴더는 만들지 않는다 (필요하면 먼저 묻는다)
- 임시 파일은 tmp/ 에만, 끝나면 삭제
- 완료 시 이 파일의 트리와 용도를 갱신한다
