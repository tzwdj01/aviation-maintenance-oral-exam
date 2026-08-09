# REST API 设计

## 1. 约定

- 根路径：`/api/v1`；JSON 使用 `snake_case`；音频上传使用 `multipart/form-data`。
- 所有变更接口要求认证、RBAC 和 `Idempotency-Key`。错误响应统一为 `{code, message, request_id, details}`。
- 考生接口只返回允许公开的信息；Prompt、原始模型响应和规则快照仅在授权复核/审计接口提供。
- `202 Accepted` 表示 ASR、TTS 或分析正在处理，客户端轮询资源 GET 接口，而不是重复 POST。

## 2. 认证、人员与基础字典

| 方法与路径 | 角色 | 用途 |
| --- | --- | --- |
| `POST /auth/login`、`POST /auth/logout`、`GET /me` | 全部 | 会话与当前权限 |
| `GET/POST/PATCH /candidates` | 管理员/考评员 | 考生档案管理 |
| `GET /aircraft-types`、`GET /authorization-types` | 已认证 | 创建考试时选择条件 |
| `GET/POST/PATCH /admin/vocabularies` | 题库管理员 | 词典身份管理 |
| `GET/POST /admin/vocabularies/{id}/versions` | 题库管理员 | 创建/查看词典不可变版本 |
| `GET/POST/PATCH /admin/vocabulary-versions/{id}/terms` | 题库管理员 | 草稿版本的术语及变体管理 |
| `POST /admin/vocabulary-versions/{id}/publish` | 题库管理员 | 发布词典版本，不影响历史标准化结果 |

## 3. 题库、版本与评分标准

| 方法与路径 | 用途 |
| --- | --- |
| `GET/POST /admin/questions` | 检索/创建题目身份与元数据 |
| `GET/PATCH /admin/questions/{id}` | 读取/修改未发布题目元数据 |
| `GET/POST /admin/questions/{id}/versions` | 查看版本、基于草稿创建新版本 |
| `GET/PATCH /admin/question-versions/{id}` | 编辑草稿题干、普通评分点（含 evaluation mode）、关键错误、来源和追问主题 |
| `POST /admin/question-versions/{id}/validate` | 校验权重、规则 ID、引用和发布条件 |
| `POST /admin/question-versions/{id}/publish` | 发布不可变版本 |
| `POST /admin/question-versions/{id}/retire` | 停用版本，不影响历史考试 |

## 4. 考试与语音流程

| 方法与路径 | 用途 | 响应重点 |
| --- | --- | --- |
| `GET/POST /exam-plans` | 考试计划身份管理 | 非版本化元数据 |
| `GET/POST /exam-plans/{id}/versions` | 考试计划版本/蓝图管理 | section、题池、选择规则、通过/CE 规则 |
| `POST /exam-plan-versions/{id}/publish` | 发布可用于组卷的计划版本 | 发布后不可变 |
| `POST /exam-plan-versions/{id}/attempts` | 随机组卷并开始考试 | `attempt_id`、`exam_plan_version_id`、`plan_snapshot`、当前状态 |
| `GET /attempts/{id}` | 恢复/轮询考试 | 服务端状态、当前题、允许动作 |
| `POST /attempts/{id}/resume` | 恢复非 `ABANDONED` 的中断考试 | 当前步骤与安全恢复动作；`ABANDONED` 必须新建 Attempt |
| `POST /attempts/{id}/items/{item_id}/present` | 呈现题目或追问 | 题干、TTS 状态/受控 URL |
| `POST /attempts/{id}/items/{item_id}/answers` | 上传主答/追问/重录音频 | `answer_id`、`ASR_PROCESSING` 状态 |
| `GET /answers/{id}` | 查询 ASR/分析状态 | 所有 transcript、采用关系、任务及下一动作 |
| `POST /answers/{id}/retry-asr` | 重新转写同一音频 | 新转写任务 ID |
| `POST /answers/{id}/transcripts/{transcript_id}/adopt` | 采用某一 ASR 及其标准化结果 | 记录 actor、词典版本与新的状态版本 |
| `POST /attempts/{id}/items/{item_id}/advance` | 确认进入下一题 | 仅题目 `finalized` 时可用 |
| `GET /attempts/{id}/items/{item_id}/final-assessment` | 获取整题最终评价 | 初答/最终掌握度、依赖度、缺失点与复核状态 |
| `POST /attempts/{id}/complete` | 完成考试并生成报告 | 结果 ID 或 `202` |

## 5. 结果、复核与审计

| 方法与路径 | 角色 | 用途 |
| --- | --- | --- |
| `GET /results/{id}` | 考生/授权人员 | 总分、能力维度、弱项、复核状态 |
| `GET /results/{id}/report` | 考生/授权人员 | HTML 报告；PDF 为后续版本 |
| `GET /review/attempts` | 考评员 | 待复核队列及原因 |
| `GET /review/attempts/{id}` | 考评员 | 完整审计包：音频、ASR 原文/标准化文、规则快照、所有 Pass 原始输出 |
| `POST /review/attempts/{id}/decisions` | 考评员 | 追加 ReviewDecision 与按对象 ReviewDecisionItem 的人工结论 |
| `GET /audit/ai-invocations` | 管理员/审计员 | 按模型、Pass、Prompt、状态检索调用审计 |
| `GET /audit/ai-invocations/{id}` | 管理员/审计员 | 单次原始请求摘要、结构化响应和错误详情 |

## 6. 关键响应契约

`GET /attempts/{id}` 应包含 `state`（只取 `ExamAttemptState`）、`state_version`、`current_item`（含 `AttemptItemState` 与版本）、`allowed_actions`、`last_error` 和 `resume_hint`。例如不应让前端通过猜测状态决定可否上传。

人工复核提交体必须区分 AI 与人工，例如：`{ "rationale": "...", "items": [{"subject_type": "critical_error_rule", "subject_id": "CE001", "original_value": "TRIGGERED", "human_value": "OVERRIDDEN_BY_HUMAN", "rationale": "..."}] }`。后端创建追加式 `ReviewDecision`/`ReviewDecisionItem`，指定当前决定，永不更新 `ai_calls`、分析、分数快照或旧决定。
