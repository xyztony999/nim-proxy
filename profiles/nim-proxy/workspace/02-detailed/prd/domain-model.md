# 领域模型 — NIM Proxy

| 属性 | 值 |
|------|-----|
| 版本 | v1.0 |
| 日期 | 2026-11-23 |
| 范围判定 | PRD 标注模块（admin/relay）→ 范围明确，跳过战略设计 Step 1-3 |

## 本域信息

| 项目 | 内容 |
|------|------|
| 本域名称 | Admin（密钥治理 + 用量观测，支撑域）；Relay（中转，核心域） |
| 领域分层 | Relay=核心域；Admin=支撑域；运行时适配/遥测=通用域（平台） |
| 聚合根 | UpstreamKey、ClientKey、RequestLog、UsageAggregate |

## 业务域清单

| 上下文名 | 领域分层 | 聚合根 | 核心职责 | 关联上下文 |
|---------|---------|--------|---------|-----------|
| Relay | 核心域 | （RelayRequest 为过程数据，无持久聚合根） | 鉴权/选钥/透传/回传/重试 | Admin（读密钥、写遥测） |
| Admin | 支撑域 | UpstreamKey, ClientKey, RequestLog, UsageAggregate | 密钥治理 + 用量观测 | Relay（被引用） |
| Platform | 通用域 | — | 健康/运行时适配/遥测采集 | 全部 |

## 领域对象清单

| 对象名 | 分类 | 与上级关系 | 核心业务字段 | 关键枚举字段 | 备注 |
|--------|------|-----------|------------|------------|------|
| UpstreamKey | 聚合根 | Admin 域入口 | id,label,secret,enabled,created_at,last_used_at | enabled(bool) | A2/A3/A4 通过；被 Relay 引用 |
| KeyHealth | 值对象 | UpstreamKey 内嵌 | last_error_status,consecutive_failures | — | 不可变，替换 |
| ClientKey | 聚合根 | Admin 域入口 | id,name,secret,enabled,created_at,last_used_at,revoked_at | enabled(bool) | 撤销=软删除终态 |
| RequestLog | 聚合根（台账） | Admin 域入口 | id,ts,client_key_id,upstream_key_id,method,path,model,status,latency_ms,stream,prompt_tokens,completion_tokens | stream(bool) | 只读追加；ID 引用密钥 |
| UsageAggregate | 聚合根（台账） | Admin 域入口 | bucket,bucket_type,dimension_type,dimension_value,requests,errors,rate_limited,prompt_tokens,completion_tokens | bucket_type,dimension_type | 由 RequestLog 聚合 |
| RelayConfig | 值对象/过程数据 | 只读展示 | upstream,connect_timeout,read_timeout,auth_mode | auth_mode | env 来源，P2 |
| RelayRequest | 过程数据 | 不持久化 | method,path,body,headers | — |  transient，遥测落 RequestLog |

## 子流程 I/O 契约

无（本系统无审批/多轮子流程）。

## 关联领域对象（边界说明）

| 关联领域对象 | 所属业务域 | 关联字段 | 需获取信息 | 触发关系 | 映射模式 |
|------------|--------|---------|----------|---------|---------|
| ClientKey | Admin | RequestLog.client_key_id | 名称（展示） | 请求完成写日志 | 同域 ID 引用 |
| UpstreamKey | Admin | RequestLog.upstream_key_id | 标签（展示） | 请求完成写日志 | 同域 ID 引用 |
| UpstreamKey/ClientKey | Admin | Relay 读取启用密钥 | secret/enabled | 每次中转 | ACL（Relay 经仓储接口读，不持有 Admin 模型） |

## 过程数据分类表

| 数据项 | 类别 | 处理方式 |
|--------|------|---------|
| 查询筛选/分页参数 | P1 | 接口入参，不持久化 |
| 密钥脱敏展示值/状态名称 | P2 | 前端派生 |
| operList/按钮可见性 | P2 | 状态+权限计算 |
| 分页包装/下拉选项 | P4 | 传输载体 |
| RelayRequest 请求体 | P7 | 透传，不持久化（只读检视 model/usage） |

## 跨域集成

- Relay → Admin：ACL + OHS（经仓储接口读启用密钥；写 RequestLog）
- Admin → 前端：OHS（REST /api/v1/admin/*）
- Relay → NIM：ACL（透传防腐，OpenAI 兼容协议=遵奉者）
- 存储：Platform 仓储适配（SQLite/D1 共用迁移 SQL）

## 库表映射（D3 DDL 输入，表前缀 np_）

| 聚合根 | 表 | 主键 | 标准字段 |
|--------|-----|------|---------|
| UpstreamKey | np_upstream_key | id TEXT(32) | created_at, updated_at |
| ClientKey | np_client_key | id TEXT(32) | created_at, updated_at, revoked_at(软删除) |
| RequestLog | np_request_log | id TEXT(32) | ts（追加，无更新） |
| UsageAggregate | np_usage_aggregate | id TEXT(32) | bucket+dimension 唯一约束 |
