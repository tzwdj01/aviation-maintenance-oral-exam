# DeepSeek Evaluation Provider

> Status: ACTIVE
> Owner: AI/Provider 架构负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: DeepSeek 评估适配器的协议与资格边界

## 1. 定位

`DeepSeekEvaluationProvider` 是 `EvaluationProvider` 的实现之一，用于结构化评分分析
（Coverage / Critical Error / Quality-Risk / Follow-up / Final Assessment）。

## 2. 资格状态

当前种子 Profile：`DEEPSEEK / deepseek-v4-pro`，`qualification_status = UNTESTED`。

**必须经过独立 Qualification（`docs/qualification/MODEL_QUALIFICATION.md`）后方可被治理流程标为
`QUALIFIED` 并用于正式考试。** 开发/训练模式可按规则使用 `CONDITIONAL` 或 `UNTESTED`，但必须明显标记。

## 3. 协议

- 端点：`POST https://api.deepseek.com/chat/completions`（OpenAI 兼容）
- 认证：`Authorization: Bearer <DEEPSEEK_API_KEY>`（仅服务端环境）
- 请求：`messages`（system prompt + `UNTRUSTED_CANDIDATE_DATA` 数据边界）+
  `response_format={"type":"json_object"}` + `temperature=0` + `stream=false`
- 输出：JSON mode 仅为传输辅助；后端用 Pydantic 严格 schema 校验
  （`app.ai.schemas.*`，`extra="forbid"`），失败按 `ProviderFailure` 处理。

## 4. 配置

| 环境变量 | 说明 | 默认 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | DeepSeek API Key（Secret） | （环境注入） |
| `DEEPSEEK_BASE_URL` | Base URL | `https://api.deepseek.com` |
| `DEEPSEEK_DEFAULT_MODEL` | 默认模型 | `deepseek-v4-pro` |

> 兼容性说明：Sprint 1A 代码读取 legacy 名 `DEEPSEEK_API_BASE_URL` / `DEEPSEEK_MODEL`；
> Phase 0 已为规范名增加别名支持。

## 5. 责任与限制

- 适配器只负责传输与解析；不决定业务状态、不计算分数。
- 禁止 Silent Failover：DeepSeek 失败不得悄悄切换 OpenAI/MiMo；进入 `TaskJob FAILED` 或
  `AttemptItem NEEDS_ATTENTION`。
- 模型名称不得硬编码到业务逻辑，必须通过配置读取。
