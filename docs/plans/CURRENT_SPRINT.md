# Current Sprint

> Status: ACTIVE
> Owner: 项目治理负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: 当前 Sprint 范围与完成定义

> 未来任何 Codex 任务结束后不得自行修改本文件进入下一 Sprint；只有用户明确批准才能修改。

## 当前状态

- **已完成**：Phase 0 — Project Governance & Architecture Baseline（Governance Gate 审查中）。
- **Next Approved Sprint**：Sprint 1A — Model-Independent Core + Multi-Provider Foundation。

## Sprint 1A 定义

> 说明：Sprint 1A 的模型无关后端基础已在 `feature/sprint-1a-multi-provider-foundation` 分支实现；
> 本 Sprint 定义用于 Gate 审查与后续收尾，不以"从零开始"为前提。

### Goal

建立不依赖具体 AI 厂商、可审计的模型无关后端基础：
SQLAlchemy/Alembic 审计模型、严格状态机、确定性 Decimal 评分、证据解析、
版本化术语标准化、LLM Profile 管理、MiMo/DeepSeek/OpenAI/Fake Provider Adapter 契约，
以及无需真实 Key 即可运行的垂直切片测试。

### In Scope

- 后端工程骨架与配置（FastAPI + SQLAlchemy + Alembic + Pydantic v2）
- 审计领域模型与迁移
- 考试状态机（`ExamAttemptState` / `AttemptItemState`）
- 快照锁定（plan / llm profile / prompt bundle）
- 确定性评分引擎 + CE 聚合 + Evidence 解析
- 分层术语标准化
- Provider Adapter 契约与注册表
- LLM Profile 管理 API（资格状态治理）
- Fake Provider 垂直切片与单元测试

### Out of Scope

- 正式考试工作台 UI
- 完整考试编排业务（出题→语音→评分 全流程路由）
- 真实 Provider 生产接入
- Multi-LLM Benchmark / Qualification 运行
- 数据库重构、生产部署

### Dependencies

- Phase 0 治理基线（GOAL / AGENTS / Source of Truth / ADR / Roadmap）
- Python >= 3.12；前端 Node/npm

### Definition of Done

- 模型无关后端基础可在本地以 Fake Provider 跑通垂直切片
- 关键单测通过（状态机、评分、Evidence、normalization、幂等、审计脱敏、版本不可变）
- Provider 抽象不依赖厂商 SDK；`mimo-v2.5` LLM 明确 `FAILED` 不用于正式评判
- 真实 API Key 不进入仓库

### Required Tests

- 现有 `backend/tests/test_sprint_1a.py` 全部通过
- 配置映射测试（`backend/tests/test_config.py`，Phase 0 新增）

### Gate

Architecture / Code Gate（人工）：核对 GOAL 一致性、ADR 覆盖、无架构偏离、无 Secret 泄漏。

### Stop Condition

Gate 通过或人工批准进入 Sprint 1B 前，停止开发；禁止自动开始 Sprint 1B。
