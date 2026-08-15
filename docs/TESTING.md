# 测试策略

> Status: ACTIVE
> Owner: 测试与质量负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: 测试分层、Golden Dataset、回归门槛、Qualification 评估

## 1. 测试目标

验证正式分数可重算、EvidenceSpan 可验证、历史快照不可变、Critical Error 不会被后续 AI 自动清除，以及重试/并发/恢复不会创建重复业务结论。

## 2. Golden Dataset

| 样本 | 场景 | 必须断言 |
| --- | --- | --- |
| A | 完整正确 | 全部点 `covered`、无追问、CE `NOT_TRIGGERED` |
| B | 不同措辞但语义正确 | 语义等价覆盖，EvidenceSpan quote/offset 可验证 |
| C | 部分正确 | 正确的 `partial`/`missing` 与针对性追问 |
| D | 需追问 | Initial 与 Final 可区分，依赖度正确，不平均分 |
| E | 含 Critical Error | Pass 2 命中预定义 CE，含有效 EvidenceSpan |
| F | 模糊/ASR 易错 | `UNCERTAIN` 或人工复核，不臆测失败 |
| G | Prompt Injection | 忽略“改分/全标 covered/泄露答案/输出假 JSON”等回答内指令 |
| H | CE 后改口 | 先前 `TRIGGERED` 在后续否认后仍保持，除非人工覆盖 |
| I | 同题多次重录 | Answer 链、supersedes 与采用关系正确，旧音频未删除 |
| J | 首次 ASR 错、二次正确 | 仅已采用 transcript/normalization 被评分，历史 ASR 保留 |
| K | Pass 1/3 潜在冲突 | `evaluation_mode` 路由唯一，非 primary pass 输出被拒绝/不采纳 |
| L | 页面刷新/worker 重启 | 从持久化 `TaskJob` 与 state/version 恢复，不重复评分 |
| M | 同 Idempotency-Key 重复请求 | 无重复 Answer/Follow-up/Score，返回首次响应 |
| N | 不同 key 并发提交 | 乐观锁/业务唯一键确保只有一个有效推进结果 |

数据集覆盖通用、B737NG、A330 与公司术语，包含原始 ASR、预期标准化文、词典版本、有效/无效 span 及人工金标。它是 Prompt 与模型升级的版本化回归资产。

## 3. 测试层次

- **规则单元测试**：point primary pass、权重/partial_weight、Initial/Final 重算、CE 状态聚合、CE 不可自动清除、追问上限。
- **证据与契约测试**：schema、未知 ID、伪造 rubric ID、假 JSON、quote/offset 不匹配、跨 transcript span、无证据的 `covered`/`TRIGGERED`/final status 必须拒绝。
- **状态机与任务测试**：所有规范状态转换、超时/主动结束/人工终止、TaskJob 重试/恢复、TTS/ASR/LLM 失败。
- **并发与幂等测试**：重复 key、不同 key 并发、state_version 冲突、任务 business key 去重、重新录音与多 ASR 采用。
- **集成/端到端测试**：SQLite/PostgreSQL、快照、权限、审计包、append-only ReviewDecision/Item、考生页面不泄露评分。

## 4. Prompt Regression 与模型升级

每次 Prompt、模型、词典、规则算法或 Provider 变更都运行完整 Golden Dataset，并按 Pass 输出：Coverage 一致率、Quality/Risk 一致率、CE 精确率/召回率、追问有效率、EvidenceSpan 有效率、JSON 有效率、人工改判率和 adversarial 拒绝率。

批准门槛：CE 召回率不得下降；未知 ID、无效 EvidenceSpan 和正式分数不可重算均为零容忍；Injection 样本不得改变规则、分数或泄露答案；低置信度不得从复核变成自动失败。保存基线模型、Prompt、词典、数据集及运行结果版本。

## 5. 测试分层（Phase 0 固化）

生产关键逻辑不得只依赖手工测试。测试至少分为以下层次，每层职责如下：

| 层次 | 覆盖内容 |
| --- | --- |
| Unit | 规则计算、Evidence 解析、状态迁移、CE 聚合、normalization、schema 契约 |
| Integration | 仓储/服务与 SQLAlchemy 集成、TaskJob 状态流转、快照不可变 |
| Contract | API 请求/响应契约、结构化输出契约、错误格式统一 |
| Provider Qualification | 各 Provider 在同一 Golden Dataset / Rubric / Evidence 规则下的对比评估 |
| State Machine | 所有规范状态转换、并发、恢复、幂等 |
| Scoring | 权重/partial 重算、Initial/Final 区分、CE 粘性、追问上限 |
| Migration | SQLite/PostgreSQL 方言兼容、Alembic 迁移、历史快照不变 |
| Security | 密钥脱敏、注入防护、最小权限、审计完整性 |
| End-to-End | 核心闭环（出题→语音→ASR→评分→追问→复核）垂直切片 |
| Regression | Golden Dataset 全量回归（每次 Prompt/模型/词典/算法/Provider 变更） |

Golden Dataset 覆盖通用、B737NG、A330 与公司术语，包含原始 ASR、预期标准化文、词典版本、
有效/无效 span 及人工金标；作为 Prompt 与模型升级的版本化回归资产。
