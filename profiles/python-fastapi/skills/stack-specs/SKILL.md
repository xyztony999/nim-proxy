---
name: stack-specs
description: Python FastAPI 后端编码规约与生成模板统一技能（Python / FastAPI / Pydantic v2 / httpx / SQLite，随栈激活挂载）
---

# Python FastAPI — 代码规格（stack-specs）

> **层级**：L2 技术栈 profile skills，随栈激活挂载。配套规则正文：本栈 `rules/backend-rules.md`（Gate 2 等价规则集，激活后位于 `.claude/rules/`）。
> **性质**：强制规约，所有使用本栈的代码必须遵循。文中 `{module}`/`{service}` 为占位符（业务 profile 替换）；📎 标记处为通用示例。

**使用方式**：生成/审查代码时，根据当前任务类型引用对应专题文件。

## 文件清单

| 文件 | 主题 |
|------|------|
| [backend-01-architecture.md](backend-01-architecture.md) | 分层架构：工程布局、依赖方向、错误处理、lifespan 与依赖注入、单 worker 约束 |
| [backend-02-api-conventions.md](backend-02-api-conventions.md) | API 设计规约：路径、HTTP 方法与状态码、统一错误体、分页、鉴权、D3 章节映射（design skill D3 引用 `{stack.api_spec}`） |
| [backend-03-patterns.md](backend-03-patterns.md) | 常用模式：配置加载、SQLite 访问与迁移、流式透传、鉴权依赖、脱敏、后台任务、测试模板 |
| [backend-04-validation-checklist.md](backend-04-validation-checklist.md) | 合规验证清单（CRITICAL/WARNING 扫描项，与 rules §8 对应） |

## 快速定位

- 生成 repository / 搭建工程骨架 → [backend-01-architecture.md](backend-01-architecture.md)
- 设计/生成 REST 接口 → [backend-02-api-conventions.md](backend-02-api-conventions.md)
- 写配置加载 / DDL / 流式透传 / 鉴权 / 测试 → [backend-03-patterns.md](backend-03-patterns.md)
- 收尾合规检查 → backend-04 / rules §8
