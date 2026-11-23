# API 设计 — admin（管理台）+ relay（中转）

| 属性 | 值 |
|------|-----|
| 模块 | admin / relay |
| 版本 | v1.0 |
| 日期 | 2026-11-23 |
| 规约依据 | python-fastapi `backend-02-api-conventions.md`（{stack.api_spec}） |

## 1. 模块设计概述

### 1.1 业务背景及目标
为单管理员提供密钥治理与用量观测的 REST 管理接口，并重构中转接口为双目标可部署。解决「密钥只能 SSH 改、用量不可见」的问题。

### 1.2 边界说明
- 做：管理台 CRUD/启停/统计/日志/配置只读；中转透传；健康检查。
- 不做：多管理员/RBAC、限流配额、审批流、跨实例聚合、WebSocket。

### 1.3 设计决策
| 决策点 | 选择 | 理由 |
|--------|------|------|
| 接口风格 | REST + 真实 HTTP 状态码 + 统一错误体 | 栈规约；与既有 /health、OpenAI 错误体同形 |
| 管理鉴权 | Authorization: Bearer ADMIN_TOKEN（恒定时间比较） | 单管理员；与客户端密钥解耦 |
| 字段命名 | snake_case | Python/FastAPI 惯例，与 /health 一致 |
| 主键 | TEXT(32) uuid4().hex | 栈规约，禁自增 |
| 分页 | pageNum/pageSize + records/total | 栈规约 |
| 密钥展示 | 脱敏（末 4 位），完整值仅创建返回一次 | 安全 |
| MQ/审批/工作流 | 不适用（N/A） | 本栈无消息队列与审批 |

### 1.4 领域对象总览
| 对象 | 角色 | 功能类型 |
|------|------|---------|
| UpstreamKey | 聚合根 | 主数据类 |
| ClientKey | 聚合根 | 主数据类 |
| RequestLog | 聚合根 | 台账报表类 |
| UsageAggregate | 聚合根 | 台账报表类 |
| RelayConfig | 值对象 | 只读 |

### 1.5 上下文映射
Relay → Admin：经仓储接口读启用密钥、写 RequestLog（ACL）。Admin → 前端：OHS REST。Relay → NIM：透传（遵奉者）。

## 2. 跨聚合根设计
N/A — 多聚合根但无跨聚合根不变量/编排（密钥与日志独立，日志以 ID 引用密钥，最终一致）。

## 3. 应用/基础设施层设计

### 3.1 接口规范
- 基础路径：管理 `/api/v1/admin`；中转 `/v1/*`（透传）；健康 `/health`；前端 `/admin/*`（静态）
- 方法：REST 语义（GET 查/POST 建/DELETE 删/POST {id}/{action} 动作）
- 成功：200/201/204；错误：真实状态码 + 统一错误体
- 保留前缀（透传 catch-all 必须排除）：`/api`、`/admin`、`/health`、`/static`

### 3.2 统一错误体
```json
{ "error": { "code": "not_found", "message": "上游密钥不存在", "details": [] } }
```
| 状态码 | code | 含义 |
|--------|------|------|
| 401 | unauthorized | 缺失/无效管理令牌或客户端密钥 |
| 403 | forbidden | 已认证无权限 |
| 404 | not_found | 资源不存在 |
| 409 | conflict | 重复/非法状态流转 |
| 422 | validation_error / invalid_input | 参数校验失败 |
| 500 | internal_error | 内部错误 |
| 503 | upstream_unavailable | 上游不可达 |

### 3.3 权限模型
| 角色 | 操作权限 |
|------|---------|
| Owner（ADMIN_TOKEN） | /api/v1/admin/* 全部 |
| ApiClient（客户端密钥） | /v1/* 透传 |
| 公开 | /health |
数据权限：单管理员，无行级隔离。

### 3.4 公共规范
- 枚举（见 {conv.enum_pool}）：auth_mode、key_status、client_key_status、stream_mode、bucket_type、dimension_type
- 时间：ISO 8601 UTC（...Z）
- 分页请求：pageNum(默认1)/pageSize(默认20,上限100)；响应 {records,total,pageNum,pageSize}
- 配置项：ADMIN_TOKEN、NVIDIA_API_KEYS、PROXY_API_KEYS、NIM_UPSTREAM、CONNECT_TIMEOUT、READ_TIMEOUT、PORT、DB_PATH

## 4. 聚合根详细设计

### 4.1 UpstreamKey（主数据类）

**领域模型 / 表 np_upstream_key**
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT(32) | PK | uuid4().hex |
| label | TEXT | NOT NULL | 备注名 |
| secret | TEXT | NOT NULL | nvapi- 完整值（存储），展示脱敏 |
| enabled | INTEGER | NOT NULL DEFAULT 1 | 0/1 |
| created_at | TEXT | NOT NULL | ISO UTC |
| updated_at | TEXT | NOT NULL | ISO UTC |
| last_used_at | TEXT | NULL | 最近转发使用 |
| last_error_status | INTEGER | NULL | 最近上游错误码 |
| consecutive_failures | INTEGER | NOT NULL DEFAULT 0 | 连续失败计数 |

不变量：secret 非空且 nvapi- 前缀；enabled∈{0,1}；consecutive_failures≥0。
状态：enabled ↔ disabled（手动，无自动）。

**接口清单**
| 接口 | 方法 | 路径 | 权限 |
|------|------|------|------|
| 列表 | GET | /api/v1/admin/upstream-keys | Owner |
| 创建 | POST | /api/v1/admin/upstream-keys | Owner |
| 详情 | GET | /api/v1/admin/upstream-keys/{id} | Owner |
| 删除 | DELETE | /api/v1/admin/upstream-keys/{id} | Owner |
| 启用 | POST | /api/v1/admin/upstream-keys/{id}/enable | Owner |
| 停用 | POST | /api/v1/admin/upstream-keys/{id}/disable | Owner |

**UpstreamKeySaveAo**：{label: str(1..128), secret: str(nvapi-..., ≥20)}
**UpstreamKeyListVo/DetailVo**：{id, label, secret_masked, enabled, created_at, updated_at, last_used_at, last_error_status, consecutive_failures}
**创建响应**：201，DetailVo + secret（完整值，仅此一次）
**校验**：label 必填长度；secret 前缀/长度；id 不存在→404；删除不存在→404。
**错误码**：validation_error(422)、not_found(404)、unauthorized(401)。

### 4.2 ClientKey（主数据类）

**表 np_client_key**
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT(32) | PK | |
| name | TEXT | NOT NULL | 名称/备注 |
| secret | TEXT | NOT NULL | 服务端生成 sk-... |
| enabled | INTEGER | NOT NULL DEFAULT 1 | |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | NOT NULL | |
| last_used_at | TEXT | NULL | |
| revoked_at | TEXT | NULL | 软删除终态时间 |

状态：enabled ↔ disabled；→ revoked（终态）。
**接口**：GET 列表 / POST 创建{name} / GET {id} / DELETE {id}(软撤销) / POST {id}/enable / POST {id}/disable，路径 /api/v1/admin/client-keys。
**ClientKeySaveAo**：{name: str(1..128)}（secret 服务端生成）
**ClientKeyListVo/DetailVo**：{id, name, secret_masked, enabled, created_at, updated_at, last_used_at, revoked_at}
**创建响应**：201 + secret（完整值仅一次）。
**规则**：已 revoked 的密钥不可再启停（409 conflict）；撤销后鉴权立即拒绝。

### 4.3 RequestLog（台账报表类，只读）

**表 np_request_log**
| 字段 | 类型 | 约束 |
|------|------|------|
| id | TEXT(32) | PK |
| ts | TEXT | NOT NULL, 索引 |
| client_key_id | TEXT(32) | NULL, 索引（纯透传模式无客户端密钥） |
| upstream_key_id | TEXT(32) | NULL |
| method | TEXT | NOT NULL |
| path | TEXT | NOT NULL |
| model | TEXT | NULL（尽力提取） |
| status | INTEGER | NOT NULL, 索引 |
| latency_ms | INTEGER | NOT NULL |
| stream | INTEGER | NOT NULL 0/1 |
| prompt_tokens | INTEGER | NULL |
| completion_tokens | INTEGER | NULL |

**接口**：GET /api/v1/admin/request-logs
**RequestLogQueryAo**：{clientKeyId?, model?, status?, start?, end?, pageNum=1, pageSize=20}
**响应**：PageVo<RequestLogListVo>；RequestLogListVo={id,ts,client_key_id,client_key_name,upstream_key_id,upstream_key_label,method,path,model,status,latency_ms,stream,prompt_tokens,completion_tokens}
**规则**：只读；保留 30 天（过期清理）；按 ts 倒序。

### 4.4 UsageAggregate（台账报表类，只读）

**表 np_usage_aggregate**
| 字段 | 类型 | 约束 |
|------|------|------|
| id | TEXT(32) | PK |
| bucket | TEXT | NOT NULL（小时/天起点 ISO） |
| bucket_type | TEXT | NOT NULL（hour/day） |
| dimension_type | TEXT | NOT NULL（key/model/status） |
| dimension_value | TEXT | NOT NULL |
| requests | INTEGER | NOT NULL DEFAULT 0 |
| errors | INTEGER | NOT NULL DEFAULT 0 |
| rate_limited | INTEGER | NOT NULL DEFAULT 0 |
| prompt_tokens | INTEGER | NOT NULL DEFAULT 0 |
| completion_tokens | INTEGER | NOT NULL DEFAULT 0 |
唯一约束：(bucket,bucket_type,dimension_type,dimension_value)。

**接口**：GET /api/v1/admin/usage
**UsageQueryAo**：{dimensionType=key|model|status, bucketType=hour|day, start?, end?}
**响应**：{records:[UsageVo], total}；UsageVo={bucket,bucket_type,dimension_type,dimension_value,requests,errors,rate_limited,prompt_tokens,completion_tokens}

### 4.5 看板与配置（只读）

- GET /api/v1/admin/dashboard → DashboardVo={status, upstream, auth_mode, upstream_key_count, client_key_count, today:{requests,errors,rate_limited}}
- GET /api/v1/admin/config → ConfigVo={upstream, connect_timeout, read_timeout, auth_mode, port, db_backend}（只读，env 来源）

### 4.6 中转与健康（relay）

- GET /health（公开）→ {status, upstream, upstream_keys, proxy_auth}
- ANY /v1/{path:path}（客户端密钥鉴权或纯透传）→ 原样透传上游；401/403/429 换钥重试；SSE 流式回传。catch-all 最后注册并排除保留前缀。
- 遥测：每请求只读提取 model/usage 写 RequestLog（不改字节，超大体跳过）。

## 5. 模块清单汇总

### 5.1 对外服务清单
| 服务 | 接口 |
|------|------|
| 启用上游密钥读取（内部） | 仓储 list_enabled_upstream_keys() |
| 启用客户端密钥校验（内部） | 仓储 find_enabled_client_key(secret) |
| 管理台 REST | /api/v1/admin/*（上表） |

### 5.2 SQL 清单 / DDL
四表：np_upstream_key、np_client_key、np_request_log、np_usage_aggregate（字段见 4.x）；索引：request_log(ts,status,client_key_id)、usage_aggregate 唯一约束。迁移文件 migrations/001_init.sql（服务器与 D1 共用）。

## 6. 更新记录

| 版本 | 日期 | 变更类型 | 说明 |
|------|------|---------|------|
| v1.0 | 2026-11-23 | initial | 首次生成（admin CRUD/启停/统计/日志/配置 + relay 透传/健康） |
