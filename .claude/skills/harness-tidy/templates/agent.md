---
name: {에이전트명}
description: {어떤 작업자인지 1구절}. {위임할 상황 2~3개}. {이웃 skill·agent 와 경계 1구절}
tools: {필요한 도구만 — 예: Read, Grep, Glob}
model: {inherit | sonnet | opus | haiku}
skills:
  - {미리 넣을 스킬 — 본문에 복사하지 않는다}
---

# {역할 1줄}

## Input
- {위임받을 때 받는 것 1줄씩}

## Rules
- {약어}-01 {규칙} (lint)
- {약어}-02 {규칙} (judge)

## Procedure
1. 대상 파일을 먼저 읽는다 (경로 rule · 하위 CLAUDE.md 가 로드되도록)
2. {단계 1줄}

## Output
- 메인 대화로 돌려줄 요약 형식 · 길이 상한

## Don't
- {금지 행동 1줄씩}

## Eval
- 위임: evals/agents/{에이전트명}/trigger-eval.json
- 동작: evals/agents/{에이전트명}/evals.json (prompt 에 `@"{에이전트명} (agent)"`)
