# Speech Production（语音生产管线 — Sprint 1B）

> Status: ACTIVE
> Owner: 语音集成负责人
> Last Reviewed: 2026-08-16（Sprint 1B Implementation）
> Source of Truth For: ASR/TTS 生产管线、Audio Artifact、TaskJob 编排、降级与重试

## 1. 目标管线

```text
TTS Question → SynthesizedAudio → MediaAsset（受控存储）→ 播放 URL

Candidate audio → AudioReference 校验 → 持久化 MediaAsset
  → TaskJob(ASR) → MiMoASRProvider → Raw Transcript（永不覆盖）
  → Aviation Normalizer（版本化词典 + 内置分层）→ Normalization Record
  → 显式单一采用（adopted transcript candidate）→ 供评分
```

业务层只与 `SpeechProvider` 协议交互（`transcribe` / `synthesize`）；MiMo 请求体与
SDK 细节只存在于 `backend/app/ai/providers/speech/`（ADR-0004）。禁止 Silent Failover
（ADR-0005）：失败进入 `TaskJob RETRY_SCHEDULED / FAILED`，绝不静默切换 Provider。

## 2. Audio Artifact（`backend/app/audio/`）

- `AudioPurpose`：`QUESTION_TTS` / `CANDIDATE_ANSWER` / `FOLLOW_UP_TTS` / `VOICE_REFERENCE`。
- `MediaAsset`（`media_assets` 表）：`storage_key`、`purpose`、`mime_type`、`codec`、
  `sample_rate`、`channels`、`duration_ms`、`size_bytes`、`sha256`、`retention` 及
  可选的 `attempt_id` / `attempt_item_id` / `answer_id`。**音频二进制不入业务表**。
- `StorageAdapter` 抽象：开发用 `LocalStorageAdapter`（`MEDIA_STORAGE_DIR`）；
  生产存储必须走该抽象，不把本地绝对路径写成生产设计。
- 受控访问：`sign_media_url` 生成 HMAC 签名的短期 URL，`GET /api/v1/media/{key}` 校验
  签名与有效期后返回音频（`MEDIA_URL_SECRET` 生产必须配置）。

## 3. 音频校验（发送 Provider 之前）

`validate_audio` 校验：非空、MIME 白名单（`MEDIA_ALLOWED_MIME_TYPES`）、最大大小
（`MEDIA_MAX_SIZE_BYTES`）、最大时长（`MEDIA_MAX_DURATION_SECONDS`）、WAV/MP3 头可读。
损坏文件返回 `AudioValidationError`，**绝不调用 Provider**；需要转码时只能通过专门
adapter/service，不散落 subprocess 调用（本 Sprint 未引入 ffmpeg，WAV 元数据用 stdlib）。

## 4. ASR 生产流（`backend/app/services/speech_jobs.py`）

1. 上传校验并持久化 `MediaAsset` 后，`enqueue_asr_job` 创建 `TaskJob(job_type=ASR)`，
   `business_key` 唯一（去重/重放）。
2. `process_asr_job`：加载音频 → `SpeechProvider.transcribe` → **Raw ASR 永远保存**
   （`ASRTranscript.raw_text` / `raw_response`）。
3. 空转写：识别 `EMPTY_TRANSCRIPT`（等价内部错误），同 Provider 有限重试
   （`TEMPORARY` + 退避），仍空 → `TaskJob FAILED`（可重录/转人工；不自动判负）。
4. 成功后调用 `normalize`（最新已发布词典版本 + 版本化内置规则集，当前
   `builtin-v3`），保存
   `ASRNormalization` + `NormalizationMapping`（坐标/规则可追溯）；Normalizer **不得覆盖** Raw ASR。
5. `adopt_transcript` 显式单一采用（每个 Answer 至多一个 adopted；重新录音保留历史行，
   `supersedes` 关系）。

### 4.1 内置规则集版本（ruleset versioning）

- `ASRNormalization.normalizer_ruleset_version` 与 `vocabulary_version_id` 独立记录。
- `builtin-v1`：Sprint 1A 基础层（B七三七NG/M P D/维修放心）。
- `builtin-v2`：TTS 合成语料驱动的拼写/连字符/同音短语规则 + 低置信候选告警。
- `builtin-v3`：S01 真人语料驱动的短语同音修正（失航/释行指令→适航指令、
  B-737-800→B737-800）与单字母混淆候选告警（MER/SIM/MTD/CF56-7B 等，仅 review）。
- 规则变更必须升版本；历史记录不可变（`docs/qualification/qualification-history.md`）。

### 4.2 TTS 发音改进（Sprint 1B remediation）

- 方案：合成前对题干中的英文缩写做确定性拼读展开（`spell_out_aviation`，
  MEL→“M E L”等），符合官方 TTS 契约（`assistant` 目标文本自由控制）。
- 实测（run `2026-08-16-s1b-s01-qual-v3`）：TTS→ASR 回环术语正确率 0.75 → 0.80；
  原提示词方案（发音指导）实测无增益且引入一次失败，已记录并弃用。

## 5. TTS 生产流与降级

1. `enqueue_tts_job` 创建 `TaskJob(job_type=TTS)`，payload 记录 `fallback_text`（题干文本）。
2. `process_tts_job`：合成 → 校验音频 → 存 `MediaAsset` → 成功。
3. TTS 失败/空音频：有限重试后 `TaskJob FAILED`；`tts_fallback_text(job)` 返回题干文本，
   展示层以**文本降级**继续，不阻塞考试。

## 6. 错误映射与重试（`docs/providers/mimo-speech.md` §5）

| 供应商错误 | ProviderFailure | 恢复 |
| --- | --- | --- |
| 超时 / 网络 / 5xx / 429 | `TEMPORARY` | 有限重试 + 指数退避 → `RETRY_SCHEDULED` → `FAILED` |
| 401 / 403（鉴权） | `PERMANENT` | 快速失败、告警、不重试 |
| 400 / 422（schema 不兼容） | `PERMANENT` | 快速失败，记录审计 |
| 空 / 畸形音频或转写 | `TEMPORARY`（`EMPTY_TRANSCRIPT`/`EMPTY_AUDIO`） | 重试或人工处理 |

重试上限与超时由 `AI_MAX_RETRIES` / `AI_CONNECT_TIMEOUT_SECONDS` / `AI_REQUEST_TIMEOUT_SECONDS`
配置；`run_after` 记录下次可执行时间。

## 7. 审计与可观测性

- 每次 Provider 调用写入 `AICall`（`requested_at` / `responded_at` / `status` /
  `request_id` / `input_summary` / `raw_response` / `error` / `retry_count` /
  **`latency_ms`**）；请求与响应持久化前经 `app.core.security.redact` 脱敏。
- `AuditEvent` 记录 `speech.asr.*` / `speech.tts.*` 成功、重试与失败，失败含
  `needs_attention` / `re_recording_supported` 标记。
- `raw_response` 保留完整供应商响应以支持复核（不含认证头与密钥）。

## 8. 本地验证

真实 Provider 调用为本地可选验证，不进 CI 默认流程：

```bash
cd backend
python -m scripts.smoke_speech   # 读取环境注入的 MIMO_* 配置；绝不打印 API Key
```

脚本执行 TTS 合成 → ASR 转写回环，输出模型、request_id、latency_ms、字节数与转写结果，
供 Speech Gate 评审。开发垂直切片使用 `FakeSpeechProvider`（无需网络/密钥）。
