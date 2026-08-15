# ADR — Architecture Decision Records（架构决策记录）

> Status: ACTIVE
> Owner: 项目治理负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: ADR 流程与模板

## 1. 目的

将重要架构决策以轻量文档固化，使未来任何开发者 / AI Agent 都能理解"为什么这样做"，
并防止普通业务需求悄悄改变基础架构。

## 2. 何时需要 ADR

修改以下任一内容**必须**先创建/更新 ADR，再修改实现：

- database（实体、约束、迁移策略）
- scoring semantics（评分语义、权重、Initial/Final）
- CE semantics（Critical Error 语义、粘性、override）
- state machine（状态、迁移）
- Provider abstraction（EvaluationProvider / SpeechProvider 接口）
- failover（是否允许跨 Provider fallback）
- Evidence rules（引文解析规则）
- question versioning（题目/规则版本化）
- audit rules（审计与保留）
- secret management（密钥管理）
- production deployment architecture（生产部署架构）

## 3. 流程

1. 标记 `ARCHITECTURE_CONFLICT`（如当前任务与 Source of Truth 冲突）。
2. 编写 ADR：`docs/adr/NNNN-<slug>.md`（NNNN 为递增序号）。
3. Status 初始为 `PROPOSED`；经人工批准后置为 `ACCEPTED`；废弃时置为 `SUPERSEDED` 并指向替代 ADR。
4. 修改实现。

## 4. 模板

```markdown
# NNNN. <标题>

> Status: PROPOSED | ACCEPTED | SUPERSEDED
> Date: YYYY-MM-DD
> Deciders: <决策人>

## Status

## Context

## Decision

## Alternatives

## Consequences

## Migration Impact

## Testing Impact
```

## 5. 已接受 ADR 索引

| 编号 | 决策 | 状态 |
| --- | --- | --- |
| [0001](0001-ai-does-not-own-approved-answers.md) | AI 不拥有正式标准答案 | ACCEPTED |
| [0002](0002-server-side-deterministic-scoring.md) | 服务端确定性评分 | ACCEPTED |
| [0003](0003-multi-provider-evaluation-architecture.md) | 多 Provider 评估架构 | ACCEPTED |
| [0004](0004-mimo-primary-speech-provider.md) | MiMo 为核心语音 Provider | ACCEPTED |
| [0005](0005-no-silent-provider-failover.md) | 禁止 Silent Provider Failover | ACCEPTED |
| [0006](0006-evidence-offsets-resolved-server-side.md) | Evidence offset 服务端解析 | ACCEPTED |
| [0007](0007-attempt-locks-evaluation-profile.md) | Attempt 锁定评估 Profile | ACCEPTED |
