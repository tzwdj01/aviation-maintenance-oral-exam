# Backlog（待办与后续 Sprint 候选）

> Status: ACTIVE
> Owner: 项目治理负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）

按优先度排列的候选工作项；进入 Sprint 前必须由用户批准并写入 `CURRENT_SPRINT.md`。

## P0 候选（核心闭环所需）

- [ ] 题库/规则/词典版本化服务与 API（草稿 → 校验 → 发布 → 只读；CE 规则、权重校验）
- [ ] 考试编排服务（考试计划/蓝图/随机组卷、Attempt 快照创建、item 流转、追问签发）
- [ ] 语音闭环服务（音频上传/受控存储、ASR 任务与转写采用、TTS 文本降级）
- [ ] 四 Pass 评分编排（任务分发、schema 校验、服务端重算、Final Assessment、NEEDS_ATTENTION 流转）
- [ ] 复核与结果（审计包、ReviewDecision/Item、能力报告）

## P1 候选

- [ ] 认证与 RBAC（考生/考评员/题库管理员/系统管理员）
- [ ] 生产 worker（持久化 TaskJob 拉取/恢复，替换开发 fake worker）
- [ ] 前端正式工作台（考生口试工作台、复核页、题库管理页）
- [ ] Golden Dataset 与 Prompt Regression 资产

## P2 候选（治理与交付）

- [ ] infra（docker-compose / 部署清单）
- [ ] CI（lint、测试、迁移检查、secret scan）
- [ ] MiMo Speech 真实接入验证（Sprint 1B）
- [ ] Multi-LLM Qualification 运行（Sprint 1C）

## 已识别治理待办

- [ ] 配置变量命名统一（`MIMO_BASE_URL` / `DEEPSEEK_BASE_URL` / `OPENAI_BASE_URL` /
  `DEEPSEEK_DEFAULT_MODEL` / `OPENAI_DEFAULT_MODEL`）— 已加别名支持，legacy 名在后续 Sprint 移除
- [ ] 将 `feature/sprint-1a-multi-provider-foundation` 合并到 `main` 的分支策略确认
