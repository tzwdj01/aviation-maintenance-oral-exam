# 0002. 服务端确定性评分

> Status: ACCEPTED
> Date: 2026-08-16（Phase 0 Governance Baseline）
> Deciders: 项目治理负责人

## Status

Accepted（固化自 `docs/SCORING.md` 与 `backend/app/scoring/` 的既有实现，Phase 0 登记为 ADR）。

## Context

LLM 输出的数字分数不可复现且难以审计；必须由服务端以快照和确定性规则重算。

## Decision

LLM 只输出 `covered / partial / missing / uncertain`、evidence quote、reasoning、
CE analysis 与 follow-up suggestion。**正式数字分数必须由服务端以
`Rubric Snapshot + Point Status + Weight / Partial Weight` 用 `Decimal` 确定性计算**，
不使用浮点，且任何正式分数都能从快照重算。

## Alternatives

- 直接采用 LLM 返回的分数（否决：不可复现、不可审计、违反原则 B）。

## Consequences

- 评分引擎独立于 Provider 实现（`app/scoring/engine.py`）。
- LLM 提示词与输出中不含"返回分数"要求。

## Migration Impact

无（Phase 0 不改代码）。

## Testing Impact

测试：Decimal 精确性、权重/partial 重算、Initial/Final 区分（`docs/TESTING.md` §3）。
