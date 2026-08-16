# Configuration（环境变量与配置契约）

> Status: ACTIVE
> Owner: 后端/部署负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: 本项目使用的环境变量与配置字段（唯一规范入口）

Provider 文档描述**协议与能力**；本文件描述**本项目使用哪些环境变量**。
`.env.example` 必须与本文件一致；真实 Key 永远不写入仓库。

## 1. 变量全集

### Application / Database

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `APP_ENV` | 运行环境（development/test/staging/production） | `development` |
| `DATABASE_URL` | SQLAlchemy 连接串（开发 SQLite / 生产 PostgreSQL） | `sqlite:///./aviation_oral_exam.db` |
| `API_V1_PREFIX` | API 前缀 | `/api/v1` |
| `ENABLE_DEV_PROVIDER_TEST` | 是否启用开发 Provider 测试 | `false` |

### MiMo Speech（服务端专用）

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `MIMO_API_KEY` | MiMo API Key（Secret） | （环境注入） |
| `MIMO_BASE_URL` | MiMo Token Plan Base URL | `https://token-plan-cn.xiaomimimo.com/v1` |
| `MIMO_ASR_MODEL` | ASR 模型 | `mimo-v2.5-asr` |
| `MIMO_TTS_MODEL` | TTS 模型 | `mimo-v2.5-tts` |
| `MIMO_VOICEDESIGN_ENABLED` | Voice Design 功能门控 | `false` |
| `MIMO_VOICECLONE_ENABLED` | Voice Clone 功能门控 | `false` |
| `MIMO_ASR_LANGUAGE` | ASR 识别语言（官方契约 `auto`/`zh`/`en`） | `auto` |
| `MIMO_TTS_VOICE` | TTS 内置音色（`mimo_default` 等） | `mimo_default` |
| `MIMO_TTS_STYLE_PROMPT` | TTS 朗读风格/发音指导（官方契约 `user` 消息） | 清晰自然专业中文口试考官语气 |

### Media / Audio（Sprint 1B 新增）

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `MEDIA_STORAGE_DIR` | 本地开发音频存储目录（生产走 StorageAdapter 抽象） | `./media` |
| `MEDIA_MAX_SIZE_BYTES` | 单段音频最大字节数（服务端校验） | `20971520`（20 MB） |
| `MEDIA_ALLOWED_MIME_TYPES` | 允许的音频 MIME 列表 | `["audio/wav","audio/mpeg"]` |
| `MEDIA_MAX_DURATION_SECONDS` | 单段音频最大时长（秒） | `120` |
| `MEDIA_ACCESS_URL_TTL_SECONDS` | 受控音频访问 URL 有效期（秒） | `3600` |
| `MEDIA_URL_SECRET` | 受控访问 URL 签名密钥（Secret；开发缺省用进程内临时密钥） | （环境注入） |

### DeepSeek（评估 Provider）

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | DeepSeek API Key（Secret） | （环境注入） |
| `DEEPSEEK_BASE_URL` | Base URL | `https://api.deepseek.com` |
| `DEEPSEEK_DEFAULT_MODEL` | 默认模型 | `deepseek-v4-pro` |

### OpenAI（评估 Provider）

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `OPENAI_API_KEY` | OpenAI API Key（Secret） | （环境注入） |
| `OPENAI_BASE_URL` | Base URL | `https://api.openai.com/v1` |
| `OPENAI_DEFAULT_MODEL` | 默认模型 | `gpt-5` |

### HTTP 控制

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `AI_CONNECT_TIMEOUT_SECONDS` | 连接超时（秒） | `10` |
| `AI_REQUEST_TIMEOUT_SECONDS` | 请求超时（秒） | `60` |
| `AI_MAX_RETRIES` | 最大重试次数 | `2` |

## 2. 命名兼容说明（legacy alias）

Phase 0 前代码使用以下 legacy 变量名。`backend/app/core/config.py` 已通过 `AliasChoices`
支持规范名，**legacy 名仍可用**（向后兼容）：

| 规范名 | Legacy 名 |
| --- | --- |
| `MIMO_BASE_URL` | `MIMO_API_BASE_URL` |
| `DEEPSEEK_BASE_URL` | `DEEPSEEK_API_BASE_URL` |
| `OPENAI_BASE_URL` | `OPENAI_API_BASE_URL` |
| `DEEPSEEK_DEFAULT_MODEL` | `DEEPSEEK_MODEL` |
| `OPENAI_DEFAULT_MODEL` | `OPENAI_MODEL` |

legacy 名在后续 Sprint 经人工批准后移除（见 `docs/plans/TECH_DEBT.md` §1）。

## 3. 密钥存放位置

| 环境 | 存放位置 |
| --- | --- |
| DEV | `.env`（gitignored） |
| CI | CI Secret |
| Production | Environment Secret / Secret Manager |

禁止进入：Git、Markdown、Python/TypeScript 源码、JSON fixture、数据库、前端 bundle、
LocalStorage、日志、raw API audit record。禁止保存 Authorization Header。

## 4. 一致性要求

- `.env.example` 与本文档保持一致（变量名、非敏感默认值）。
- 测试应验证重要变量映射（`backend/tests/test_config.py`）。
- 模型名称必须配置化，不得硬编码到业务逻辑（默认值允许在配置中给出）。
