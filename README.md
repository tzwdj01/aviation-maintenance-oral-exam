# 航空维修放行人员 AI 口试系统

Aviation Maintenance Oral Exam — 面向维修放行人员训练、模拟口试与考评员辅助评估的
**可审计 AI 口试系统**。AI 作为评分辅助，不作为未经人工治理的最终授权决策者。

> 仓库治理入口：先读 [`GOAL.md`](GOAL.md) 与 [`AGENTS.md`](AGENTS.md)，
> 文档体系见 [`docs/README.md`](docs/README.md)。

## Current Status

仓库当前处于 **Phase 0 — Project Governance & Architecture Baseline 完成后、Sprint 1A 待 Gate 审查**状态。

- 完整设计文档位于 `docs/`（PRD、架构、数据模型、评分、状态机、Provider、Qualification、ADR、计划）。
- Sprint 1A「Model-Independent Core + Multi-Provider Foundation」的**后端基础已实现**于
  `feature/sprint-1a-multi-provider-foundation` 分支：SQLAlchemy/Alembic 审计模型、严格状态机、
  确定性 Decimal 评分、证据解析、版本化术语标准化、LLM Profile 管理 API、
  MiMo/DeepSeek/OpenAI/Fake Provider Adapter 契约，以及无需真实 Key 即可运行的垂直切片测试。
- 前端仅有开发期 LLM Profile 列表壳；正式考试工作台属于后续 Sprint。
- 当前 Sprint 定义见 [`docs/plans/CURRENT_SPRINT.md`](docs/plans/CURRENT_SPRINT.md)。

## Quick Start

```bash
# Backend（Python >= 3.12）
python -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip install pytest ruff
cd backend && PYTHONPATH=. ../.venv/bin/alembic upgrade head
PYTHONPATH=. ../.venv/bin/python scripts/seed_development.py
cd .. && .venv/bin/python -m pytest

# Frontend（React + TypeScript + Vite）
cd frontend && npm install && npm run build
```

本地开发无需真实 API Key：Fake Provider 可跑通垂直切片。真实 Provider 接入见
[`docs/providers/`](docs/providers/README.md) 与 [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)。

## Development Workflow

1. 阅读 `GOAL.md` 与 `AGENTS.md`（含文档路由与防偏离规则）。
2. 阅读 `docs/plans/CURRENT_SPRINT.md` 确认范围。
3. 遵循 Source of Truth 优先级：GOAL → Accepted ADR → 域文档 → CURRENT_SPRINT → 实现 → 假设。
4. 架构级变更必须先建 ADR（`docs/adr/README.md`），不得在普通 feature 中静默改变架构。
5. 任务结束执行 Architecture Drift Check（`AGENTS.md` §5）。

## Documentation Index

| 文档 | 内容 |
| --- | --- |
| [`GOAL.md`](GOAL.md) | 产品 North Star 与不可突破的 AI 原则 |
| [`AGENTS.md`](AGENTS.md) | Agent 强制入口、文档路由、防偏离机制 |
| [`docs/README.md`](docs/README.md) | 完整文档索引 |
| [`docs/PRD.md`](docs/PRD.md) | 产品需求与验收标准 |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 系统架构与 Provider 边界 |
| [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) | 数据模型与约束 |
| [`docs/SCORING.md`](docs/SCORING.md) | 评分、Evidence、Critical Error、追问 |
| [`docs/EXAM_STATE_MACHINE.md`](docs/EXAM_STATE_MACHINE.md) | 考试状态机（唯一规范） |
| [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) | 环境变量配置契约 |
| [`docs/SECURITY.md`](docs/SECURITY.md) | 密钥管理与数据保护 |
| [`docs/adr/`](docs/adr/README.md) | 架构决策记录 |
| [`docs/plans/`](docs/plans/ROADMAP.md) | 路线图、当前 Sprint、Backlog、技术债 |

## Security Notice

- **真实 API Key 永远不得写入本仓库**（Git、Markdown、代码、JSON fixture、前端 bundle、
  LocalStorage、日志、审计原文均禁止）。
- 开发用 `.env`（gitignored），CI 用 CI Secret，生产用 Secret Manager。
- 浏览器只与后端通信；所有真实 Provider 请求由后端 Adapter 发起（`Frontend → Backend → Provider`）。
- 详细规则见 [`docs/SECURITY.md`](docs/SECURITY.md) 与 [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)。
