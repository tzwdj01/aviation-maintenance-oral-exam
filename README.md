# 航空维修放行人员 AI 口试系统

## Sprint 1A 状态

当前已具备可运行的模型无关后端基础：SQLAlchemy/Alembic 审计模型、严格状态机、证据解析、
确定性 Decimal 评分、版本化术语标准化、LLM Profile 管理 API，以及 MiMo/DeepSeek/OpenAI 的
Provider Adapter 契约。前端仅提供开发期 LLM Profile 列表壳；正式考试工作台不属于本 Sprint。

详细实现和本地启动说明见 [多 Provider 设计](docs/multi-provider-design.md)。

本仓库当前处于设计阶段。系统面向维修放行人员培训、模拟口试、授权前能力评估辅助和考官辅助评分；AI 不作为正式授权的唯一决定者。

当前已完成的设计文档位于 [`docs/`](/Users/lucky/Documents/ChatGPT/放行人员口试/docs)：

- [产品需求](/Users/lucky/Documents/ChatGPT/放行人员口试/docs/PRD.md)
- [系统架构](/Users/lucky/Documents/ChatGPT/放行人员口试/docs/architecture.md)
- [数据模型](/Users/lucky/Documents/ChatGPT/放行人员口试/docs/data-model.md)
- [评分机制](/Users/lucky/Documents/ChatGPT/放行人员口试/docs/scoring-design.md)
- [考试状态机](/Users/lucky/Documents/ChatGPT/放行人员口试/docs/exam-state-machine.md)
- [MiMo 集成](/Users/lucky/Documents/ChatGPT/放行人员口试/docs/mimo-integration.md)
- [API 设计](/Users/lucky/Documents/ChatGPT/放行人员口试/docs/api-design.md)
- [前端设计](/Users/lucky/Documents/ChatGPT/放行人员口试/docs/frontend-design.md)
- [测试策略](/Users/lucky/Documents/ChatGPT/放行人员口试/docs/testing-strategy.md)
- [技术风险](/Users/lucky/Documents/ChatGPT/放行人员口试/docs/risks.md)

## 目标目录结构（尚未实现）

```text
backend/app/{api,models,schemas,repositories,services,ai,scoring,exam,audio,core}
backend/{alembic,tests}
frontend/src/{api,features,components,hooks,pages,routes,types}
docs/
infra/
scripts/
```

禁止将 MiMo API Key 写入源码或前端。业务代码、数据库迁移、外部 API 调用和依赖安装均等待人工架构评审后进行。
