# Xiaomi MiMo Speech Provider（ASR / TTS）

> Status: ACTIVE
> Owner: 语音集成负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: MiMo ASR/TTS 的协议、配置、Adapter 责任、Retry 与 Error mapping

## 1. 定位

MiMo Speech 是当前项目的**核心语音 Provider**，由 `SpeechProvider` 统一接口承载：

- ASR：`mimo-v2.5-asr`（回答音频 → 转写文本）
- Standard TTS：`mimo-v2.5-tts`（题干/追问 → 播放音频）
- Optional Voice Design：`mimo-v2.5-tts-voicedesign`（独立 optional capability，资格状态单独管理，功能门控）
- Optional Voice Clone：`mimo-v2.5-tts-voiceclone`（同上，功能门控）

历史 Qualification 结论：`mimo-v2.5-asr` 曾为 `CONDITIONAL_PASS`，`mimo-v2.5-tts` 曾为 `PASS`
（详见 [`docs/qualification/qualification-history.md`](../qualification/qualification-history.md)）。

## 1.1 官方契约确认（2026-08-16，Sprint 1B）

真实 Provider 接入前已核对 `mimo.mi.com/docs` 当前官方契约（更新 2026-07-17）：

- 端点：`POST /v1/chat/completions`；认证 `Authorization: Bearer <key>` 或 `api-key: <key>`。
- **ASR `mimo-v2.5-asr`**：`messages[].content[].input_audio.data` 为 data URL，
  **仅支持 mp3/wav**；`asr_options.language`（`auto`/`zh`/`en`）；转写在
  `choices[0].message.content`。请求体不含 `stream` 字段。
- **TTS `mimo-v2.5-tts`**：`assistant` 消息 = 目标合成文本（必需）；`audio.format` 默认 `wav`；
  `audio.voice` 为内置音色（`mimo_default`、冰糖、茉莉、苏打、白桦、Mia、Chloe、Milo、Dean）；
  音频在 `choices[0].message.audio.data`（base64）。
- **Voice Clone `mimo-v2.5-tts-voiceclone`**：`audio.voice` 必需，为 mp3/wav 音频样本的 base64。
- **Voice Design `mimo-v2.5-tts-voicedesign`**：`user` 消息 = 音色设计文本（必需）；
  **`audio.voice` 不被支持**（Qualification V2 的 HTTP 400 即由此字段导致）；
  `audio.optimize_text_preview` 仅该模型支持。

实现以本契约为准；禁止猜测未被官方文档支持的字段。

## 2. 配置契约

真实 Key 只存在于服务端环境变量（`.env` / CI Secret / Secret Manager），**禁止写入仓库**。

| 环境变量 | 说明 | 示例/默认 |
| --- | --- | --- |
| `MIMO_API_KEY` | MiMo 服务端 API Key（Secret） | （由环境注入） |
| `MIMO_BASE_URL` | MiMo Token Plan Base URL | `https://token-plan-cn.xiaomimimo.com/v1` |
| `MIMO_ASR_MODEL` | ASR 模型名 | `mimo-v2.5-asr` |
| `MIMO_TTS_MODEL` | TTS 模型名 | `mimo-v2.5-tts` |
| `MIMO_VOICEDESIGN_ENABLED` | Voice Design 功能门控 | `false` |
| `MIMO_VOICECLONE_ENABLED` | Voice Clone 功能门控 | `false` |

> 兼容性说明：Sprint 1A 代码读取 `MIMO_API_BASE_URL`（legacy 名）。Phase 0 已为 `MIMO_BASE_URL`
> 增加别名支持，legacy 名仍可用；详见 `docs/CONFIGURATION.md` 与 `backend/app/core/config.py`。

## 3. Provider Adapter 责任

`MiMoASRProvider` / `MiMoTTSProvider`（继承 `MiMoSpeechBase`）负责：

- 认证头（`Authorization: Bearer <key>`，由环境注入）
- 请求序列化（OpenAI 兼容 `chat/completions` 负载）
- 超时（连接/请求分离，配置化）
- 响应标准化（`TranscriptResult` / `SynthesizedAudio`）
- 供应商错误映射（统一为 `ProviderFailure`）
- request ID 提取（`x-request-id` / `request-id`）

业务服务不得直接调用 MiMo SDK/HTTP；音频与密钥只流经后端。

## 4. Retry 与错误处理原则

- ASR/TTS 失败以持久化 `TaskJob` 记录；临时失败有限重试 + 退避，永久失败（鉴权、schema 不兼容）快速失败并告警。
- ASR 失败/空转写/低置信：保留原音频，允许重录或转人工；**绝不直接负面判定**。
- TTS 失败：降级为题干文本，允许重听/重试，不阻塞考试。
- 同一任务不得静默切换 Provider（禁止 Silent Failover）。

## 5. Error mapping 原则

| 供应商错误类型 | 映射 | 恢复 |
| --- | --- | --- |
| 超时 / 5xx / 网络错误 | `ProviderFailure`（临时） | 有限重试 → `RETRY_WAIT`/`FAILED` |
| 401/403（鉴权） | `ProviderFailure`（永久） | 快速失败，告警，不重试 |
| 400/schema 不兼容 | `ProviderFailure`（永久） | 快速失败，记录审计 |
| 空/畸形音频响应 | `ProviderFailure` | 重试或人工处理 |

## 6. 安全与审计

- 浏览器只向后端上传音频；后端生成受控短期音频访问 URL。
- `ai_calls` 保存请求/响应时必须脱敏认证头与密钥（`app.core.security.redact`）。
- 详细安全规则见 `docs/SECURITY.md`；环境变量全集见 `docs/CONFIGURATION.md`。
