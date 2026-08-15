# 0005. 禁止 Silent Provider Failover

> Status: ACCEPTED
> Date: 2026-08-16（Phase 0 Governance Baseline）
> Deciders: AI/Provider 架构负责人

## Status

Accepted（固化自 `docs/multi-provider-design.md` 与 `backend/app/ai/providers/registry.py` 的既有语义）。

## Context

跨 Provider 静默切换会破坏审计一致性、资格边界与评分可复现性，并可能在不同模型间引入偏差。

## Decision

Provider 失败（如 DeepSeek 超时 → 重试 → 仍失败）默认必须进入
`TaskJob FAILED` 或 `AttemptItem NEEDS_ATTENTION`，**禁止偷偷切换**到其他 Provider。
未来若实现 fallback，必须记录 `original_provider` / `fallback_provider` /
`mixed_provider=true` / `needs_human_review=true`，并经过 ADR。

## Alternatives

- 自动跨厂商兜底（否决：破坏审计与资格治理）。

## Consequences

- 失败可安全重试或人工介入。
- 审计中 Provider 字段始终为单一可信来源。

## Migration Impact

无（Phase 0 不改代码）。

## Testing Impact

测试：失败任务不切换 Provider、状态进入 FAILED/NEEDS_ATTENTION（`backend/tests/test_sprint_1a.py` 已覆盖 job 失败语义）。
