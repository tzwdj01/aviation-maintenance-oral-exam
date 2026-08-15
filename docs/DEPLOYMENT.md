# Deployment（部署与环境划分）

> Status: ACTIVE
> Owner: 部署/DevOps 负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）
> Source of Truth For: 部署拓扑与环境隔离

## 1. 环境划分

| 环境 | 用途 | 数据库 | 说明 |
| --- | --- | --- | --- |
| DEV | 本地开发 | SQLite | Fake Provider 垂直切片；无需真实 Key |
| TEST | 自动化测试 | SQLite/PostgreSQL | CI 运行 |
| STAGING | 预发布验证 | PostgreSQL | 真实 Provider 可选、受控 |
| PRODUCTION | 正式使用 | PostgreSQL | 仅 `QUALIFIED` 模型；Secret Manager |

**数据库、API Key、日志、Provider Credential 不得跨环境混用。**

## 2. 部署形态（目标）

- 后端：FastAPI（ASGI）+ 持久化 `TaskJob` worker（横向扩展或开发简化）。
- 数据库：SQLite（开发）/ PostgreSQL（生产），同一 SQLAlchemy 模型与 Alembic 迁移路径。
- 对象存储：音频等媒体（开发本地存储；生产受控对象存储 + 短期 URL）。
- 前端：静态构建产物（Vite build），仅与后端通信。

> Sprint 1A 无生产 worker/部署实现；本文件是部署原则，具体清单在后续 Sprint 落地。

## 3. 部署前置

- 环境变量按 `docs/CONFIGURATION.md` 注入，Secret 从 Secret Manager 读取。
- 执行 Alembic 迁移。
- Health Check 就绪（`/api/v1/health`）。
- 运行 Smoke Test。

## 4. 环境隔离清单

- 各环境独立 `DATABASE_URL` / Secret / 日志目标。
- 禁止开发 Key 出现在生产配置，反之亦然。
- 日志与审计不得包含 Secret。
