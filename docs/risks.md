# 技术风险与缓解措施

> Status: ACTIVE
> Owner: 项目治理负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: 技术风险登记与缓解措施

| 风险 | 影响 | V1 缓解与验收信号 |
| --- | --- | --- |
| ASR 误识别航空术语或口音 | 知识点/关键错误误判 | 版本化词典、原文与标准化文并存、金标音频、低置信度复核 |
| 语义理解幻觉 | 模型自行增加标准或错误匹配 | 规则 ID 白名单、candidate evidence、schema 校验、金标回归 |
| Critical Error 误报/漏报 | 安全和公平风险 | 独立 Pass、`uncertain` 状态、人工队列、未来双 Judge 数据预留 |
| 追问泄露标准答案 | 评分失真 | Pass 4 仅允许目标点 ID、开放式追问模板、人工抽检 |
| 追问后掩盖初答弱项 | 能力报告失真 | 分离 Initial Response / Final Mastery / Prompt Dependency，禁止平均分 |
| 模型/网络故障 | 考试中断或重复处理 | 持久化状态、幂等键、有限重试、TTS 文本降级、恢复接口 |
| 音频和考试资料泄露 | 隐私与合规风险 | 最小权限、短期 URL、加密/保留策略、审计访问 |
| SQLite/PostgreSQL 差异 | 上线迁移或并发故障 | 兼容类型、Alembic、PostgreSQL 集成测试 |
| 题库规则治理不足 | 再好的模型也无法可靠评分 | 版本发布、业务专家审核、来源与适用范围记录 |
| 前端状态与后端不一致 | 重复答案/错题推进 | 服务端状态机、轮询恢复、乐观锁/行锁、幂等接口 |
| 候选人回答 Prompt Injection | 修改评分、伪造 JSON/规则 ID、泄露答案 | 将回答作为不可信数据隔离；系统 Prompt 明确拒绝回答内指令；schema/ID/span 服务端校验；对抗金标回归 |
| Worker 重启或重复投递 | 重复 ASR/评分/追问 | 持久化 `TaskJob`、business key 唯一、状态锁与幂等记录 |
| 后续回答掩盖已触发 CE | 安全风险被错误清除 | 统一 CE 状态机，AI 不得降级 `TRIGGERED`，仅人工决定可覆盖 |

V1 不以 Token 成本为风险优化目标；资源充足时优先保留多 Pass 可靠性、审计完整性和复核能力。响应速度仍应监控，但不得以合并关键分析阶段换取速度。
