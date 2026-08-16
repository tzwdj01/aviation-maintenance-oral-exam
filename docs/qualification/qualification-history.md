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

## 4. Sprint 1B 正式 Speech Qualification（Run 2026-08-16-s1b-qual-v1）

- Golden Dataset 版本：`speech-qual-2026-08-16-v1`
  （27 个 ASR 用例 A–E 类 + 10 个 TTS 用例；另含 5 个真人语音条件用例 asr-h1..h5）
- Rubric 版本：不适用（语音资格评估，无评分 Rubric）
- Normalizer ruleset version：`builtin-v1`；Vocabulary version：`builtin`（无已发布业务词典）
- 评估对象：`mimo-v2.5-asr` / `mimo-v2.5-tts`（真实 MiMo 调用，2026-08-16）
- 结论（按指标）：
  - **ASR**：request success 100%（27/27）；empty transcript 0%；terminal failure 0%；
    retry 0%；latency P50 702ms / P95 860ms；raw text similarity 0.865；
    raw aviation term accuracy **0.611**；normalized aviation term accuracy **0.611**；
    normalization improvement **0.000**；false correction 0。
  - **TTS**：api success 100%（10/10）；valid audio 100%；empty audio 0%；
    latency P50 1609ms / P95 2800ms；TTS→ASR round-trip raw similarity 0.883；
    round-trip aviation term accuracy **0.717**。
  - 真人语音用例（正常语速/较快/停顿/轻度口音/环境噪声）：本环境无真人音频，
    记录 `not_evaluated`（需要外部 `--audio-dir` 提供音频）。
- 结论：**ASR = CONDITIONAL_PASS；TTS = CONDITIONAL_PASS；
  VoiceDesign = NOT_TESTED；VoiceClone = NOT_TESTED / NOT_AUTHORIZED；
  SPEECH_GATE = PASS_WITH_ACTIONS**。
- 已知限制：
  - 术语识别弱点（TTS→ASR 回环）：`CDL→四百五十`、`MPD→NPD`、`CFM56→Swiflam五六`、
    `CFM56-7B→七字节`、`B737-800→B七三七负八百`、`B737NG→B-737NG`、`MEL→ML`、`EO→E U`、
    `适航指令→试航指令`、`最低设备清单→对低设备清单`。
  - `builtin-v1` normalizer 对这些错误模式无修复规则：normalization improvement = 0.0
    （0 假正 / 0 危险替换，但无正确率提升）。
  - 口音/方言鲁棒性、环境噪声、真人语速维度未评估（无真人音频样本）。
- 变更（相对于上次）：上次 Qualification V2 Full（ASR=CONDITIONAL_PASS / TTS=PASS）；
  本次为 Sprint 1B 正式资格评估（真实 API + 版本化 Dataset + 指标化 artifacts）；
  TTS 结论由 PASS 调整为 CONDITIONAL_PASS（缩写/型号发音回环 71.7%）。
- 相关 ADR：`0004`（MiMo 核心语音 Provider）、`0005`（禁止 Silent Failover）。
- Artifacts：`artifacts/qualification/speech/2026-08-16-s1b-qual-v1/`
  （manifest.json / results.json / metrics.json / failures.json / normalization-errors.json / report.md；
  音频不入仓库，仅 hash/metadata）。

### 语音能力当前登记（2026-08-16 时点）

| 能力 | 历史结论 | Sprint 1B 正式结论 | 说明 |
| --- | --- | --- | --- |
| `mimo-v2.5-asr` | `CONDITIONAL_PASS` | `CONDITIONAL_PASS` | 管线/契约达标；术语正确率 61.1%、normalizer 无提升、真人语音维度未评估 |
| `mimo-v2.5-tts` | `PASS` | `CONDITIONAL_PASS` | API/音频 100% 达标；缩写/型号发音回环 71.7%，需人工听测复核 |
| Voice Design | 独立管理（门控） | `NOT_TESTED` | 未启用、未测试 |
| Voice Clone | 独立管理（门控） | `NOT_TESTED / NOT_AUTHORIZED` | 无授权参考音频，未测试 |

## 5. 纪律

- `API_AVAILABLE ≠ QUALIFIED`；正式考试只用 `QUALIFIED`（或受限 `CONDITIONAL`）模型。
- 评估门槛与流程见 `docs/qualification/MODEL_QUALIFICATION.md` 与
  `docs/qualification/SPEECH_QUALIFICATION.md`。
