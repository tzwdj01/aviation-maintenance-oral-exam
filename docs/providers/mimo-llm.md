# Xiaomi MiMo LLM Provider（评估适配器）

> Status: ACTIVE
> Owner: AI/Provider 架构负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: MiMo LLM 评估适配器的协议与资格边界

## 1. 定位

MiMo LLM 通过 `EvaluationProvider` 适配器接入（`MiMoEvaluationProvider`，继承
`DeepSeekEvaluationProvider` 的 OpenAI 兼容 Chat Completions 协议 + JSON mode）。

## 2. 资格边界（重要）

根据 Qualification V2 Full 结果：`mimo-v2.5` 的 Coverage、Critical Error、追问与稳定性
**未达到正式 Judge 门槛**，其 LLM Profile 被登记为：

```text
qualification_status = FAILED
```

因此：

- **不得作为正式评分 Judge**；仅可用于诊断/开发。
- `API_AVAILABLE ≠ QUALIFIED`：模型能调用不等于可正式使用。
- 未来若重新评估，必须走 `docs/qualification/MODEL_QUALIFICATION.md` 的完整 Qualification 流程，
  通过后由治理流程将状态改为 `QUALIFIED`，并记录到 `docs/qualification/qualification-history.md`。

## 3. 协议

- 端点：OpenAI 兼容 `POST {MIMO_BASE_URL}/chat/completions`
- 认证：`Authorization: Bearer <MIMO_API_KEY>`（仅服务端环境）
- 请求：`messages` + `response_format={"type":"json_object"}` + `temperature=0` + `stream=false`
- 输出：JSON mode 仅为传输辅助；后端必须用 Pydantic 严格 schema 再次校验
  （`app.ai.schemas.*`，`extra="forbid"`），校验失败按 `ProviderFailure` 处理。

## 4. 配置

| 环境变量 | 说明 |
| --- | --- |
| `MIMO_API_KEY` | MiMo API Key（Secret） |
| `MIMO_BASE_URL` | `https://token-plan-cn.xiaomimimo.com/v1` |
| `MIMO_LLM_MODEL` | LLM 评估模型（当前种子为 `mimo-v2.5`） |

> 兼容性说明：Sprint 1A 代码读取 legacy 名 `MIMO_API_BASE_URL`；`MIMO_BASE_URL` 已作为别名支持。

## 5. 结构化输出契约

与 DeepSeek/OpenAI 共用同一套 Pass 契约（Coverage / Critical Error / Quality-Risk /
Follow-up / Final Assessment），见 `docs/multi-provider-design.md` §Structured outputs 与
`docs/SCORING.md` §4。MiMo 无豁免：所有正式结论仍必须通过服务端 schema/ID/Evidence 校验。
