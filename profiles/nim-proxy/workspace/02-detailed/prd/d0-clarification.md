# D0 需求澄清报告 — NIM Proxy 管理台 + 双目标中转

| 属性 | 值 |
|------|-----|
| 日期 | 2026-11-23 |
| 模块 | admin（管理台，新增）+ relay（中转，双目标改造） |
| 需求类型 | 新增（admin）+ 增强/迁移（relay） |
| 状态 | 澄清完成，可进入 D1 |

## 1. 需求原文与解析

用户诉求：「首先把架构（profile）建立起来，技术栈沿用现有项目；然后看是否做一个前端管理页面」。
经确认：**做标准版管理台**，前端 React+Vite，部署双目标（自建服务器 + Cloudflare Workers），一套 Python。

## 2. 概念匹配（对照既有架构）

| 概念 | 匹配结果 | 处理 |
|------|---------|------|
| 上游密钥 / 客户端密钥 / 中转请求 / 上游 / 服务实例 | 完全匹配（business-concepts 既有） | 沿用，补生命周期状态 |
| 管理台（Admin 域） | 无匹配 → 新增 | D1 初始生成 |
| 用量统计 / 请求日志 | 无匹配 → 新增 | 新实体 |
| 双目标运行时 | 无匹配 → 新增（ADR-009） | 适配层设计 |

## 3. 已确认决策

| # | 决策 | 来源 |
|---|------|------|
| D0-1 | 管理台标准版：运行状态看板 + 密钥管理（SQLite/D1 持久化、免重启）+ 用量统计与请求日志 + 单管理员令牌登录 | 用户选择 |
| D0-2 | 前端 React 19 + Vite + TS（react-vite-web 栈），产物由后端托管 | 用户选择（ADR-011） |
| D0-3 | 双目标：服务器（uvicorn+SQLite）+ Workers（D1+workers.fetch），一套 Python | 用户选择 + go/no-go GO（ADR-009/010） |
| D0-4 | 用量统计 = 请求级 + token 尽力统计：只读提取 model/usage，字节原样透传；超大请求体跳过解析 | 用户选择（修订 ADR-001 为「只读检视、不改字节」） |
| D0-5 | 上游密钥生命周期 = 手动启停（enabled/disabled）+ 健康可见（最近错误码/连续失败次数）；**不自动停用** | 用户选择（解决 kb Q1） |
| D0-6 | 生产 Workers：Worker `nim-proxy` + 域名 `nim-proxy.tonyxyz.com`；spike 验证后删除；B 阶段服务器先行迁移再补 CF 适配器 | 用户选择 |

## 4. 默认假设（用户未异议，按此执行）

- 单管理员：`ADMIN_TOKEN` 环境变量；管理页登录输入令牌 → 会话内保存 → `Authorization: Bearer` 调 `/api/v1/admin/*`；未配置令牌时管理接口禁用（中转不受影响）
- 客户端密钥属性：名称/备注、enabled、created_at、last_used_at；撤销 = 软删除（revoked）
- 请求日志保留 30 天（原始），按小时/天聚合长期保留；两实例各自统计，不跨实例聚合
- 管理页中文界面；图表用轻量库（D4 定）
- 后端从单文件 app.py 迁移为 app/ 包（栈分层约定），deploy.sh 同步调整

## 5. 角色与权限

| 角色 | 操作 |
|------|------|
| 管理员（Owner，单管理员） | 看板、密钥增删启停、用量/日志查询、配置查看 |
| 客户端调用方（ApiClient） | 仅 `/v1/*` 中转（客户端密钥鉴权），无管理权限 |

## 6. 核心实体（D2 建模输入）

- UpstreamKey（上游密钥）：id、label、secret（脱敏展示）、enabled、created_at、last_used_at、last_error_status、consecutive_failures
- ClientKey（客户端密钥）：id、name、secret、enabled、created_at、last_used_at、revoked_at
- RequestLog（请求日志）：id、ts、client_key_id、upstream_key_id、method、path、model、status、latency_ms、stream、prompt_tokens、completion_tokens
- UsageAggregate（用量聚合）：bucket（hour/day）、维度（client_key/model/status）、requests、errors、tokens
- RelayConfig（运行配置）：upstream、timeouts、auth_mode（只读展示，env 来源）

## 7. 状态机

- UpstreamKey：enabled ↔ disabled（手动）；无自动流转
- ClientKey：enabled ↔ disabled（手动）；enabled/disabled → revoked（终态，软删除）
- RequestLog：无状态（追加写 + 过期清理）

## 8. 边界（不做）

- 多管理员/多租户/RBAC；客户端自助门户
- 按密钥限流/配额（未来增强）
- token 精确计费（尽力统计，流式 usage 依赖客户端 include_usage）
- 跨实例聚合；WebSocket 透传（NIM 不涉）
- 管理接口的审批流/工作流（不适用）

## 9. 集成关系

- 上游：NVIDIA NIM（OpenAI 兼容，透传）
- 存储：服务器 SQLite 文件 / Workers D1（同一套迁移 SQL）
- 前端：React SPA，同源 `/admin`（Workers 静态资源绑定 / 服务器静态目录）
