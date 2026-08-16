# Roadmap（长期路线图）

> Status: ACTIVE
> Owner: 项目治理负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: 长期路线图与 Gate 定义

> 只有用户明确批准才能修改本路线图或进入下一 Sprint；Codex 任务结束后不得自行推进。

## 主线路线

```text
Phase 0  Project Governance & Architecture Baseline
   │
   ▼
Sprint 1A  Model-Independent Core + Multi-Provider Foundation   ✅ Architecture/Code Gate PASS
   │
   ▼
Sprint 1B  MiMo Speech Production Integration   ✅ Speech Gate CONDITIONAL_PASS（已合并 main）
   │
   ▼
Speech Gate
   │
   ▼
Sprint 1C  Multi-LLM Qualification（MiMo vs DeepSeek vs OpenAI）   ← 当前（Sprint Transition APPROVED）
   │
   ▼
Model Qualification Gate
   │
   ▼
Sprint 1D  End-to-End Vertical Slice
           Question → TTS → Voice Answer → ASR → Normalize → Evaluate
           → Follow-up → Final Assess → Server Score → Human Review
   │
   ▼
Sprint 2   Question Bank & Exam Management
   │
   ▼
Sprint 3   Production Oral Exam UX
   │
   ▼
Sprint 4   Production Hardening
   │
   ▼
Sprint 5   Pilot / Canary / Controlled Rollout
```

## 阶段状态

| 阶段 | 状态 |
| --- | --- |
| Phase 0 | ✅ 完成（Governance Gate 通过） |
| Sprint 1A | ✅ 完成（Architecture/Code Gate PASS，已合并至 `main`） |
| Sprint 1B | ✅ 完成（Speech Gate `CONDITIONAL_PASS`，已合并至 `main`） |
| Sprint 1C | 🚧 当前（Sprint Transition APPROVED；Model Qualification Gate 待过） |
| Sprint 1D–5 | 未开始（待批准） |

> `SECOND_SPEAKER_VALIDATION = DEFERRED`（经人工批准）：不是 Sprint 1C blocker，
> 但仍是 Pilot / Canary / Production 前的硬性 Gate（登记于
> `docs/qualification/SPEECH_QUALIFICATION.md` 与 `docs/plans/TECH_DEBT.md`）。

## Gate 定义

每个 Gate 是进入下一阶段的人工审查点，至少核对：

- 与 GOAL / Accepted ADR 的一致性
- 当前 Sprint 的 Definition of Done
- 测试与回归通过（含 Golden Dataset，如适用）
- 无未登记的架构偏离（Drift Check = PASS）
- 无 Secret 泄漏
