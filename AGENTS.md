# AGENTS.md — 项目进入入口（所有 Codex / AI Agent 必须遵守）

> Status: ACTIVE
> Owner: 项目治理负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）

本文件是所有 AI Agent / 开发者进入本仓库后的**强制入口**。开始任何工作前必须完成下述检查。
本文件保持精简；详细规范在各 Source of Truth 文档中，不要在此复制全文。

## 1. Before any code change

任何代码或文档修改前，Agent 必须：

1. 阅读 `GOAL.md`（产品 North Star，不可偏离）。
2. 阅读 `docs/plans/CURRENT_SPRINT.md`（确认改动在当前 Sprint 范围内）。
3. 阅读相关域 Source of Truth 文档（见下方路由规则）。
4. 检查当前实现，再决定是否重构（不得凭想象重写）。
5. 检查相关测试。
6. 检查 Git 状态（分支、未提交改动、最近提交）。
7. 确认请求的改动在当前 Sprint 范围内；范围外工作标记 `OUT_OF_SCOPE`，不得顺手完成。

## 2. 文档路由规则

修改以下内容时，**必须先阅读**对应 Source of Truth：

| 修改内容 | 必须阅读 |
| --- | --- |
| Exam workflow / states | `docs/EXAM_STATE_MACHINE.md` |
| Scoring / CE / Evidence | `docs/SCORING.md` |
| Database / entities | `docs/DATA_MODEL.md` |
| Provider / LLM / ASR / TTS | `docs/ARCHITECTURE.md`、`docs/providers/`、`docs/qualification/` |
| API Key / secrets | `docs/SECURITY.md`、`docs/CONFIGURATION.md` |
| Deployment / release | `docs/DEPLOYMENT.md`、`docs/RELEASE.md` |
| 大型架构变更 | `docs/adr/README.md`，并判断是否需要 ADR |

## 3. Source of Truth 优先级

项目内部决策优先级（从高到低）：

1. `GOAL.md`
2. Accepted ADR（`docs/adr/`）
3. Domain-specific Source of Truth 文档（EXAM_STATE_MACHINE / SCORING / DATA_MODEL / ARCHITECTURE / SECURITY / CONFIGURATION / DEPLOYMENT / RELEASE）
4. `docs/plans/CURRENT_SPRINT.md`
5. 当前实施计划
6. 现有实现
7. Agent 假设

如果当前任务与 GOAL / Accepted ADR / Source of Truth 明显冲突：

1. 标记 `ARCHITECTURE_CONFLICT`。
2. 说明冲突内容。
3. 提出 ADR。
4. 等待授权或按任务明确授权进行架构变更。

**普通业务需求不得顺带改变基础架构。**

## 4. 每次任务开始：PROJECT ALIGNMENT

开始任务时输出（或内部确认）对齐检查：

- Goal alignment（是否服务于 GOAL 中的核心闭环）
- Current Sprint alignment（是否在 CURRENT_SPRINT 范围内）
- ADR impact（是否触及需 ADR 的区域）
- Source-of-truth docs（是否已读相关文档）
- Security impact（是否引入 secret / 是否破坏最小权限）
- Qualification impact（是否影响模型资格边界）
- Migration impact（是否影响数据库 / 已发布版本 / 历史快照）
- Testing requirements（是否需要新增/更新测试）

发现范围外工作时标记 `OUT_OF_SCOPE`，不得顺手完成。

## 5. 每次任务结束：Architecture Drift Check

任何 feature 完成前，必须逐项检查：

1. 是否仍符合 `GOAL.md`。
2. 是否超出 Current Sprint。
3. 是否绕过 Provider abstraction。
4. 是否让 LLM 拥有数字评分权。
5. 是否修改 state machine（且无 ADR）。
6. 是否修改正式 rubric semantics（且无 ADR）。
7. 是否引入 secret。
8. 是否引入 silent failover。
9. 是否破坏 auditability。
10. 是否需要 ADR 但没有 ADR。

最终报告必须包含：

```text
## Architecture Drift Check
Result: PASS | BLOCKED
```

## 6. 关键红线速查

- 不把 AI 当作未经人工治理的最终授权决策者（`GOAL.md` §1、§4）。
- 正式分数只能由服务端确定性计算（`GOAL.md` 原则 B、`docs/SCORING.md`）。
- 真实 API Key 永远不得写入 Git / Markdown / 代码 / 前端 / 日志 / 审计原文（`docs/SECURITY.md`）。
- 禁止 Silent Provider Failover（`docs/ARCHITECTURE.md`、`docs/adr/0005-*.md`）。
- 状态机唯一规范是 `docs/EXAM_STATE_MACHINE.md`；`RECORDING` 仅是前端状态。
- 架构变更先 ADR 后实现（`docs/adr/README.md`）。
