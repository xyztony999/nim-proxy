# nim-proxy 后端代码生成任务清单（B1-B7）

> 创建时间：2026-11-23
> 设计文档：profiles/nim-proxy/workspace/02-detailed/api/api-admin.md
> 代码输出：D:/Project/nim-proxy（app/ 包 + workers/ 适配）
> 编排依据：python-fastapi backend-orchestrator（会话内执行）

## 数据层
- [x] T01 · DDL 与仓储接口 + SQLite 实现（migrations/001_init.sql；repositories/base.py + sqlite.py）

## 代码生成
- [x] T02 · schemas（Ao/Vo/枚举）+ 领域异常 + 错误体映射
- [x] T03 · services（keys / telemetry / relay）
- [x] T04 · api（admin router + relay/health + deps + 异常处理 + main 装配）
- [x] T05 · 双目标适配（core/http_client + workers/entry + workers/http_client + workers/d1_repository）

## 测试与验证
- [x] T06 · pytest（keys CRUD/启停、telemetry 查询、relay 透传/重试/鉴权、admin API 全链路）
- [x] T07 · 合规检查（backend-rules C1-C12 + compileall + pytest）
