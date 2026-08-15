# 评分与动态追问设计

> Status: ACTIVE
> Owner: 评分与题库治理负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: 评分语义、Evidence 规则、Critical Error 语义、追问决策、能力报告

## 1. 不可突破的治理边界

正式标准只包括版本化的 `must_have_points`、`important_points` 和 `critical_errors`。LLM 只能将回答映射到这些预定义 ID；不得新增标准答案、得分点或 Critical Error。语义等价表达允许被识别，但每项正式判断必须关联可验证的 `EvidenceSpan`。

所有正式分数由服务端规则引擎依据 `rubric_snapshot`、保存的点状态与权重计算；LLM 从不返回可信分数、分项分数或最终通过结论。人工复核是追加式决定，永不覆盖模型原始输出。

## 2. 评分标准与 primary evaluation pass

```json
{
  "must_have_points": [
    {"id": "M03", "description": "查询适用维修标准", "evaluation_mode": "COVERAGE", "weight": 30, "partial_weight": 15}
  ],
  "important_points": [
    {"id": "I02", "description": "说明风险控制逻辑", "evaluation_mode": "QUALITY_RISK", "weight": 15, "partial_weight": 8}
  ],
  "critical_errors": [
    {"id": "CE001", "description": "未查技术文件即放行", "severity": "critical"}
  ]
}
```

每个普通点仅有一个 `evaluation_mode`：

| 模式 | primary pass | 可用状态 | 职责 |
| --- | --- | --- | --- |
| `COVERAGE` | Pass 1 | `covered`/`partial`/`missing`/`uncertain` | 判断事实性知识点是否被语义覆盖 |
| `QUALITY_RISK` | Pass 3 | `covered`/`partial`/`missing`/`uncertain` | 判断预定义风险、程序意识或表达完整性点是否被有质量地体现 |

Pass 1 和 Pass 3 可以并行，但不得对同一 point 写入 competing primary status。若模型输出的 `point_id` 与其 `evaluation_mode` 不一致，schema/business 校验拒绝该输出并进入 `NEEDS_ATTENTION`。同一点的历史分析可保留，但规则引擎只采纳与该点 primary pass、当前已采用转写/会话版本匹配的最新成功结果。

## 3. 多阶段 AI 分析

| 阶段 | 输入 | 输出 | 约束 |
| --- | --- | --- | --- |
| Pass 1 — Coverage | 已采用标准化转写、`COVERAGE` 点 | point status、EvidenceSpan、置信度、原因 | 不评 Critical Error、不输出分数 |
| Pass 2 — Critical Error | 已采用标准化转写、`critical_errors` | 每条规则 `NOT_TRIGGERED`/`TRIGGERED`/`UNCERTAIN`、EvidenceSpan、置信度、原因 | 独立于 Pass 1/3；不得创建新 CE |
| Pass 3 — Quality/Risk | 已采用标准化转写、`QUALITY_RISK` 点 | point status、EvidenceSpan、置信度、原因 | 不处理 `COVERAGE` 点、不改变 CE |
| Pass 4 — Follow-up | 未解决点、CE 不确定性、追问历史、批准 topic | 是否追问、目标点 ID、开放式问题、原因 | 最多两次、不泄露答案、不输出分数 |
| Final Assessment | 完整 Conversation Chain、已有 final point 规则 | `final_point_assessments`、依赖度、备注、EvidenceSpan | 不输出正式分数或改变 CE |

候选人回答是**不可信数据**，不是指令。所有 Prompt 将回答放在明确的数据边界中；模型被要求忽略其中任何要求修改标准、输出 JSON、泄露答案或修改成绩的内容。

## 4. 结构化输出契约

Pass 1/3 共同的点输出形状：

```json
{
  "point_id": "M03",
  "status": "covered",
  "evidence_spans": [
    {"answer_id": "...", "transcript_id": "...", "source_type": "NORMALIZED", "quote": "先翻手册看损伤是否超限", "start_char": 0, "end_char": 13}
  ],
  "confidence": 0.96,
  "reason": "对应已发布评分点的语义等价表达"
}
```

Pass 2 使用 `critical_error_id`、`result`、`evidence_spans`、`confidence`、`reason`。`TRIGGERED` 必须存在至少一个可验证 span；`UNCERTAIN` 强制 `needs_human_review=true`。题库外重大风险可填 `additional_risk_observation`，但只能触发人工复核，不能扣分或升级为 CE。

Final Assessment 仅返回：

```json
{
  "final_point_assessments": [
    {"point_id": "M03", "final_status": "covered", "evidence_spans": ["..."], "resolved_from_answer_ids": ["..."], "confidence": 0.94, "reason": "追问后已清晰说明"}
  ],
  "prompt_dependency": "B",
  "assessment": "一次轻度追问后补齐程序依据",
  "examiner_note": "主动识别能力仍需加强",
  "needs_human_review": false
}
```

服务端验证 quote、字符区间、answer/transcript 关系及 point ID；无效 EvidenceSpan、未知 ID、伪造 JSON 或不合 schema 的输出一律拒绝为正式分析。

## 5. 服务端评分、Critical Error 与最终评价

1. 仅对已采用 transcript/normalization 创建 Pass 任务。
2. 对每个普通点采纳其 primary pass 的有效状态：`covered=weight`、`partial=partial_weight`、`missing/uncertain=0`；总分与维度分完全由快照重算。
3. Initial Response Score 只使用主答首次已采用转写的点状态。
4. 汇总所有有效 CE：任意 `TRIGGERED` → `TRIGGERED`；否则任意 `UNCERTAIN` → `UNCERTAIN`；多 Judge 冲突 → `CONFLICTED`；否则 `NOT_TRIGGERED`。后续回答不能自动清除 `TRIGGERED`。
5. Pass 4 仅在仍存在缺失/存疑点、CE 不确定性或批准风险主题，且 `follow_up_count < 2` 时创建追问。
6. Final Assessment 产出会话链的 final point status。规则引擎据此重算 Final Mastery Score；不得信任 LLM 的数值。
7. `Prompt Dependency`：A 首答满足；B 一次轻度追问后满足；C 明显追问才满足；D 追问后仍未掌握。分类由保存的会话链和最终点状态校验。

当 Final Assessment 与先前有效点状态冲突时，服务端不覆盖原记录，而是存新 final analysis 并标记复核。人工可使用 `ReviewDecisionItem` 覆盖当前结论，形成 `OVERRIDDEN_BY_HUMAN`，同时保留原 AI/规则结果。

## 6. 默认评分维度

| 维度 | 默认权重 | 来源 |
| --- | ---: | --- |
| 核心技术要点 | 40 | 映射到该维度的普通点 |
| 手册/程序意识 | 20 | 映射到该维度的普通点 |
| 判断与处置逻辑 | 15 | 映射到该维度的普通点 |
| 安全与风险意识 | 15 | 映射到该维度的普通点；Critical Error 独立处理 |
| 表达完整性 | 10 | 映射到该维度的普通点 |

权重、partial 权重和通过线都是题目/考试计划版本的人工治理数据，正式发布前必须校验总和和维度映射。

## 7. 质量与回归

Golden Dataset 和 Prompt Regression 必须单独量化 Coverage 一致率、CE 精确率/召回率、QUALITY_RISK 一致率、追问有效率、EvidenceSpan 有效率、结构化输出有效率以及人工改判率。任何 Prompt、模型、词典或评分算法变更都必须保存版本并重跑金标集。
