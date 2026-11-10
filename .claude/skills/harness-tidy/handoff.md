# Handoff — 공식 기능으로 넘기기

정리(harness-tidy)가 끝난 뒤 검증·최적화·전체 점검은 공식 기능이 맡는다. 넘기기 전에 사용자 승인을 받는다 (HT-13).
harness-tidy 는 규칙 ID 기반 **씨앗 케이스**만 만든다. 케이스 확장 · 실행 · 채점 · 벤치마크는 skill-creator 가 한다.

## 넘김 표
| 모드 | 넘길 곳 | 언제 | 넘김 프롬프트 |
|---|---|---|---|
| inventory (L2, 선택) | /doctor prompt-audit | 사용자가 전체 점검을 원할 때 · 월 1회 · 큰 개편 전 | `/doctor prompt-audit` (하네스 전체: 오래된 지시 · 없는 파일 참조 · 파일 간 모순). 끊긴 @참조 · 이름 충돌은 L0 스크립트가 이미 잡는다 |
| skill | skill-creator (Eval) | 2단계 작성 + 매핑표 승인 + 커버리지 100% 후 | "{스킬명} 스킬을 개선 중이야. 기준선은 원본(SKILL.md.bak 또는 git 태그 {기준선}) 스냅샷, 비교 대상은 정리본. 두 쪽 모두 evals/{스킬명}/evals.json 의 같은 케이스로 돌리고, expected_output 의 [규칙 ID][매핑 행] 을 assertion 이름에 유지해줘. 이동 케이스는 옮긴 rule 이 로드되는 경로를 실제로 만져야 한다." |
| skill | skill-creator (Description 최적화) | Eval 결과 확인 후 | "evals/{스킬명}/trigger-eval.json 을 검토해서 20개로 늘리고 description 최적화를 돌려줘." |
| agent | /doctor prompt-audit | 정리본 작성 후 | `/doctor prompt-audit .claude/agents/{이름}.md` |
| agent | Eval (수동 또는 스크립트) | 점검 후 | evals/agents/{이름}/ 의 케이스를 `@"{이름} (agent)"` 로 실행하고 규칙 ID 별로 채점 |
| claude-md | claude-md-improver | 정리본 작성 후 | "정리한 CLAUDE.md 를 감사해줘." |
| rules | skill-creator (Eval) | 정리본 확정 후 | "{대표 스킬} 스킬 Eval 에 evals/rules/{파일명}/evals.json 케이스를 포함해 돌려줘. 케이스는 {paths} 파일을 만지는 작업이어야 rule 이 로드된다." |
| 전체 | inventory.py --changed-since · (선택) prompt-audit | 대상 하나를 머지한 뒤 | 회귀 점검: 먼저 스크립트로 바뀐 파일의 끊긴 참조·줄 초과를 보고, 모순 점검이 필요할 때만 prompt-audit |

## 넘기기 전 점검
- [ ] evals.json — mapping.md 모든 행에 케이스 또는 `없음(사유)` (`inventory.py --coverage evals/{대상}` 이 exit 0 — 커버리지 100% · ID 없음 0 · 변경 유형 오류 0)
- [ ] expected_output 에 [규칙 ID][매핑 행] (예: [DS-03][M07])
- [ ] trigger-eval.json — 별도 파일, {query, should_trigger} 형식
- [ ] lint/forbidden.txt 로 직접 검사한 결과를 먼저 보고 (lint 는 넘기지 않는다)
- [ ] .bak 원본 존재 (기존 대상 개선 시 기준선)

## trigger-eval.json 작성 기준 (skill-creator 와 동일, agent 위임에도 적용)
- should_trigger true 8~10개 · false 8~10개, 최종 20개 내외 (씨앗은 6개 이상)
- 질의는 실제 사용자가 칠 법한 구체적인 문장: 이름 · 범위 · 상황 · 구어체 · 오타 포함
- 짧고 단순한 질의는 description 과 무관하게 호출되지 않을 수 있다 → 실제 상황을 담는다
- false 는 무관한 질의가 아니라 **키워드는 겹치지만 다른 대상이 맞는 근접 사례**로 만든다

## 기능 찾기
- 스킬 이름은 환경마다 접두어가 다르다 (예: anthropic-skills:skill-creator, /skill-creator). 사용 가능한 목록에서 이름으로 찾는다.
- description 최적화는 `claude -p` 가 필요해 Claude Code 에서만 돌아간다.
- `/doctor prompt-audit` 는 Claude Code 내장 기능이다 (v2.1.283 이상, 번들 스킬 /claude-api 가 켜져 있어야 함).

## 없을 때 설치 안내
- skill-creator: Claude Code 에서 `/plugin install skill-creator@claude-plugins-official`
- claude-md-management (claude-md-improver 포함): Claude Code 에서 `/plugin install claude-md-management@claude-plugins-official`
- /doctor prompt-audit: Claude Code 업데이트
- 설치 후 Claude Code 를 재시작한다.

## 결과 받기
- 규칙 ID별 통과/실패와 description 변경안을 요약해 매핑표 옆에 붙인다.
- prompt-audit 지적은 검토 문서의 [확인필요] 로 옮겨 결정 칸으로 처리한다.
- 항상 통과하는 assertion(변별력 없음)은 규칙 문장이나 케이스를 다시 보도록 표시한다.
- description 변경안은 바로 반영하지 않고 사용자 승인 후 반영한다.
