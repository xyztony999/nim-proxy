<!-- kb-generated: 2026-11-23 | sources: 5 | assumptions: 0 | open: 0 -->

# 设计决策知识库（业务向 ADR）

> 只收本项目拍过的板；栈级通用决策不在此列。来源见 [source-index.md](../source-index.md)。

| 编号 | 决策 | 影响 | 来源 |
|------|------|------|------|
| ADR-001 | 请求体与响应体不解析、原样透传 | NIM 升级参数无需改代码；代价是无法在转发层按请求内容做统计或限流 | README.md、app.py |
| ADR-002 | 客户端用自定义密钥访问代理，真实 NIM 密钥只存服务器 | 上游密钥不暴露给客户端；更换上游密钥不影响客户端 | README.md |
| ADR-003 | 多把上游密钥轮询，401/403/429 自动换下一把重试 | 单把密钥失效时服务不中断；不解决账户级限速 | README.md |
| ADR-004 | 全部行为由环境变量配置（`.env` + systemd `EnvironmentFile`） | 改配置需重启服务；没有运行时配置界面 | README.md、app.py |
| ADR-005 | 部署形态：systemd + uvicorn 单 worker；可选 nginx + certbot 提供 HTTPS | 进程内状态仅在单 worker 下有效；浏览器端客户端必须走 HTTPS | README.md、deploy.sh |
| ADR-006 | CORS 全开放 | 浏览器端客户端（LobeChat / NextChat 等）可直接调用 | app.py |
| ADR-007 | 关闭交互式文档端点（`/docs`、`/redoc`） | 减少公网暴露面 | app.py |
| ADR-008 | 两台海外 VPS 各部署一个实例，互为备份，实例间不共享状态 | 没有中心配置；两端配置需各自维护 | README.md |
| ADR-009 | 部署目标 = 双目标（自建服务器 + Cloudflare Workers），一套 Python 代码（2026-11-23 go/no-go 实测 GO，报告见 workspace/05-reports/2026-11-23-cf-workers-gonogo.md） | 仓储层抽象为接口（服务器=SQLite 文件 / Workers=D1）；禁用进程内跨请求状态；Workers 付费版为前提 | 用户决策 + spike 实测 |
| ADR-010 | Workers 上出站请求统一走 `workers.fetch`（SDK 封装），不用 httpx | httpx jsfetch 传输层带体 POST 在部分隔离实例挂起（F-1）；workers.fetch 实测 POST/SSE 稳定；服务器端仍用 httpx（运行时适配层按平台选择） | spike F-1 |
| ADR-011 | 中转管理台前端 = React 19 + Vite + TS 工程（引擎 react-vite-web 栈），构建产物由后端托管（Workers 走静态资源绑定 / 服务器走静态目录） | 构建门禁 typecheck+lint+build；发布需本机构建 | 用户决策 |
