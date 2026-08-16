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

## 2.1 治理状态（2026-08-16，Sprint 1B 收口）

- `HUMAN_VALIDATION_S01 = READY`：S01 真人语音已完成采集并通过基线/回归 Qualification。
- `SECOND_SPEAKER_VALIDATION = DEFERRED`：经人工批准本阶段延期；**不得伪装为已完成**。
- **硬性 Gate**：在任何 Pilot / Canary / Production 部署前，必须完成至少第二名
  自愿说话人 S02 的 Qualification。此 Gate 同时登记于
  `docs/qualification/qualification-history.md` 与 `docs/plans/TECH_DEBT.md`。

## 2.2 S01 是 Validation Dataset，不是 Normalizer 映射来源

- S01 真人语音用于**发现问题**与**评估效果**。
- S01 单说话人的单个错误**不得**直接作为 fuzzy Normalizer 自动替换规则的安全证明。
- 安全 Normalizer 规则集（`builtin-v4`）grounded 于：版本化 Golden corpus、
  已确认的历史 failure corpus、TTS pronunciation benchmark 与安全确定性规则
  （拼写展开/连字符/机型紧凑形式的可逆编码）。
- 无法高置信确认的候选一律降级为 review-only（warning），不静默改写。

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
- S02 第二说话人验证是 Pilot/Canary/Production 前的硬性 Gate（当前 DEFERRED）。
