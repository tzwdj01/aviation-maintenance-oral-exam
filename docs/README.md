# Documentation Index（文档索引）

> Status: ACTIVE
> Owner: 项目治理负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）

本索引是进入文档体系的导航页。阅读顺序建议：
`GOAL.md` → `AGENTS.md` → 本文档 → 按域 Source of Truth → `docs/plans/CURRENT_SPRINT.md`。

## 根目录

| 文档 | 用途 | Source of Truth For | 何时必须阅读 |
| --- | --- | --- | --- |
| [`GOAL.md`](../GOAL.md) | 产品 North Star 与项目边界 | 产品战略、核心闭环、AI 原则 | 每次任务开始 |
| [`AGENTS.md`](../AGENTS.md) | Agent 强制入口、文档路由、防偏离机制 | Agent 工作流程 | 每次任务开始 |
| [`README.md`](../README.md) | 项目导航、快速开始、当前状态 | 仓库导航 | 首次进入仓库 |

## 域 Source of Truth

| 文档 | 用途 | Source of Truth For | 何时必须阅读 |
| --- | --- | --- | --- |
| `ARCHITECTURE.md` | 系统架构、分层、Provider 边界、多阶段评分编排 | 架构与 Provider 抽象 | Provider / 架构改动 |
| `DATA_MODEL.md` | 数据模型、约束、索引、快照与保留 | 数据库实体与约束 | 数据库 / 实体改动 |
| `SCORING.md` | 评分机制、Evidence 规则、Critical Error、追问 | 评分与动态追问语义 | 评分 / CE / Evidence 改动 |
| `EXAM_STATE_MACHINE.md` | 考试与题目状态机（唯一规范） | 考试状态 | Exam workflow / states 改动 |
| `CONFIGURATION.md` | 环境变量与配置契约（唯一入口） | 配置字段与 Provider 环境变量 | 配置 / 部署改动 |
| `SECURITY.md` | 密钥管理、数据保护、审计脱敏 | 安全与合规边界 | 涉及 secret / 音频 / 考试资料 |
| `TESTING.md` | 测试分层、Golden Dataset、回归门槛 | 测试策略 | 任何代码改动前确认测试要求 |
| `DEPLOYMENT.md` | 环境划分与部署原则 | 部署拓扑 | 部署 / 环境改动 |
| `RELEASE.md` | 发布流程与回滚策略 | 发布治理 | 发版 |

## 产品与设计记录（ACTIVE，保持复用）

| 文档 | 用途 |
| --- | --- |
| `PRD.md` | 产品需求、角色、验收标准（产品需求源） |
| `api-design.md` | REST API v1 契约设计 |
| `frontend-design.md` | 前端页面与交互设计 |
| `multi-provider-design.md` | Sprint 1A 多 Provider 设计决策与开发检查 |
| `risks.md` | 技术风险与缓解措施 |

## Providers（Provider 能力与协议）

| 文档 | 用途 |
| --- | --- |
| `providers/README.md` | Provider 层索引与职责 |
| `providers/mimo-speech.md` | MiMo ASR/TTS 协议、配置与责任 |
| `providers/mimo-llm.md` | MiMo LLM 评估适配器（仅诊断，未合格） |
| `providers/deepseek.md` | DeepSeek 评估适配器协议 |
| `providers/openai.md` | OpenAI 评估适配器协议 |

## Qualification（模型资格认证）

| 文档 | 用途 |
| --- | --- |
| `qualification/MODEL_QUALIFICATION.md` | 多 LLM 资格认证制度、指标与门槛 |
| `qualification/SPEECH_QUALIFICATION.md` | 语音能力资格认证 |
| `qualification/qualification-history.md` | 历史 Qualification 结论记录 |

## ADR（架构决策记录）

| 文档 | 用途 |
| --- | --- |
| `adr/README.md` | ADR 流程与模板 |
| `adr/0001-*.md` … `0007-*.md` | 已接受的核心架构决策 |

## Plans（计划与治理）

| 文档 | 用途 |
| --- | --- |
| `plans/ROADMAP.md` | 长期路线图与 Gate |
| `plans/CURRENT_SPRINT.md` | 当前 Sprint 范围与完成定义 |
| `plans/BACKLOG.md` | 待办与后续 Sprint 候选 |
| `plans/TECH_DEBT.md` | 已识别技术债与架构偏差记录 |

## 已废弃 / 被合并文档

| 文档 | 状态 | 去向 |
| --- | --- | --- |
| `mimo-integration.md` | SUPERSEDED | 内容合并至 `providers/mimo-speech.md` 与 `providers/mimo-llm.md` |

> 规则：不得为满足文件名要求制造两个 Source of Truth。若发现等价文档，优先复用并统一命名/链接。
