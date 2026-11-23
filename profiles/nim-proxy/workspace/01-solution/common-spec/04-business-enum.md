# 业务枚举池

> 本业务域枚举。格式：code + label。
> 接口设计文档引用的枚举必须在本池有定义且无重复（G1-07）。
> `status: draft` 是 `/profile kb` 生成的草稿候选，D1 / D3 定稿后去标。

| 枚举标识 | code | label | status | 来源 / 备注 |
|----------|------|-------|--------|-------------|
| auth_mode | enforced | 强制鉴权 | draft | `PROXY_API_KEYS` 非空：客户端须出示有效的客户端密钥 |
| auth_mode | relay_only | 纯透传 | draft | `PROXY_API_KEYS` 为空：客户端自己的 Authorization 原样转发上游 |
| response_mode | stream | 流式 | draft | 上游 content-type 为 `text/event-stream` |
| response_mode | non_stream | 非流式 | draft | 整体缓冲后回传 |
