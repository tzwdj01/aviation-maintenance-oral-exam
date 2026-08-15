# Model Qualification（多 LLM 资格认证制度）

> Status: ACTIVE
> Owner: AI 评估与质量负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: LLM 评估 Provider 的资格认证流程、指标与门槛

## 1. 核心原则

```text
API_AVAILABLE ≠ QUALIFIED
```

模型「能调用」不等于「可正式使用」。**正式考试只能使用经过 Qualification Gate 的模型**。
训练/开发模式可根据规则允许 `CONDITIONAL` 或 `UNTESTED`，但必须明显标记，且不得用于正式评判。

## 2. 资格状态机

| 状态 | 含义 | 可否正式使用 |
| --- | --- | --- |
| `UNTESTED` | 尚未评估 | 否 |
| `QUALIFYING` | 评估进行中 | 否 |
| `QUALIFIED` | 通过 Qualification Gate | 是 |
| `CONDITIONAL` | 有条件通过（受限场景） | 受限场景可 |
| `FAILED` | 未通过 | 否（可诊断/开发） |
| `RETIRED` | 已退役 | 否 |

## 3. 评估方法

所有候选模型使用**同一**：

- Golden Dataset（同一组样本与人工金标）
- Rubric（同一版本评分规则）
- Evidence 规则（同一引文/偏移解析规则）

用于横向比较 MiMo / DeepSeek / OpenAI。

## 4. 核心指标（至少）

| 指标 | 定义/说明 |
| --- | --- |
| Coverage Exact Agreement | Pass 1 点状态与金标一致率 |
| Major Disagreement | 显著偏离（covered↔missing 等）比例 |
| Evidence Validity | EvidenceSpan 可验证比例（VALID/AMBIGUOUS/INVALID） |
| CE Recall | Critical Error 检出召回率 |
| CE Precision | Critical Error 精确率 |
| Follow-up Accuracy | 追问决策与目标点选择准确率 |
| Answer Leakage | 是否泄露标准答案 |
| Prompt Injection Resistance | 对抗样本拒绝率 |
| Structured Output Validity | 输出通过 schema 校验比例 |
| Decision Stability | 相同输入多次运行结果稳定性 |
| Latency | 响应延迟（P50/P95） |
| Provider Failure Rate | 调用失败率 |

## 5. 门槛与纪律

- 不得因为某个模型成绩不好而修改 Golden Label 或阈值使其通过。
- 变更 Prompt / 模型 / 词典 / 评分算法 / Provider 后，必须重跑完整 Golden Dataset 并保存版本。
- 每个 Pass 输出回归指标：Coverage 一致率、Quality/Risk 一致率、CE 精确率/召回率、
  追问有效率、EvidenceSpan 有效率、JSON 有效率、人工改判率、adversarial 拒绝率。
- 零容忍项：未知 ID、无效 EvidenceSpan、正式分数不可重算、Injection 改变规则/分数/泄露答案、
  低置信度从复核变成自动失败。

## 6. 结果记录

评估结论记录到 `docs/qualification/qualification-history.md`，并在 `LLMProfile.qualification_status`
与 `qualification_summary` 中体现。评估产物（数据集、运行脚本、输出）作为版本化资产保留。
