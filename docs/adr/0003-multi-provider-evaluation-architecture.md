# 0003. 多 Provider 评估架构

> Status: ACCEPTED
> Date: 2026-08-16（Phase 0 Governance Baseline）
> Deciders: AI/Provider 架构负责人

## Status

Accepted（固化自 `docs/multi-provider-design.md` 与 `backend/app/ai/providers/` 的既有实现）。

## Context

评分业务不能绑定单一厂商 SDK/HTTP 负载，需要可替换、可资格管理的评估 Provider。

## Decision

业务层只通过统一接口 `EvaluationProvider`
（`evaluate_coverage` / `detect_critical_errors` / `evaluate_quality_risk` /
`decide_follow_up` / `final_assessment`）与 `SpeechProvider` 交互。Provider 通过
`ProviderRegistry` 按 `LLMProfile` 快照显式选择；服务端统一 schema 校验，不依赖厂商的
结构化输出保证。候选支持：MiMo / DeepSeek / OpenAI（以 `qualification_status` 治理）。

## Alternatives

- 单一厂商直接集成（否决：绑定风险、无法资格管理）。
- 多个 SDK 散落在业务代码（否决：违反服务端边界与可替换性）。

## Consequences

- 业务服务不依赖具体厂商 SDK。
- 新 Provider 通过实现统一接口 + 注册 + Qualification 接入。

## Migration Impact

无（Phase 0 不改代码）。

## Testing Impact

测试：Fake Provider 垂直切片、Provider 契约一致性、未知 Provider 拒绝。
