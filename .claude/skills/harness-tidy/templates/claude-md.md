# {프로젝트명}

## Identity
- {프로젝트 목적 1줄}

## Global Rules
- G-01 규칙·스킬을 추가할 때는 @.claude/templates/rule-format.md 를 따른다
- G-02 Skill Routing 표에 해당하는 요청이면 그 스킬을 먼저 로드한다
- G-03 세션 종료 시 @.claude/templates/session-feedback.md 표를 작성한다
- G-04 파일·폴더를 3개 이상 만드는 작업은 트리를 먼저 제안하고 승인 후 진행한다
- G-05 STRUCTURE.md 에 없는 최상위 폴더는 만들지 않는다
- G-06 스킬을 만들거나 고칠 때는 @.claude/templates/skill.md 를 따른다

## Skill Routing
| 요청 표현 | 스킬 |
|---|---|
| {표현} | {스킬명} |
| 스킬 정리, CLAUDE.md 정리, 규칙 압축 | harness-tidy |
| 스킬 Eval, 트리거 최적화 | skill-creator |

## References
- 구조: STRUCTURE.md
- 경로 규칙: .claude/rules/ (paths 에 맞는 파일을 만질 때 자동 로드)
- 작업자: .claude/agents/ · 응답 형식: .claude/output-styles/ · 강제 규칙: settings.json hooks
- 세부 절차는 각 스킬 폴더의 참조 파일. 여기에 복사하지 않는다
