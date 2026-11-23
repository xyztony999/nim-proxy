# PRD — NIM Proxy 管理台与双目标中转

| 属性 | 值 |
|------|-----|
| 模块 | admin（管理台）+ relay（中转双目标改造） |
| 版本 | v1.0 |
| 日期 | 2026-11-23 |
| 功能类型 | 主数据类（密钥）+ 台账报表类（日志/统计）+ 透传工具类（中转） |

## 1. 业务目标（G1）

为服务所有者提供密钥治理与用量观测能力，把原本散落在环境变量、只能 SSH 修改的密钥与配置变成可视化、免重启可治理的对象；同时让中转服务可部署到自建服务器与 Cloudflare Workers 两个目标。服务对象：单管理员（Owner）；客户端调用方（ApiClient）仅使用中转 API。

## 2. 功能范围（G2）

**做**：
- 运行状态看板（服务状态/上游/密钥数/鉴权模式/今日请求·错误·429 计数）
- 上游密钥管理（增/删/脱敏查/启停/健康记录）
- 客户端密钥管理（签发/撤销/脱敏查/启停/最近使用）
- 用量统计（按密钥/模型/状态维度，小时/天聚合，token 尽力统计）
- 请求日志查询（明细+筛选+分页，保留 30 天）
- 运行配置只读展示
- 中转双目标改造（服务器 SQLite / Workers D1；出站 httpx / workers.fetch）
- 单管理员令牌登录

**不做**：多管理员/RBAC/多租户；客户端自助门户；按密钥限流配额；token 精确计费；跨实例聚合；WebSocket 透传；审批流。

## 3. 角色定义（G3）

| 角色 | 职责 | 权限 |
|------|------|------|
| 管理员 Owner | 治理密钥、观测用量、查看配置 | 管理台全部（ADMIN_TOKEN 鉴权） |
| 客户端调用方 ApiClient | 调用 /v1/* 中转 | 仅中转（客户端密钥鉴权），无管理权限 |

## 4. 领域对象与关系（G4/G5）

- UpstreamKey（上游密钥，聚合根）：被 relay 轮询引用
- ClientKey（客户端密钥，聚合根）：被 relay 鉴权引用
- RequestLog（请求日志，聚合根/台账）：引用 client_key_id、upstream_key_id
- UsageAggregate（用量聚合，聚合根/台账）：由 RequestLog 聚合
- RelayConfig（运行配置，值对象/只读）：env 来源

关系：relay 读 UpstreamKey/ClientKey（启用态）；relay 每请求写 RequestLog；UsageAggregate 由 RequestLog 周期聚合；RequestLog 以 ID 引用两类密钥。

## 5. 业务字段（T1）

| 对象 | 关键字段 |
|------|---------|
| UpstreamKey | id, label, secret(脱敏), enabled, created_at, last_used_at, last_error_status, consecutive_failures |
| ClientKey | id, name, secret(脱敏), enabled, created_at, last_used_at, revoked_at |
| RequestLog | id, ts, client_key_id, upstream_key_id, method, path, model, status, latency_ms, stream, prompt_tokens, completion_tokens |
| UsageAggregate | bucket, bucket_type, dimension_type, dimension_value, requests, errors, rate_limited, prompt_tokens, completion_tokens |

## 6. 状态流转（T2）

- UpstreamKey：enabled ↔ disabled（手动，ADR-013，不自动停用）
- ClientKey：enabled ↔ disabled；enabled/disabled → revoked（终态，软删除）
- RequestLog/UsageAggregate：无状态（追加+过期清理）

## 7. 查询筛选（T4）

- 请求日志：按 client_key_id / model / status / 时间范围筛选；分页 pageNum/pageSize
- 用量统计：按 dimension_type（key/model/status）+ bucket_type（hour/day）+ 时间范围

## 8. 被引用关系（T1a）

UpstreamKey/ClientKey 被 relay 核心域引用 → 需提供「启用密钥」服务接口（内部仓储读取，非对外 CRUD）。

## 9. 非功能（N1-N4）

- N1 性能：个人用量（≤40 RPM 账户级）；单 worker / Workers 单请求隔离；日志保留 30 天
- N2 异常：上游 401/403/429 换钥重试；管理接口未配置 ADMIN_TOKEN 时禁用（中转不受影响）；密钥比较恒定时间
- N3 规则：透传只读检视不改字节（ADR-012）；超大请求体跳过解析；密钥完整值仅创建时返回一次
- N4 历史：请求日志即审计；密钥健康计数可追溯

## 10. 集成（T6）

上游 NVIDIA NIM（OpenAI 兼容，透传，ACL 防腐）；存储 SQLite/D1（共用迁移 SQL）；前端 React SPA 同源 /admin。

## PRD 完备性检查 — 通过

功能类型：主数据 + 台账报表 + 透传工具
检查项：G1-G5 ✅ / T1,T1a,T2,T4,T6 ✅ / N1-N4 ✅（T3 审批、T5 导出、T7-T9 不适用）
可进入 D3 API 设计。
