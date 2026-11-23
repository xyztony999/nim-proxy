# 业务枚举池

> 本业务域枚举。格式：code + label。
> 接口设计文档引用的枚举必须在本池有定义且无重复（G1-07）。
> `status: draft` 为草稿候选；D3 定稿引用的枚举去标为正式。

| 枚举标识 | code | label | status | 来源 / 备注 |
|----------|------|-------|--------|-------------|
| auth_mode | enforced | 强制鉴权 | 正式 | PROXY_API_KEYS 非空（D3 引用） |
| auth_mode | relay_only | 纯透传 | 正式 | PROXY_API_KEYS 为空（D3 引用） |
| key_status | enabled | 启用 | 正式 | 上游密钥状态（D3 引用） |
| key_status | disabled | 停用 | 正式 | 上游密钥状态（D3 引用） |
| client_key_status | enabled | 启用 | 正式 | 客户端密钥状态（D3 引用） |
| client_key_status | disabled | 停用 | 正式 | 客户端密钥状态（D3 引用） |
| client_key_status | revoked | 已撤销 | 正式 | 终态，软删除（D3 引用） |
| stream_mode | stream | 流式 | 正式 | text/event-stream（D3 引用） |
| stream_mode | non_stream | 非流式 | 正式 | 整体缓冲回传（D3 引用） |
| bucket_type | hour | 小时 | 正式 | 用量聚合粒度（D3 引用） |
| bucket_type | day | 天 | 正式 | 用量聚合粒度（D3 引用） |
| dimension_type | key | 按密钥 | 正式 | 用量统计维度（D3 引用） |
| dimension_type | model | 按模型 | 正式 | 用量统计维度（D3 引用） |
| dimension_type | status | 按状态码 | 正式 | 用量统计维度（D3 引用） |
