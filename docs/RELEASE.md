# Release（发布流程与回滚策略）

> Status: ACTIVE
> Owner: 项目治理负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: 发布治理与回滚策略

## 1. 发布流程

每次正式发布至少执行：

1. **Backup**：数据库与审计材料备份（含不可变快照）。
2. **Migration**：Alembic 迁移（向前），迁移脚本可回滚或有明确 forward-fix strategy。
3. **Deploy**：按 `docs/DEPLOYMENT.md` 环境顺序（TEST → STAGING → PRODUCTION）。
4. **Health Check**：`/api/v1/health` 与关键业务探测。
5. **Smoke Test**：核心闭环关键路径（出题→答题→评分→复核）冒烟。
6. **Canary**（生产）：小流量灰度，监控错误率/延迟/结构化输出有效率。
7. **Rollback**：失败时按备份与迁移策略回滚或 forward-fix。

## 2. 回滚原则

- 正式生产迁移必须可回滚，或有明确的 forward-fix strategy。
- 历史考试数据（快照、采用关系、审计）在回滚中不得丢失。
- 发布后发现问题：优先评估 forward-fix；确需回滚时按备份恢复并复核审计一致性。

## 3. 发布纪律

- 发布必须通过 Architecture Drift Check（`AGENTS.md` §5）与 CURRENT_SPRINT 范围确认。
- 涉及模型/Prompt/词典/评分语义变更，必须先通过 Golden Dataset 回归（`docs/TESTING.md`）。
- 发布不自动触发；需人工批准。
- 本 Phase 0 不创建 release tag（仅治理分支 + PR）。
