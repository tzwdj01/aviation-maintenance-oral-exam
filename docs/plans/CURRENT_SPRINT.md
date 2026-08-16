# Current Sprint

> Status: ACTIVE
> Owner: 项目治理负责人
> Last Reviewed: 2026-08-16（Sprint 1B → Sprint 1C Transition）
> Source of Truth For: 当前 Sprint 范围与完成定义

> 未来任何 Codex 任务结束后不得自行修改本文件进入下一 Sprint；只有用户明确批准才能修改。

## 当前状态（Sprint Transition — APPROVED）

- **Previous Sprint**: Sprint 1B — MiMo Speech Production Integration
- **Previous Gate**: **CONDITIONAL_PASS**（Speech Gate 已人工批准，`SPRINT_1B_APPROVED = YES`；
  PR #4 已以 merge commit 合并至 `main`，merge commit `6ab873f`）
- **Status**: **APPROVED**
- **Next Approved Sprint**: **Sprint 1C — Multi-LLM Judge Qualification**
- **保留**：`SECOND_SPEAKER_VALIDATION = DEFERRED`（经人工批准延期；**不是 Sprint 1C blocker**，
  但仍是 Pilot / Canary / Production 前的硬性 Gate，登记于
  `docs/qualification/SPEECH_QUALIFICATION.md`、`docs/plans/TECH_DEBT.md`）
- 本次变更为治理文档状态转换（`docs: advance project to sprint 1c`），不含 Sprint 1C 业务代码。

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

## Sprint 1B — MiMo Speech Production Integration（已完成 — 历史定义，仅供追溯）

> Sprint 1B 已通过 Speech Gate（`CONDITIONAL_PASS`，`SPRINT_1B_APPROVED = YES`）并合并至
> `main`（merge commit `6ab873f`）。以下定义保留历史，不再作为当前工作范围。

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

## Sprint 1C — Multi-LLM Judge Qualification（当前）

### Goal

在完全相同的 Golden Dataset、Rubric、Evidence、Critical Error 和 Prompt Bundle 条件下，
对 **MiMo / DeepSeek** 两个评估 Provider 执行**独立、可复现、可审计**的
Formal Judge Qualification，确定各模型作为正式评分 Judge 的资格边界
（`docs/qualification/MODEL_QUALIFICATION.md`）。

> **Scope 决策（用户批准）**：Sprint 1C 的 Formal Judge candidates 仅为 **MiMo + DeepSeek**。
> `OPENAI_SPRINT_1C_STATUS = OUT_OF_SCOPE_BY_USER`——不是 Provider FAIL，也不是
> Credential blocker；OpenAI Provider adapter 与既有架构支持**不删除、不标记 FAILED**，
> 仅本 Sprint 不执行其 Qualification。未来如需重新纳入 OpenAI，必须另行人工批准并执行
> 独立 Qualification。MiMo 与 DeepSeek 在**同 Golden / 同 Prompt / 同 Schema / 同 Gate v1 /
> 同 Evidence / 同 CE rules** 下公平比较。

### 必须保持的原则

- AI 不拥有标准答案；AI 不直接生成正式 numeric score；server-side deterministic scoring
- Evidence quote 由服务端 exact-match 并计算 offset；Critical Error 不允许后续 AI 自动清除
- Attempt 在 `READY` 时锁定 provider/model/profile/prompt/qualification snapshot
- `API_AVAILABLE ≠ QUALIFIED`；禁止 Silent Provider Failover
- 不得为某 Provider PASS 修改 Golden labels 或降低 Qualification threshold

### In Scope

- MiMo / DeepSeek 评估 Provider 的独立 Qualification 运行
  （同一 Golden Dataset / Prompt Bundle / Schema / Gate v1 / Evidence / CE rules）
- 同一 Golden Dataset benchmark harness（Question / Rubric Snapshot / Evidence rules /
  Critical Error rules / Prompt Bundle / evaluation schema / qualification thresholds 全量对齐）
- Prompt Bundle versioning
- structured-output contract verification（`extra="forbid"` schema 校验）
- evidence validation（quote exact-match + offset）
- CE benchmark / follow-up benchmark / decision stability benchmark
- 指标化结果（与 `docs/qualification/MODEL_QUALIFICATION.md` 一致，不另建第二套标准）：
  Coverage Exact Agreement、Major Disagreement、Evidence Validity、Critical Error Recall、
  Critical Error Precision、Follow-up Accuracy、Answer Leakage、Prompt Injection Resistance、
  Structured Output Validity、Decision Stability、Latency（P50/P95）、Provider Failure Rate
- 资格登记与更新：`LLMProfile.qualification_status` / `qualification_summary`、
  `docs/qualification/MODEL_QUALIFICATION.md`、`docs/qualification/qualification-history.md`
- 可复现与审计：运行脚本、manifest、results、metrics 入库（不含 Key）

### Out of Scope（Sprint 1C 不负责）

- Speech remediation
- 第二说话人 Speech Qualification（S02，`DEFERRED` — 非 1C blocker，仍为
  Pilot/Canary/Production 前硬 Gate）
- Sprint 1D full orchestration
- 完整考试 UI
- Question Bank 管理
- RBAC 大规模开发
- RAG
- 自动题目生成
- Production deployment
- Pilot / Canary
- Sprint 2+

### Dependencies

- Sprint 1B（已完成并合并 `main`；Speech Gate `CONDITIONAL_PASS`）
- MiMo / DeepSeek 真实 Key（仅环境 / Secret Manager / gitignored .env 注入；禁止入库；
  OpenAI 不在本 Sprint 范围）
- 版本化 Golden Dataset / Rubric / Evidence / Critical Error / Prompt Bundle
- `docs/qualification/MODEL_QUALIFICATION.md`、`docs/TESTING.md`、`docs/adr/0003-*`、`docs/adr/0005-*`

### Definition of Done

- 三个 Provider 在同一 Golden/Rubric/Evidence/CE/Prompt 条件下的 Qualification 运行完成
- 每 Provider 的指标与资格结论登记（`QUALIFIED` / `CONDITIONAL` / `FAILED` 等）
- 正式考试只允许使用通过 Model Qualification Gate 的模型
- 真实 Key 不入仓库；无 Secret 泄漏

### Required Tests

- 现有后端测试继续通过
- Qualification 指标计算与 manifest 确定性单测
- Golden labels 不可变（不得为通过而修改金标）
- Fake Provider 离线 Qualification 垂直切片
- 真实 Provider 调用为本地可选验证，不进 CI 默认流程（`docs/TESTING.md`）

### Gate

Model Qualification Gate（人工）：核对三 Provider 资格结论、Golden 对齐、审计完整性、
无 Secret 泄漏、无架构偏离。

### Stop Condition

Model Qualification Gate 通过或人工批准进入 Sprint 1D 前停止；禁止自动开始 Sprint 1D。
