# 0007. Attempt 锁定评估 Profile

> Status: ACCEPTED
> Date: 2026-08-16（Phase 0 Governance Baseline）
> Deciders: AI/Provider 架构负责人

## Status

Accepted（固化自 `docs/multi-provider-design.md` 与 `backend/app/exam/assembly.py` 的既有实现）。

## Context

若进行中/历史考试受系统默认模型变更影响，评分结果将不可复现、不可审计。

## Decision

创建 `ExamAttempt` 时保存并锁定：

- provider
- model
- `llm_profile_id`
- qualification snapshot
- prompt bundle version

Attempt 进入 `READY` 后锁定。管理员后续修改默认模型**不得影响 active Attempt 与 historical Attempt**。

## Alternatives

- 运行时实时读取系统默认 Provider（否决：破坏可复现性）。

## Consequences

- 快照是审计与复现的基础（`plan_snapshot` / `llm_profile_snapshot` / `prompt_bundle_snapshot`）。

## Migration Impact

无（Phase 0 不改代码）。

## Testing Impact

测试：快照不可变、默认模型变更不影响进行中考试（`docs/TESTING.md` §2 样本 L）。
