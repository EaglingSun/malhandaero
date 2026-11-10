---
name: {스킬명}
description: {하는 일 1구절}. "{표현1}", "{표현2}", "{표현3}" 요청 시 사용. {이웃 스킬}과 구분: {기준 1구절}
---

# {스킬명}

## Input
- {필요한 입력 1줄씩}

## Rules
- {약어}-01 {규칙} (lint)
- {약어}-02 {규칙} (judge)

## Procedure
1. 대상 파일을 먼저 읽는다 (경로 rule 이 자동 로드되도록)
2. {단계 1줄} — 상세: procedure.md

## Output
- {출력 형식 1~3줄}

## Don't
- {금지 행동 1줄씩}

## Refs
- procedure.md · pitfalls.md · why.md · lint/forbidden.txt
- {ID 묶음}은 .claude/rules/{파일}.md 소관 (자동 로드)

## Eval
- 준수: evals/{스킬명}/evals.json
- 트리거: evals/{스킬명}/trigger-eval.json
