# Current Sprint

> Status: ACTIVE
> Owner: 项目治理负责人
> Last Reviewed: 2026-08-16（Sprint 1A → Sprint 1B Transition）
> Source of Truth For: 当前 Sprint 范围与完成定义

> 未来任何 Codex 任务结束后不得自行修改本文件进入下一 Sprint；只有用户明确批准才能修改。

## 当前状态（Sprint Transition — APPROVED）

- **Previous Sprint**: Sprint 1A — Model-Independent Core + Multi-Provider Foundation
- **Previous Gate**: PASS（Architecture / Code Gate 已人工批准，`SPRINT_1A_APPROVED = YES`；PR #1 已以 merge commit 合并至 `main`）
- **Status**: **APPROVED**
- **Next Approved Sprint**: **Sprint 1B — MiMo Speech Production Integration**
- 本次变更为治理文档状态转换（`docs: advance project to sprint 1b`），不含 Sprint 1B 业务代码。

## Sprint 1A（已完成 — 历史定义，仅供追溯）

> Sprint 1A 已通过 Architecture / Code Gate 并合并至 `main`（merge commit `0ff02d2`）。以下定义保留历史，不再作为当前工作范围。

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

- `backend/tests/test_sprint_1a.py`、`backend/tests/test_governance_gate.py`、`backend/tests/test_config.py` 全部通过（合并时 23 passed）

### Gate

Architecture / Code Gate（人工）— 已 PASS。

### Stop Condition

Gate 通过后停止，等待人工批准进入 Sprint 1B。

## Sprint 1B — MiMo Speech Production Integration（当前）

### Goal

将 MiMo Speech（ASR / TTS）从 Provider Adapter 契约推进到**生产级语音集成**：
真实 Provider 调用验证、服务端配置/密钥注入、音频上传校验与受控存储、
ASR 任务编排与转写采用、术语标准化串联、TTS 文本降级，并通过 Speech Gate。

### In Scope

- MiMo ASR / TTS 真实接入验证（`mimo-v2.5-asr` / `mimo-v2.5-tts`；Base URL 见 `docs/CONFIGURATION.md`）
- 服务端配置与密钥注入（环境变量 / Secret Manager；`docs/SECURITY.md`）
- 音频上传校验、受控存储与短期访问 URL（Media Service 雏形）
- ASR 任务（`TaskJob`）编排：转写保存、显式采用（单一 adopted）、术语标准化串联（Raw ASR 永不覆盖）
- TTS 生成与题干文本降级路径
- 语音相关测试（ASR/TTS 契约、错误映射、低置信/空转写路径）

### Out of Scope

- 完整考试编排路由（Sprint 1D / 2）
- Multi-LLM Qualification 运行（Sprint 1C）
- 前端正式工作台（Sprint 3）
- VoiceClone / VoiceDesign 正式启用（未合格前保持功能门控）
- 生产部署 / worker 大规模实现（Sprint 2 / 4）

### Dependencies

- Sprint 1A（已完成并合并 `main`）
- MiMo Token Plan 账号与真实密钥（仅环境 / Secret Manager 注入）
- `docs/providers/mimo-speech.md`、`docs/CONFIGURATION.md`、`docs/SECURITY.md`
- Sprint 1A TECH_DEBT 中与语音相关的登记项

### Definition of Done

- 在本地或受控 TEST 环境以真实 MiMo 完成一次可审计的 ASR 转写 + TTS 合成验证
- Raw ASR 保留、单一转写采用、normalization 串联（评分仍使用已采用标准化文）
- TTS 失败降级为题干文本且不阻塞流程
- 真实 Key 不入仓库；浏览器不持有 Provider Secret
- Speech Gate 评审材料齐备（调用审计、错误映射、低置信处理路径）

### Required Tests

- 现有后端测试（23）继续通过
- 新增语音相关单测/契约测试（Adapter 错误映射、音频校验、转写采用、TTS 降级）
- 真实 MiMo 调用为本地可选验证，不进 CI 默认流程（`docs/TESTING.md`）

### Gate

Speech Gate（人工）：核对 MiMo 语音可用性、审计完整性、无 Secret 泄漏、无架构偏离。

### Stop Condition

Speech Gate 通过或人工批准进入 Sprint 1C 前停止；禁止自动开始 Sprint 1C。
