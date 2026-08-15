# Speech Qualification（语音能力资格认证）

> Status: ACTIVE
> Owner: 语音集成与质量负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: ASR/TTS 能力资格认证

## 1. 目的

语音能力（ASR 转写、TTS 合成）在用于正式口试前必须经过资格评估，确保航空术语识别、
口音鲁棒性与合成可听性满足要求。

## 2. 当前结论（历史）

- `mimo-v2.5-asr`：历史 Qualification 结论 `CONDITIONAL_PASS`（有条件通过）。
- `mimo-v2.5-tts`：历史 Qualification 结论 `PASS`。
- VoiceDesign / VoiceClone：独立 optional capability，资格状态单独管理；在参数确认并单独
  Qualification 前保持功能门控，不发送未确认的负载。

详见 [`docs/qualification/qualification-history.md`](qualification-history.md)。

## 3. ASR 评估维度

- 航空术语识别率（基于版本化词典与金标音频）
- 口音/方言鲁棒性
- 低置信识别是否被安全保留（不静默篡改）
- 空转写/失败路径是否触发可恢复状态

## 4. TTS 评估维度

- 自然度与可理解性
- 题干/追问朗读准确性（专业术语发音）
- 失败降级路径（保留文本）

## 5. 纪律

- 原始 Qualification 产物不得被修改；整理文档不得改变原始结论。
- 语音能力变更需重新 Qualification，并记录到 `qualification-history.md`。
