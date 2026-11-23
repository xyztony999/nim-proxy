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
