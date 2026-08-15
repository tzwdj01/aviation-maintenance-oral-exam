# Providers（外部 AI / 语音 Provider 层）

> Status: ACTIVE
> Owner: AI/Provider 架构负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: Provider 层职责与能力索引

## 分层

- **Business Domain（Exam Engine）**：不得依赖任何具体 AI 厂商。
- **Speech Provider Layer**：统一接口 `SpeechProvider`（`transcribe` / `synthesize`）。
- **Evaluation Provider Layer**：统一接口 `EvaluationProvider`
  （`evaluate_coverage` / `detect_critical_errors` / `evaluate_quality_risk` /
  `decide_follow_up` / `final_assessment`）。

业务服务只与统一接口交互；具体 Provider 通过 `ProviderRegistry` 按 `LLMProfile` 快照显式选择。
真实 API Key 只存在于服务端环境/密钥管理，浏览器永远不得持有 Provider Secret。

## 能力索引

| Provider | 用途 | 状态 | 文档 |
| --- | --- | --- | --- |
| Xiaomi MiMo | 语音（ASR/TTS） | 核心语音 Provider | [`mimo-speech.md`](mimo-speech.md) |
| Xiaomi MiMo | LLM 评估 | 仅诊断（`FAILED`，非正式 Judge） | [`mimo-llm.md`](mimo-llm.md) |
| DeepSeek | LLM 评估 | `UNTESTED`（待 Qualification） | [`deepseek.md`](deepseek.md) |
| OpenAI | LLM 评估 | `UNTESTED`（待 Qualification） | [`openai.md`](openai.md) |

## Provider 通用责任

每个 Provider Adapter 负责：认证头、序列化、超时、响应标准化、供应商错误映射、request ID 提取。
服务层负责：持久化、业务状态机、schema 校验、重试策略、人工复核流转。

## 硬性规则

- 调用只能发生在后端（`Frontend → Backend → Provider`）。
- **禁止 Silent Provider Failover**：失败进入 `TaskJob FAILED` 或 `AttemptItem NEEDS_ATTENTION`；
  未来 fallback 必须记录 `original_provider` / `fallback_provider` / `mixed_provider=true` /
  `needs_human_review=true` 并经过 ADR。
- 模型「能调用」≠「可正式使用」：正式考试只用经过 Qualification Gate 的模型。
- Provider 认证从环境变量注入，审计记录中必须脱敏。

## 模型与端点（摘要，完整契约见各文档与 `docs/CONFIGURATION.md`）

| 能力 | 模型 | 端点 |
| --- | --- | --- |
| MiMo ASR | `mimo-v2.5-asr` | `https://token-plan-cn.xiaomimimo.com/v1/chat/completions` |
| MiMo TTS | `mimo-v2.5-tts` | 同上 |
| MiMo Voice Design | `mimo-v2.5-tts-voicedesign` | 功能门控，未合格 |
| MiMo Voice Clone | `mimo-v2.5-tts-voiceclone` | 功能门控，未合格 |
| DeepSeek | `DEEPSEEK_DEFAULT_MODEL` | `https://api.deepseek.com/chat/completions` |
| OpenAI | `OPENAI_DEFAULT_MODEL` | `https://api.openai.com/v1/responses` |
