<!-- kb-generated: 2026-11-23 | sources: 5 | assumptions: 1 | open: 0 -->

# 架构选择知识库

> 领域划分与技术栈版本。来源见 [source-index.md](../source-index.md)。

## 领域划分

| 领域 | 英文 | 类型 | 职责 | 模块 |
|------|------|------|------|------|
| 中转 | Relay | core | 客户端鉴权、上游密钥轮询、请求透传、流式回传、健康检查 | relay（既有实现，状态见 workspace/INDEX.md） |
| 管理台 | Admin | supporting | 密钥管理、用量统计、运行状态可视化 —— 已立项（标准版），范围见 ADR-009/011 | admin（未建设） |

应用是单体服务，当前只有中转一个领域，所有代码在单文件 `app.py` 中；B 阶段拆分为 `app/` 包。

## 部署目标（ADR-009，2026-11-23 实测）

| 目标 | 运行时 | 数据层 | 出站 HTTP | 入口 |
|------|--------|--------|-----------|------|
| 自建服务器（Vultr / 搬瓦工） | uvicorn 单 worker + systemd | SQLite 文件（data/） | httpx | `uvicorn app.main:app` |
| Cloudflare Workers | Python Workers（CPython 3.14 WASM，快照冷启动 ~4 s） | D1（同一套 SQLite 迁移 SQL） | `workers.fetch`（ADR-010） | `workers.asgi.entrypoint(app)` |

| 组件 | 开发机实测版本 | 声明约束（requirements.txt） | 备注 |
|------|--------------|---------------------------|------|
| Python | 3.12.6（服务器目标）/ 3.14.2（Workers 实测） | 未声明 | ⚠️假设：语法基线 3.10+（A4，双端均满足）；Workers 需付费版 $5/月 |
| FastAPI | 0.163.1（本机）/ 0.165.0（spike） | >=0.111 | |
| uvicorn | 0.54.0 | >=0.30（standard extras） | 仅服务器目标 |
| httpx | 0.28.1 | >=0.27 | 服务器出站 + 测试客户端；Workers 上禁用（ADR-010） |
| pydantic | 2.14.3 | 随 FastAPI 引入 | |
| starlette | 1.10.0 | 随 FastAPI 引入 | |
| pytest | 9.1.1 | 未列入依赖 | 开发机已装；项目目前没有测试 |
| React 19 + Vite + TS | react-vite-web 栈（引擎随发） | — | 管理台前端（ADR-011），产物由后端托管 |
| 部署 | systemd + uvicorn；可选 nginx + certbot；Workers = wrangler deploy | — | 服务器目录 `/opt/nim-proxy`，服务名 `nim-proxy`；workers.dev 域名在国内不可达，必须自定义域名 |
