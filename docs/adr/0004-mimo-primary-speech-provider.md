# 0004. MiMo 为核心语音 Provider

> Status: ACCEPTED
> Date: 2026-08-16（Phase 0 Governance Baseline）
> Deciders: 语音集成负责人

## Status

Accepted（固化自 `docs/mimo-integration.md` 与 `backend/app/ai/providers/speech/` 的既有实现）。

## Context

口试闭环需要 ASR（回答转写）与 TTS（题干朗读）；项目选择 Xiaomi MiMo 语音能力。

## Decision

MiMo Speech 作为核心语音 Provider，由 `SpeechProvider` 承载：

- ASR：`mimo-v2.5-asr`
- Standard TTS：`mimo-v2.5-tts`
- Optional Voice Design / Voice Clone：独立 optional capability，资格状态单独管理，未合格前功能门控。

Base URL：`https://token-plan-cn.xiaomimimo.com/v1`。调用只发生在后端；Key 只存在于服务端环境。

## Alternatives

- 其他语音厂商（未选定；Provider 抽象允许未来替换）。

## Consequences

- 语音能力与业务解耦，可替换。
- VoiceDesign/VoiceClone 在参数确认并 Qualification 前不发送未确认负载。

## Migration Impact

无（Phase 0 仅文档化；配置命名对齐见 `docs/CONFIGURATION.md`）。

## Testing Impact

测试：Fake Speech 垂直切片；真实 MiMo 调用在本地可选验证，不进 CI 默认流程。
