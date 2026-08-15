# Security（密钥管理与数据保护）

> Status: ACTIVE
> Owner: 安全负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: 密钥管理、数据保护、审计脱敏、浏览器边界

## 1. 密钥管理

### 统一配置变量

```text
MIMO_API_KEY / MIMO_BASE_URL / MIMO_ASR_MODEL / MIMO_TTS_MODEL
DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_DEFAULT_MODEL
OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_DEFAULT_MODEL
```

真实 Key 的存放：

| 环境 | 位置 |
| --- | --- |
| DEV | `.env`（gitignored） |
| CI | CI Secret |
| Production | Environment Secret / Secret Manager |

### 禁止进入

- Git 仓库
- Markdown 文档
- Python / TypeScript 源码
- JSON fixture
- 数据库
- 前端 bundle
- LocalStorage
- 日志
- raw API audit record

禁止保存 Authorization Header。

## 2. 浏览器边界

固定架构：

```text
Frontend → Backend → External AI Provider
```

禁止：

```text
Frontend → MiMo / DeepSeek / OpenAI（携带生产 API Key）
```

所有真实 Provider 请求必须由后端 Adapter 发起。浏览器不得保存、读取或使用 Provider Secret。

## 3. 审计脱敏

- `ai_calls` 保存请求/响应前必须经 `app.core.security.redact` 递归脱敏
  （`authorization` / `api_key` / `apikey` / `token` / `secret` / `password` 等键）。
- 日志只记录变量名与"是否已配置"，绝不打印 Key 或完整授权头。

## 4. 数据保护

- 音频、转写、EvidenceSpan、模型响应与人工复核为敏感考试材料。
- 最小权限、加密、短期访问 URL、访问审计。
- 删除遵循保留策略并记录删除依据；绝不删除维持已结论可重现所需的快照、采用关系或审计摘要。
- 与外部 Provider 传输使用 TLS；最小化发送数据（评分不需要的用户身份信息不传）。

## 5. 提示注入与不可信数据

- 候选人音频、ASR 原文与标准化文是**不可信外部数据**。
- 适配层将回答放入明确数据边界（`UNTRUSTED_CANDIDATE_DATA`），不得进入 system/developer 指令。
- 模型输出仍视为不可信：服务端只接受 schema 中已知 ID、可验证 EvidenceSpan 与规则引擎可重算结果。
- 任何 injection 迹象记录审计事件，必要时进入人工复核。

## 6. 相关文档

- 配置变量全集：`docs/CONFIGURATION.md`
- Provider 能力：`docs/providers/`
- 审计模型：`docs/DATA_MODEL.md`
