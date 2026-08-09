# 数据模型设计

> Sprint 1A 实施说明：模型使用 UUID、UTC 时间戳和 SQLAlchemy 可移植 JSON/UUID 类型；运行中的
> Attempt 存储计划、题目版本、Rubric、Prompt bundle 与 LLMProfile 快照。Provider 名称使用可验证
> 字符串而非封闭数据库 enum，以便未来增加厂商，同时业务层对已知状态严格校验。

## 1. 设计约定

- 主键使用 UUID；SQLite 使用兼容存储，PostgreSQL 使用原生 UUID/JSONB。
- 所有业务表具有 `created_at`、`updated_at`；发布、审计和复核记录额外保存 actor。
- 发布后的版本及考试快照不可更新；订正只能创建新版本或追加决定。
- 分数使用整数/`NUMERIC`，不使用浮点。所有正式分数必须能以快照、已采用转写、最终点状态和权重重新计算。

## 2. 版本化题库、词典与考试蓝图

| 实体 | 关键字段 | 说明 |
| --- | --- | --- |
| `questions` | `id`, `code`, `title`, `question_type`, `aircraft_type_id`, `authorization_type_id`, `category`, `difficulty`, `status` | 稳定题目身份与检索元数据 |
| `question_versions` | `id`, `question_id`, `version_no`, `question_text`, `status`, `published_at` | 不可变题干版本 |
| `scoring_rubrics` | `id`, `question_version_id`, `max_score`, `pass_score`, `critical_error_policy`, `schema_version` | 每个题干版本的一份规则标准 |
| `rubric_points` | `id`, `rubric_id`, `point_code`, `category`, `evaluation_mode`, `dimension`, `weight`, `partial_weight`, `required`, `text`, `display_order` | `category` 仅为 `must_have`/`important`；`evaluation_mode` 仅为 `COVERAGE`/`QUALITY_RISK`，每点只有一个 primary pass |
| `critical_error_rules` | `id`, `rubric_id`, `rule_code`, `description`, `severity`, `exam_effect` | 唯一正式 Critical Error 规则集 |
| `reference_sources` / `follow_up_topics` | 来源字段 / `topic_text` | 标准依据与人工批准的追问范围 |
| `vocabularies` | `id`, `code`, `name`, `scope` | 稳定词典身份，如通用、B737NG、A330、公司 |
| `vocabulary_versions` | `id`, `vocabulary_id`, `version_no`, `status`, `published_at` | 不可变词典版本 |
| `vocabulary_terms` | `id`, `vocabulary_version_id`, `canonical_term`, `variants`, `meaning`, `status` | 术语和变体只属于特定词典版本 |
| `exam_plans` | `id`, `code`, `name`, `status` | 稳定考试计划身份 |
| `exam_plan_versions` | `id`, `exam_plan_id`, `version_no`, `status`, `pass_score`, `critical_error_policy`, `published_at` | 不可变的考试规则版本 |
| `exam_blueprint_sections` | `id`, `exam_plan_version_id`, `sequence`, `aircraft_type_id`, `authorization_type_id`, `category`, `question_count`, `difficulty_min`, `difficulty_max`, `selection_mode`, `weight` | 一个蓝图分区；`selection_mode` 为 `REQUIRED`/`RANDOM` |
| `exam_question_pools` | `id`, `blueprint_section_id`, `question_id`, `question_version_id`, `pool_weight`, `required` | 题池可固定版本或引用稳定题目身份；实际选择时锁定版本 |
| `exam_selection_rules` | `id`, `blueprint_section_id`, `rule_type`, `rule_value` | 可表达类别、难度、题量、必选/随机及扩展选择规则 |

`ExamPlanVersion` + `ExamBlueprintSection` + `ExamQuestionPool/ExamSelectionRule` 是随机组卷 Blueprint。开始考试时，服务端在单一事务中选择已发布版本、生成题目顺序、写入 `plan_snapshot` 与每题快照；后续计划/题库修改不能改变历史考试。

## 3. 考试、回答、ASR 采用与证据

| 实体 | 关键字段 | 说明 |
| --- | --- | --- |
| `exam_attempts` | `id`, `exam_plan_version_id`, `candidate_id`, `aircraft_type_id`, `authorization_type_id`, `state`, `state_version`, `plan_snapshot`, `abandoned_reason`, `started_at`, `completed_at` | `state` 仅取 `ExamAttemptState`；完整计划快照用于重现 |
| `attempt_items` | `id`, `attempt_id`, `blueprint_section_id`, `sequence`, `question_snapshot`, `rubric_snapshot`, `state`, `state_version`, `follow_up_count`, `initial_score`, `final_mastery_score`, `critical_error_status` | `state` 仅取 `AttemptItemState`；Critical Error 非 Boolean |
| `follow_ups` | `id`, `attempt_item_id`, `follow_up_no`, `question_text`, `target_point_ids`, `triggered_by_analysis_id`, `status` | 上限 2，追问与触发依据绑定 |
| `media_assets` | `id`, `storage_key`, `mime_type`, `size_bytes`, `sha256`, `duration_ms` | 原始音频元数据，二进制不入库 |
| `answers` | `id`, `attempt_item_id`, `follow_up_id`, `answer_type`, `status`, `supersedes_answer_id`, `audio_asset_id`, `submitted_at` | `answer_type`：`MAIN`/`FOLLOW_UP`/`RE_RECORDING`；旧回答保留，当前采用回答显式确定 |
| `asr_transcripts` | `id`, `answer_id`, `raw_text`, `language`, `confidence`, `is_adopted`, `adopted_at`, `adopted_by`, `ai_call_id` | 一个 Answer 可有多个 ASR 结果；评分只允许一个已采用转写 |
| `asr_normalizations` | `id`, `transcript_id`, `normalized_text`, `vocabulary_version_id`, `applied_mappings`, `status`, `is_adopted` | 原文不覆盖；评分使用与已采用 transcript 关联的已采用标准化文 |
| `evidence_spans` | `id`, `answer_id`, `transcript_id`, `source_type`, `quote`, `start_char`, `end_char`, `start_ms`, `end_ms` | `source_type` 为 `RAW`/`NORMALIZED`；未来可填时间戳；quote 和字符区间必须服务端验证 |

## 4. AI 分析、分数与 Critical Error

| 实体 | 关键字段 | 说明 |
| --- | --- | --- |
| `knowledge_point_analyses` | `id`, `answer_id`, `attempt_item_id`, `point_id`, `analysis_pass`, `status`, `confidence`, `reason`, `ai_call_id` | `analysis_pass` 为 `COVERAGE`/`QUALITY_RISK`/`FINAL_ASSESSMENT`；Final 行保存整题会话链的 final point status |
| `analysis_evidence_spans` | `id`, `analysis_type`, `analysis_id`, `evidence_span_id` | 多态关联普通点、Critical Error 与 Final point 分析的可验证证据 |
| `critical_error_analyses` | `id`, `answer_id`, `attempt_item_id`, `critical_error_id`, `result`, `confidence`, `reason`, `additional_risk_observation`, `judge_no`, `ai_call_id` | `result`：`NOT_TRIGGERED`/`TRIGGERED`/`UNCERTAIN`；未来双 Judge 用 `judge_no` |
| `score_evaluations` | `id`, `attempt_item_id`, `scope`, `calculation_version`, `input_snapshot`, `score`, `dimension_scores`, `critical_error_status` | 纯服务端规则引擎结果；`scope` 为 `INITIAL`/`FINAL` |
| `question_final_assessments` | `id`, `attempt_item_id`, `prompt_dependency`, `assessment`, `examiner_note`, `critical_error_status`, `ai_call_id` | final LLM 的非分数汇总与 final point analysis 关联；分数由 `score_evaluations` 给出 |
| `exam_final_results` | `id`, `attempt_id`, `total_score`, `initial_response_score`, `final_mastery_score`, `critical_error_status`, `review_status`, `dimension_scores`, `weak_point_summary` | 考试级服务端汇总，保留 AI 建议与人工最终结果关系 |

`critical_error_status` 在 `attempt_items`、`question_final_assessments`、`exam_final_results` 统一只允许：`NOT_TRIGGERED`、`TRIGGERED`、`UNCERTAIN`、`CONFLICTED`、`OVERRIDDEN_BY_HUMAN`。一旦任一有效回答的分析结果为 `TRIGGERED`，规则引擎不得因后续追问降级；仅当前有效人工决定可产生 `OVERRIDDEN_BY_HUMAN`。

## 5. 任务、幂等、Prompt 与人工复核

| 实体 | 关键字段 | 说明 |
| --- | --- | --- |
| `prompt_versions` | `id`, `code`, `analysis_pass`, `content_hash`, `template_snapshot`, `status`, `approved_by`, `published_at` | 每个 Pass 的不可变 Prompt 快照 |
| `ai_calls` | `id`, `attempt_item_id`, `answer_id`, `provider`, `call_type`, `model`, `input_summary`, `request_payload`, `response_payload`, `prompt_version_id`, `requested_at`, `responded_at`, `provider_request_id`, `status`, `retry_count`, `latency_ms`, `error_code` | 原始结构化响应和脱敏请求审计；不存密钥 |
| `task_jobs` | `id`, `job_type`, `status`, `business_key`, `attempt_id`, `attempt_item_id`, `answer_id`, `ai_call_id`, `payload_snapshot`, `retry_count`, `run_after`, `locked_at`, `completed_at`, `last_error` | `job_type`：`ASR`/`TTS`/`COVERAGE`/`CRITICAL_ERROR`/`QUALITY_RISK`/`FOLLOW_UP`/`FINAL_ASSESSMENT`；状态：`PENDING`/`RUNNING`/`SUCCEEDED`/`FAILED`/`RETRY_WAIT` |
| `idempotency_records` | `id`, `key`, `actor_id`, `request_hash`, `resource_type`, `resource_id`, `response_snapshot`, `status`, `expires_at` | 保存首次命令结果，抵御重放 |
| `review_decisions` | `id`, `attempt_id`, `reviewer_id`, `status`, `rationale`, `is_current`, `supersedes_decision_id`, `created_at` | append-only 复核批次；仅一个当前决定 |
| `review_decision_items` | `id`, `review_decision_id`, `attempt_item_id`, `subject_type`, `subject_id`, `original_value`, `human_value`, `rationale` | 分别处理题分、总分、Critical Error 规则、ASR 采用、uncertain/conflict；记录原值和人工结论 |
| `audit_events` | `id`, `entity_type`, `entity_id`, `action`, `actor_id`, `before_data`, `after_data`, `occurred_at`, `request_id` | 所有状态、发布、采用、重试和复核事件 |

## 6. 数据库约束与索引

- 发布版本唯一：`question_versions(question_id, version_no)`、`exam_plan_versions(exam_plan_id, version_no)`、`vocabulary_versions(vocabulary_id, version_no)`。
- `rubric_points(rubric_id, point_code)` 唯一；`category ∈ {must_have, important}`、`evaluation_mode ∈ {COVERAGE, QUALITY_RISK}`；一个普通点只能有一个 primary evaluation pass。
- 每个 `answers` 只能是 `MAIN` 或关联一个 `follow_up_id`；`supersedes_answer_id` 不得跨 `attempt_item`；历史行不可删除。
- 每个 `answer_id` 最多一个 `asr_transcripts.is_adopted=true`；每个已采用 transcript 最多一个已采用 normalization。评分任务必须引用已采用 normalization。
- `evidence_spans` 由服务端验证 `quote == substring(transcript, start_char, end_char)`，且 source type 与文本一致；无有效 span 的正式 `covered`、`partial`、`TRIGGERED` 与 final point status 不得入库。
- `follow_ups(attempt_item_id, follow_up_no)` 唯一且 `follow_up_no ∈ {1,2}`；创建时锁定 AttemptItem 并检查计数。
- `task_jobs(business_key)` 唯一；`business_key` 至少包含业务对象、Pass、已采用转写/会话版本与重试语义。
- `idempotency_records(actor_id, key)` 唯一；相同 key 但 request hash 不同必须拒绝。`review_decisions` 对同一范围仅允许一个 `is_current=true`。
- `state_version` 作为乐观锁条件；按 `(state, updated_at)`、`(status, run_after)`、`(attempt_item_id, call_type)`、`(attempt_id, sequence)` 建索引。

## 7. 数据保留与安全

音频、转写、EvidenceSpan、模型响应和人工复核为敏感考试材料，使用最小权限、加密、短期访问 URL 和访问审计。删除遵循保留策略并记录删除依据；绝不删除维持已结论可重现所需的快照、采用关系或审计摘要。
