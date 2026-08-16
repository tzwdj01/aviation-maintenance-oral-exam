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

## 5. Sprint 1B — S01 真人语音 ASR Qualification + Remediation（Run 2026-08-16-s1b-s01-qual-v3）

- Golden Dataset 版本：`speech-qual-2026-08-16-v1`（S01 真人 10 例；外部录音目录
  `C:\Users\Lucky\Documents\speech-qualification-human\S01`，**真人 WAV 不入仓库**，
  仅提交 manifest/hash/元数据/金标文本）
- 评估对象：`mimo-v2.5-asr`（S01 真人语音 10 例，NORMAL×5 / FAST×2 / PAUSE×1 /
  MILD_OFFICE_NOISE×2）；`mimo-v2.5-tts`（TTS→ASR 回环 10 例）
- Normalizer ruleset：`builtin-v1` → `builtin-v2` → `builtin-v3`（当前 `builtin-v3`）；
  Vocabulary：`builtin`
- 结论（按指标，S01 真人 ASR）：
  - request success **100%**（10/10）；empty 0%；retry 0%；terminal failure 0%；
    latency P50 **750ms** / P95 **884ms**
  - raw aviation term accuracy **0.525**；raw text similarity **0.890**
  - normalized term accuracy：v1 **0.550** / v2 **0.550** / v3 **0.683**
  - **normalizer remediation（v1→v3）：+0.133**；false correction **0**（全部版本）；
    review-required rate 0.1 → 0.5（低置信候选转人工复核，不静默改写）
- 结论（TTS 发音 remediation）：
  - before（默认提示词+原文）：round-trip term accuracy **0.75**，raw similarity 0.876
  - after（`spell_out_aviation` 拼读展开）：round-trip term accuracy **0.80**（+0.05），
    10/10 成功；raw similarity 0.814（拼读后文本与金标差异所致，normalized similarity 0.865）
  - 发音指导提示词方案实测无增益且引入 1 次失败，已记录弃用
- 结论：**ASR = CONDITIONAL_PASS（S01 真人已评估，含真人语音维度）**；
  **TTS = CONDITIONAL_PASS**（发音 remediation 生效但幅度有限，需人工听测）；
  **SPEECH_GATE = PASS_WITH_ACTIONS**
- 已知限制：
  - 剩余未修复：`MER→MEL`、`故障法流→故障保留`、`SIM→FIM`、`MTD→MPD`、
    `CF56-7B→CFM56-7B` 均为 review 候选（已告警，未静默改写）。
  - `builtin-v3` 规则基于 S01 单一说话人观测推导，需独立说话人交叉验证（S02）。
  - 真人语料仅 10 例，统计功效有限；噪声/语速条件各 2 例。
- 变更（相对于上次）：Sprint 1B 正式 Qualification（Run `2026-08-16-s1b-qual-v1`，
  TTS 合成语料）新增 S01 真人语音评估 + 规则集 v2/v3 + TTS 拼读 remediation。
- 相关 ADR：`0004`、`0005`。
- Artifacts：`artifacts/qualification/speech/2026-08-16-s1b-s01-qual-v1/`（原始 S01 运行）、
  `.../2026-08-16-s1b-s01-qual-v2/`（规则集重算 + 拼读 after）、
  `.../2026-08-16-s1b-s01-qual-v3/`（最终：v3 规则 + review 告警）。
  > **治理修订**：`builtin-v3` 中的 S01 单说话人推导自动规则（失航/释行指令→适航指令）
  > 已被降级为 review-only 候选（S01 只能发现/评估，不能单独证明 fuzzy rule 安全）；
  > 最终 SAFE 规则集为 `builtin-v4`。权威结果见下方 §6 的
  > `2026-08-16-s1b-human-s01-v1`（baseline）与 `2026-08-16-s1b-human-s01-v2`（安全回归）。

## 6. S01 安全治理回归（Run 2026-08-16-s1b-human-s01-v1 baseline / -v2 安全回归）

- 治理状态：`HUMAN_VALIDATION_S01 = READY`；`SECOND_SPEAKER_VALIDATION = DEFERRED`
- Dataset：`speech-qual-2026-08-16-v1`（S01 真人 10 例，外部录音目录，真人 WAV 不入仓库）
- Normalizer ruleset：baseline = `builtin-v1`（未针对 S01 调优）；安全规则集 = `builtin-v4`
- **baseline（builtin-v1）**：term accuracy **0.550**（improvement +0.025）；按条件分组：
  NORMAL(n=5) 0.400 / FAST(n=2) 0.250 / PAUSE(n=1) 0.750→1.000 / MILD_OFFICE_NOISE(n=2) 1.000
- **v2 安全回归（builtin-v4）**：term accuracy **0.5833**（baseline→v2 **+0.0333**）；
  **false correction 0**；review-required 0.1→0.7（S01 单说话人候选降级为 review，
  不静默改写）；success 100%、empty 0%、P50 750ms / P95 884ms；分组：
  NORMAL 0.400 / FAST 0.250→0.4167（B-737-800 安全规则修复）/ PAUSE 1.000 / NOISE 1.000
- **TTS 发音 benchmark（tts-pron-bench-v1，render-v1）**：回环术语正确率
  **0.75 → 0.80（+0.05）**，10/10 成功；normalized similarity 0.904
- 说明：S01 v2 属于 **remediation 后回归验证，不是完全独立的最终 holdout**；
  独立第二说话人验证由 S02 承担（DEFERRED）。
- Artifacts：`artifacts/qualification/speech/2026-08-16-s1b-human-s01-v1/`、
  `.../2026-08-16-s1b-human-s01-v2/`、`.../s01-remediation-comparison.json`

## 7. S02 第二说话人验证 — DEFERRED（Pilot/Canary 前硬 Gate）

- 状态：**DEFERRED（经人工批准延期）**，不得视为已完成。
- 现状：`C:\Users\Lucky\Documents\speech-qualification-human\S02\S02_case01.wav`
  为 44 字节空占位（duration_ms=0），未构成有效样本。
- 处理：S01 单说话人结论保留 `CONDITIONAL_PASS`；S02 交叉验证需在补充有效录音后
  单独执行，并在本文件追加新记录。
- **硬性 Gate（不得遗忘/删除）**：在任何 Pilot / Canary / Production 部署前，
  必须完成至少第二名自愿说话人 S02 的 Qualification；该 Gate 已在
  `docs/qualification/SPEECH_QUALIFICATION.md` 与 `docs/plans/TECH_DEBT.md` 登记。

## 8. Sprint 1C — Multi-LLM Judge Qualification（Run 2026-08-16-s1c-judge-v1）

- **RUN_VALIDITY = INVALIDATED_HARNESS_DEFECT**（人工 Harness Review 结论）：
  该 Run 保留为 diagnostic artifact，**不得作为 Sprint 1C 正式 MiMo Qualification FAIL 证据**。
  原因：`StructuredEvaluationProvider` 仅向 Provider 发送 `candidate_text`，未发送完整
  Trusted Rubric / CE / Evidence context；JSON-mode Provider 未收到完整业务 output schema，
  导致 MiMo 生成自定义 JSON shape。Harness 修复后需重跑（`judge-qual-golden-v1` 不变）。
  **历史 Qualification V2 的 `MiMo = FAILED` 保持不变**，与本次被作废的 Run 明确区分。
- Golden Dataset：`judge-qual-golden-v1`（10 例，覆盖场景 A–H；Question / Rubric
  Snapshot / Evidence rules / Critical Error rules / Prompt Bundle `prompt-bundle-v1` /
  evaluation schema 全量对齐；金标不可修改）
- 评估对象：`mimo-v2.5`（`mimo_llm_model`）、`deepseek-v4-pro`、`gpt-5`
- 结论（按 Provider）：
  - **MiMo `mimo-v2.5`**：`RUN`（INVALIDATED）— 10/10 case FAILED（Harness 缺陷所致）
    - structured output validity **0.0**（全部 10 例首个 Pass 输出未通过
      `extra="forbid"` schema 校验：模型返回 `知识点/points/assessment` 等自定义结构，
      非约定 `point_assessments[]` 契约）
    - provider failure rate **1.0**；coverage/CE/follow-up/evidence 指标不可用
    - **provisional = FAIL**（零容忍：structured output schema 失败；与历史
      Qualification V2 Full 的 `FAILED` 结论一致）
  - **DeepSeek `deepseek-v4-pro`**：`NOT_RUN`（`DEEPSEEK_API_KEY` 未配置；
    `API_AVAILABLE ≠ QUALIFIED`）
  - **OpenAI `gpt-5`**：`NOT_RUN`（`OPENAI_API_KEY` 未配置）
- 说明：本 Run 为 Sprint 1C Judge Qualification 的实现 + MiMo 执行；
  **三 Provider 完整对比仍需 DeepSeek / OpenAI Key 配置后重跑同一 Golden Dataset**。
- Artifacts：`artifacts/qualification/judge/2026-08-16-s1c-judge-v1/`
  （manifest / results / metrics / failures / report；不含 Key）
- 相关 ADR：`0003`（多 Provider 评估架构）、`0005`（禁止 Silent Failover）。

### 8.1 Sprint 1C Harness Remediation（Gate v1 冻结 + Formal-Run Ready）

- `MODEL_QUALIFICATION_GATE_VERSION = v1` 已冻结于
  `docs/qualification/MODEL_QUALIFICATION.md` §5.1（QUALIFIED / CONDITIONAL 阈值表 +
  零容忍条款）。
- 修复：`EvaluationRequest` 携带 question/critical_error_rules/prior_analysis；
  `StructuredEvaluationProvider` 构建共享 `TRUSTED_EVALUATION_CONTEXT`
  （rubric + allowed IDs + CE rules + Evidence rules + `output_type.model_json_schema()` +
  prompt version），候选回答只在 `UNTRUSTED_CANDIDATE_DATA` 边界。
- Formal-Run invariants：SMOKE 前置、稳定性子集=全部 10 例、每 case ≥3 次、
  Decision Stability 覆盖 Coverage+CE+Follow-up、manifest 哈希（golden/prompt/schema/
  stability）+ gate version + code commit、run_validity 守卫。

### 8.2 Sprint 1C — MiMo Formal Run v3（中断，无持久化）

- **RUN_STATUS = `ABORTED_NO_PERSISTENCE`**（登记，不代表 PASS / FAILED / QUALIFIED /
  CONDITIONAL 任何 Qualification 结论）
- 事实：
  - MiMo smoke **PASS**（上一轮已验证）
  - `JC-A1` run1 **SUCCESS**
  - **0/30** formal case-runs 被持久化
  - v3 artifact directory **不存在**（`artifacts/qualification/judge/2026-08-16-s1c-judge-v3/`）
  - 后台进程已终止
- 说明：本轮**不构成有效 Formal Qualification**。根因是当时 harness 无
  checkpoint / resume 能力，进程终止后已完成进度全部丢失。
- **历史结论不变**：MiMo Qualification V2 = `FAILED`（历史记录，见 §1）；本次
  `ABORTED_NO_PERSISTENCE` 不改变该历史结论。
- 处理：harness v2（`judge-harness-v2`）加入 checkpoint / resume 后，以新 Formal Run
  （`2026-08-16-s1c-judge-v4`）重新执行，不得复用 v3。

## 9. 纪律

- `API_AVAILABLE ≠ QUALIFIED`；正式考试只用 `QUALIFIED`（或受限 `CONDITIONAL`）模型。
- 评估门槛与流程见 `docs/qualification/MODEL_QUALIFICATION.md` 与
  `docs/qualification/SPEECH_QUALIFICATION.md`。
