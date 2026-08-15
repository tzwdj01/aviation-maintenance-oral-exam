# Qualification History（历史资格认证结论）

> Status: ACTIVE
> Owner: AI 评估与质量负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: 模型/语音能力的历史 Qualification 结论登记

本文件登记历史 Qualification 结论，**保留原始结果，整理文档不得修改原始结论**。
原始 Qualification artifacts（数据集、运行脚本、输出目录）为版本化资产，应与本登记表关联保存。

> 注意：`scripts/qualification/`（含 `qualification_v2_output*/` 与 `.env`）已被 `.gitignore`
> 排除，未进入仓库。原始 artifacts 需要在本机/受控存储中保留，并在本表登记引用位置。

## 1. 最近一次 Full Qualification：Qualification V2 Full

- 日期：Sprint 0.5（仓库初始化前）
- 结论登记来源：`backend/app/db/seed.py`（种子数据）

### LLM 评估能力

| 模型 | 结论 | 登记 | 说明 |
| --- | --- | --- | --- |
| `mimo-v2.5` | **FAILED as formal Judge** | `LLMProfile.qualification_status = FAILED`（`qualification_summary.source = qualification_v2_full`） | Coverage、Critical Error、追问与稳定性未达正式 Judge 门槛；仅诊断可用 |

### 语音能力

| 能力 | 结论 | 说明 |
| --- | --- | --- |
| `mimo-v2.5-asr` | `CONDITIONAL_PASS` | 有条件通过 |
| `mimo-v2.5-tts` | `PASS` | 通过 |
| Voice Design / Voice Clone | 独立 optional capability，资格状态单独管理 | 未合格前功能门控，不发送未确认负载 |

## 2. 当前登记状态（Phase 0 时点）

| Profile | Provider | Model | qualification_status | 备注 |
| --- | --- | --- | --- | --- |
| MiMo LLM | MIMO | `mimo-v2.5` | `FAILED` | 不得正式 Judge |
| DeepSeek | DEEPSEEK | `deepseek-v4-pro` | `UNTESTED` | 待独立 Qualification |
| OpenAI | OPENAI | `gpt-5` | `UNTESTED` | 待独立 Qualification |

## 3. 后续 Qualification 登记格式

每次新的 Qualification 运行追加以下记录：

```text
## YYYY-MM-DD — <Qualification 名称>
- Golden Dataset 版本：
- Rubric 版本：
- 评估对象：
- 结论（按指标）：
- 变更（相对于上次）：
- 相关 ADR：
```

## 4. 纪律

- `API_AVAILABLE ≠ QUALIFIED`；正式考试只用 `QUALIFIED`（或受限 `CONDITIONAL`）模型。
- 评估门槛与流程见 `docs/qualification/MODEL_QUALIFICATION.md` 与
  `docs/qualification/SPEECH_QUALIFICATION.md`。
