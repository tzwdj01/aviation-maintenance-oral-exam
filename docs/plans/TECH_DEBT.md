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
