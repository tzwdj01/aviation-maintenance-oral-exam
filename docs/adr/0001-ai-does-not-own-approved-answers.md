# 0001. AI 不拥有正式标准答案

> Status: ACCEPTED
> Date: 2026-08-16（Phase 0 Governance Baseline）
> Deciders: 项目治理负责人

## Status

Accepted（固化自 `docs/PRD.md` §5.3 与 `docs/SCORING.md` §1 的既有设计结论，Phase 0 将其登记为 ADR）。

## Context

若允许 LLM 自行创建/修改正式标准答案，评分将不可复现、超出治理边界，并可能放大模型幻觉。

## Decision

正式的主问题、Rubric、RubricPoint、Critical Error Rule、技术标准与评分权重必须来自
**经过批准和版本控制的数据**。LLM 只能将考生回答映射到预定义 ID，不得新增标准答案、
得分点或 Critical Error；不得自行创建新的正式考试标准。

## Alternatives

- LLM 自由生成标准答案（否决：不可控、不可审计）。
- 部分 AI 生成标准、人工审核后发布（否决：本阶段范围外，需另行治理）。

## Consequences

- 题库必须人工治理并版本化发布。
- LLM 输出受规则 ID 白名单与 schema 校验约束。

## Migration Impact

无（本阶段不改代码）。

## Testing Impact

测试需覆盖：未知/伪造 rubric ID 被拒绝（`docs/TESTING.md` Golden Dataset G）。
