# GOAL — Aviation Maintenance Oral Exam（航空维修放行人员 AI 口试系统）

> Status: ACTIVE（本项目最高级长期目标文档）
> Owner: 项目治理负责人（Repo Owner）
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: 产品战略与项目边界
>
> **本文件保持稳定，不得被普通 Sprint 随意修改。** 产品战略级变更必须通过正式 ADR 并经人工批准。

## 1. 产品定位

建立**生产级「航空维修放行人员 AI 口试系统」**，用于：

- 维修放行人员训练与模拟口试
- 考评员辅助评估
- 结构化知识点评价
- 风险知识点识别
- 受控动态追问
- 考试过程完整审计
- 人工复核与最终结论

系统是口试训练与辅助评估工具。在完成适用资质、题库治理、评估验证及人工复核流程之前，
**不将 AI 作为未经人工治理的最终授权决策者**。

## 2. 业务核心闭环（North Star Pipeline）

一切后续开发都必须服务于以下闭环，不得偏离：

```text
Approved Question Bank
→ Exam Assembly（随机组卷 + 快照锁定）
→ TTS Question
→ Candidate Voice Answer
→ ASR
→ Aviation Terminology Normalization
→ Structured Rubric Evaluation（四阶段：Coverage / Critical Error / Quality-Risk / Follow-up）
→ Controlled Dynamic Follow-up（≤2 次，可追溯）
→ Final Assessment
→ Server-side Scoring（确定性规则引擎）
→ Human Review（append-only）
→ Final Result（能力报告 + 复核状态）
```

## 3. 项目边界（不得演变成）

除非未来经过正式 ADR 并经人工批准改变产品战略，本项目不得逐步演变成：

- 通用聊天机器人
- 通用 RAG / 自由问答助手
- AI 自由出题工具
- 无约束 Agent 平台
- 无人值守的放行资质认定或自动发证系统

## 4. 不可突破的 AI 原则

### 原则 A：AI 不拥有正式标准答案

正式的主问题、Rubric、RubricPoint、Critical Error Rule、技术标准与评分权重，
必须来自**经过批准和版本控制的数据**。LLM 不得自行创建新的正式考试标准。

### 原则 B：AI 不拥有正式数字分数

LLM 可以输出 `covered / partial / missing / uncertain`、evidence quote、reasoning、
CE analysis 与 follow-up suggestion；**不得让 LLM 输出一个数字后直接作为正式分数**。
正式数字分数必须由服务端以
`Rubric Snapshot + Point Status + Weight / Partial Weight` 确定性计算。

### 原则 C：考试必须完整可审计

必须能够追溯：Question、Question Version、Rubric Version、Exam Plan Version、
Prompt Version、Provider、Model、Qualification Status、Audio、Raw ASR、
Normalized Transcript、Evidence Quote、AI Structured Output、Critical Error Analysis、
Server Score、Follow-up、Human Review、Override、Final Result 以及全部 timestamps。

## 5. 分层架构约束

### Business Domain（Exam Engine）

负责 Question / Rubric / Exam Plan / Attempt / Answer / State Machine / Evidence /
Scoring / Audit / Human Review。**不得依赖任何具体 AI 厂商。**

### Speech Provider Layer

统一接口 `SpeechProvider`；当前主要 Provider 为 Xiaomi MiMo：

- ASR：`mimo-v2.5-asr`
- Standard TTS：`mimo-v2.5-tts`
- Optional Voice Design：`mimo-v2.5-tts-voicedesign`
- Optional Voice Clone：`mimo-v2.5-tts-voiceclone`

### Evaluation Provider Layer

统一接口 `EvaluationProvider`；未来支持 Xiaomi MiMo、DeepSeek、OpenAI API。
业务服务不得直接依赖具体 Provider SDK/API。

## 6. 关键治理红线（详见各 Source of Truth）

- 模型「能调用」≠「可正式使用」：正式考试只允许经过 Qualification Gate 的模型。
- Attempt 进入 `READY` 后锁定 Provider / Model / Qualification / Prompt Bundle，后续改动不得影响进行中或历史考试。
- 禁止 Silent Provider Failover；任何 fallback 必须记录、标记 `needs_human_review=true` 并经过 ADR。
- Evidence offset 由服务端解析（0 匹配=INVALID / 1 匹配=VALID / 多匹配=AMBIGUOUS）。
- Critical Error 一旦 `TRIGGERED` 粘性保持，仅人工可 override；Review 必须 append-only 且附理由。
- Raw ASR 永不覆盖；航空术语修正不得危险全局替换，低置信修正保留为 candidate/review。
- API Key 与 Provider Secret 只存在于服务端环境/密钥管理；禁止进入 Git、Markdown、代码、前端、日志与审计原文。
- 浏览器永远不得持有 Provider Secret：`Frontend → Backend → External AI Provider`。

## 7. 演进与修订

- 本文档的修改必须经项目治理负责人批准，并记录变更。
- 产品战略 / 架构级变更遵循 `docs/adr/README.md` 的 ADR 流程。
- 各域详细规范见 `docs/README.md` 索引与 `AGENTS.md` 路由规则。
