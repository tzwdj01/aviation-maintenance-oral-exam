# OpenAI Evaluation Provider

> Status: ACTIVE
> Owner: AI/Provider 架构负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: OpenAI 评估适配器的协议与资格边界

## 1. 定位

`OpenAIEvaluationProvider` 是 `EvaluationProvider` 的实现之一，使用 Responses API 的
`text.format: json_schema`（strict）进行结构化评分分析，并在接收后由后端独立校验。

## 2. 资格状态

当前种子 Profile：`OPENAI / gpt-5`，`qualification_status = UNTESTED`。

**必须经过独立 Qualification（`docs/qualification/MODEL_QUALIFICATION.md`）后方可被治理流程标为
`QUALIFIED` 并用于正式考试。**

## 3. 协议

- 端点：`POST https://api.openai.com/v1/responses`
- 认证：`Authorization: Bearer <OPENAI_API_KEY>`（仅服务端环境）
- 请求：`instructions`（system）+ `input`（`UNTRUSTED_CANDIDATE_DATA` 数据边界）+
  `text.format={"type":"json_schema","name":<task_type>,"strict":true,"schema":<pydantic json schema>}`
- 输出：`output_text`（或 `output[].content[].text`）；后端仍必须用 Pydantic 严格 schema 校验。

## 4. 配置

| 环境变量 | 说明 | 默认 |
| --- | --- | --- |
| `OPENAI_API_KEY` | OpenAI API Key（Secret） | （环境注入） |
| `OPENAI_BASE_URL` | Base URL | `https://api.openai.com/v1` |
| `OPENAI_DEFAULT_MODEL` | 默认模型 | `gpt-5` |

> 兼容性说明：Sprint 1A 代码读取 legacy 名 `OPENAI_API_BASE_URL` / `OPENAI_MODEL`；
> Phase 0 已为规范名增加别名支持。

## 5. 责任与限制

- 结构化输出是传输保证，不是业务保证；服务端 schema/ID/Evidence 校验不可省略。
- 禁止 Silent Failover；模型名称必须配置化。
