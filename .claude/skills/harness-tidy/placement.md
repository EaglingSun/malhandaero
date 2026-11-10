# placement — 규칙을 어디에 둘까

한 규칙은 한 곳에만 둔다 (HT-15). 위에서부터 처음 맞는 곳에 둔다.

| 순서 | 규칙·지시의 성격 | 둘 곳 | 예 |
|---|---|---|---|
| 0 | 매번 자동으로 실행 · 차단해야 함 (판단 불필요) | hook (settings.json) · 확실한 허용 · 차단은 permissions | 허용 목록 밖 쓰기 차단, 편집 후 lint |
| 1 | 프로젝트 전체의 사실 · 행동 원칙 | CLAUDE.md (개인은 CLAUDE.local.md) | 승인 전 커밋 금지, 빌드 명령 |
| 2 | 특정 파일 종류의 품질 기준, 여러 작업이 공유 | rule (.claude/rules/, paths) | 용어 병기, 번역투 금지 |
| 3 | 응답의 역할 · 어조 · 형식 (세션 전체) | output style | 결론 먼저, 표 위주 |
| 4 | 특정 작업의 순서 · 도구 · 그 작업만의 기준 | skill | 대본 분량 계산, 검수 절차 |
| 5 | 격리된 맥락 · 제한된 도구로 일하는 작업자 | agent (본문 = system prompt) | 코드 리뷰어, 대량 검색 |
| 6 | 외부 시스템 연결 | MCP (+ 사용법은 skill) | Notion, DB |
| 7 | 자동 로드되지 않는 기준 문서에만 있음 | 그 문서 + 사용하는 skill·agent 절차에 "읽는다" 1줄 | 검토 지시문 |

- auto memory 는 둘 곳이 아니라 **승격 대상의 출처**다 (Claude 가 쓴 학습 메모 → 위 표로 옮긴다)

## 로드 판정 (Claude Code 기준)
| 위치 | 언제 로드되나 | 컨텍스트 비용 |
|---|---|---|
| CLAUDE.md · CLAUDE.local.md (작업 폴더와 상위) | 세션 시작, 항상 | 매 요청 |
| 하위 폴더의 CLAUDE.md | 그 폴더의 파일을 읽거나 고칠 때 | 로드 후 매 요청 |
| .claude/rules/*.md (paths 없음) | 세션 시작, 항상 | 매 요청 |
| .claude/rules/*.md (paths 있음) | paths 에 맞는 파일을 읽거나 고칠 때 | 로드 후 매 요청 |
| output style | 선택된 1개가 세션 내내 | 매 요청 |
| auto memory MEMORY.md | 세션 시작, 첫 200줄 또는 25KB | 매 요청 |
| skill · command | description 은 항상, 본문은 호출될 때 | 낮음 |
| agent | 위임·명시 호출 때, 별도 맥락 (자기 본문 + CLAUDE.md + preload skills) | 메인과 분리 |
| hook | 이벤트 때 실행, 지시로 로드되지 않음 | 0 (출력이 있을 때만) |
| 그 밖의 문서 | @ 참조되거나 읽으라고 지시할 때만 | 그때만 |

## 중복을 발견했을 때
- 같은 맥락에서 **자동 로드**되는 곳에 이미 있다 → 이 대상에서 빼고, Refs 에 "{ID}는 {파일} 소관" 1줄
- agent 본문이 skill 내용을 복사했다 → 본문에서 빼고 frontmatter `skills:` 로 preload
- **자동 로드되지 않는** 곳에만 있다 → 그 문서를 기준으로 삼아 "읽는다" 1줄(ID 는 그 문서 쪽), 또는 남기고 그 문서를 다음 정리 대상으로 표시
- 일부만 겹친다 → 겹치지 않는 부분만 남기고, 덜어 낸 부분의 소관 파일을 적는다

## 주의
- 경로 rule · 하위 CLAUDE.md 는 파일을 만질 때 로드된다 → skill·agent Procedure 1 = "대상 파일을 먼저 읽는다"
- CLAUDE.md · rule · output style 은 지시라서 강제되지 않는다 → 막아야 하면 hook (순서 0). hook 도 꺼져 있거나(disableAllHooks) 실패하면(exit 0 · 2 밖) 대개 그대로 진행된다 → 확실한 허용 · 차단은 permissions
- 상위 파일(CLAUDE.md · rule)을 바꾸면 하류 skill·agent 모두에 영향 → 하류 반영 표로 확인한다
- 공식 권장은 CLAUDE.md 파일당 200줄 아래다. 이 스킬은 정리 목적상 더 엄격한 50줄을 쓴다
