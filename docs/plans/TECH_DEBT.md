# Tech Debt（技术债与架构偏差登记）

> Status: ACTIVE
> Owner: 项目治理负责人
> Last Reviewed: 2026-08-16（Phase 0 Governance Baseline）

Phase 0 审阅发现的、**不构成本阶段业务修改范围**但需后续治理的事项。
每项记录影响、建议与所需授权。

## 1. 配置环境变量命名与规范名不一致

- **现状**：代码与 `.env.example` 使用 `MIMO_API_BASE_URL` / `DEEPSEEK_API_BASE_URL` /
  `OPENAI_API_BASE_URL` / `DEEPSEEK_MODEL` / `OPENAI_MODEL`。
- **规范目标**：`MIMO_BASE_URL` / `DEEPSEEK_BASE_URL` / `OPENAI_BASE_URL` /
  `DEEPSEEK_DEFAULT_MODEL` / `OPENAI_DEFAULT_MODEL`（`docs/CONFIGURATION.md`）。
- **处理**：Phase 0 已在 `backend/app/core/config.py` 通过 `AliasChoices` 支持规范名（legacy 名仍可用），
  未破坏现有 `.env`。
- **后续**：在进入 Sprint 1A Gate 前，确认是否移除 legacy 名（需人工批准；影响 `.env` 用户）。

## 2. main 分支为空，工作内容在 feature 分支

- **现状**：`main` 仅含空初始化提交；全部内容位于
  `feature/sprint-1a-multi-provider-foundation`。
- **影响**：任何基于 `main` 的 PR/发布都会丢失 Sprint 1A 内容。
- **建议**：确认分支策略（如：将 feature 合并到 main，或长期以 feature 为集成分支）并登记 ADR 或治理决定。

## 3. Qualification 原始产物未入库

- **现状**：`scripts/qualification/`（含 `qualification_v2_output*/`）被 `.gitignore` 排除，
  仓库内仅有结论登记（`seed.py`、`docs/qualification/qualification-history.md`）。
- **影响**：未来难以复核历史评估。
- **建议**：将评估产物（脱敏后）纳入受控存储并在 qualification-history 登记位置，或制定归档流程。

## 4. 前端为壳，无正式工作台

- **现状**：`frontend` 仅 LLM Profile 列表。
- **影响**：不属于 Phase 0 范围；按 Roadmap 在 Sprint 3 处理。

## 5. 生产 worker 未实现

- **现状**：`app/services/jobs.py` 仅开发用 fake worker。
- **影响**：生产恢复性依赖 DB TaskJob；worker 实现在 Sprint 1B/2 完成。

## 6. 既有代码未通过 ruff format

- **现状**：Phase 0 前提交的代码未按 `ruff format` 排版，`ruff format --check` 对既有文件报告 27 个文件需重排
  （涉及 `backend/app/ai/providers/*`、`models/domain.py`、`db/seed.py`、`tests/test_sprint_1a.py` 等）。
- **影响**：格式检查不能作为 CI 门槛直接启用。
- **处理**：Phase 0 仅格式化新增/修改文件（`core/config.py`、`tests/test_config.py`），
  未批量重排既有代码（避免大范围无关 diff）。
- **后续**：经人工批准后，单独提交一次 `ruff format` 全量排版，再启用 CI 格式门槛。

## 7. /admin 路由缺少管理员鉴权（Sprint 1A Conformance Review）

- **现状**：`/api/v1/admin/llm-profiles` 仅依赖 `get_db`，匿名调用者可创建/修改 Profile 并改变默认评估模型。
  已修复最严重的部分：创建时强制 `UNTESTED`（禁止自证 qualification）。完整鉴权/RBAC 需要用户模型，超出 Sprint 1A 范围。
- **Gate 条件**：任何非开发环境的公开部署前必须补齐 admin 鉴权/RBAC（列入 Sprint 2 认证与 RBAC）。

## 8. 状态迁移的 state_version 检查未在数据库层原子化

- **现状**：`app/exam/state_machine.py` 的乐观锁检查是内存级比较；并发事务可在提交时互相覆盖。
  Sprint 1A 尚无 attempt 变更端点，此路径当前不可达。
- **后续**：实现考试编排端点时，必须用条件更新（`UPDATE ... WHERE state_version = expected`）原子化持久化，
  拒绝零行更新（`docs/EXAM_STATE_MACHINE.md` §3）。

## 9. 术语标准化多次出现仅记录首个映射（P2，PR #1 评审）

- **现状**：`app/normalization/normalizer.py` 对同一 alias 多次出现时 `str.replace` 替换全部，但只记录首个偏移，
  且长度变化的替换会漂移后续坐标，审计映射不完整。
- **后续**：逐次出现地应用替换并相对原文记录坐标（保证每个标准化都可逆、可追溯）。

## 10. 幂等并发预留未序列化（P2，PR #1 评审）

- **现状**：`execute_idempotently` 在并发新 key 下可能双执行 handler；唯一键冲突时一方失败而非重放。
- **后续**：先预留/锁定幂等键再执行 handler，令竞争者等待或读取已完成记录（`docs/EXAM_STATE_MACHINE.md` §3）。

## 11. 前端开发代理/CORS 未配置（P2，PR #1 评审）

- **现状**：Vite 开发服务器与 API 不同源，`frontend/src/api.ts` 默认调用 `localhost:8000`，无 CORS/代理时浏览器拦截。
- **后续**：配置 scoped 开发 CORS 或 Vite dev proxy（Sprint 3 前端工作台落地时一并处理）。
