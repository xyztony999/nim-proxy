# PageSpec — admin 管理台（Owner / React + Vite）

| 属性 | 值 |
|------|-----|
| 模块编码 | admin（AA：S-01/S-02/D-01/P-01） |
| 所属 App | nim-proxy-admin（web/ 独立 Vite 工程） |
| 业务类型 | master_data（密钥）+ 台账（日志/统计） |
| 页面类型 | config（标准列表/表单/详情）+ code（用量图表） |
| 前端栈 | react-vite-web（React 19 + Vite + TS + react-router v7 + MUI + Recharts） |
| 版本 | v1.0 / 2026-11-23 |
| API 依据 | workspace/02-detailed/api/api-admin.md |

## 1. 全局约定

- 路由 basename `/admin`；SPA fallback 由后端静态托管（Workers assets / 服务器静态目录）
- 鉴权：ADMIN_TOKEN 存 sessionStorage；fetch 封装统一加 `Authorization: Bearer`；401 → 跳 /admin/login
- 异步三态：每个数据 hook 返回 {data, loading, error}；错误用 MUI Alert 显示 error.message（来自统一错误体）
- 字段命名 snake_case（与后端 VO 一致）；时间 ISO UTC → 本地化显示
- 枚举显示映射见 §3；状态色：enabled=green，disabled=gray，revoked=red，错误状态码≥400=red/orange
- 目录：src/pages/<Feature>/、src/components/、src/hooks/use*.ts、src/api/actions.ts、src/api/client.ts

## 2. 路由定义

| 路由 | 页面组件 | 说明 |
|------|---------|------|
| /admin/login | LoginPage | 令牌登录（无侧栏） |
| /admin | DashboardPage | 看板（默认） |
| /admin/upstream-keys | UpstreamKeysPage | 上游密钥管理 |
| /admin/client-keys | ClientKeysPage | 客户端密钥管理 |
| /admin/usage | UsagePage | 用量统计 |
| /admin/request-logs | RequestLogsPage | 请求日志 |
| /admin/config | ConfigPage | 运行配置（只读） |

布局：AuthedLayout（侧栏导航 + 顶栏）包裹除 login 外页面；未登录守卫重定向 login。

## 3. 字典/枚举显示清单

| 枚举 | 来源 | 显示 |
|------|------|------|
| key_status | enum_pool | enabled→启用(green)/disabled→停用(gray) |
| client_key_status | enum_pool | enabled/disabled/revoked→已撤销(red) |
| auth_mode | enum_pool | enforced→强制鉴权/relay_only→纯透传 |
| bucket_type | enum_pool | hour→小时/day→天 |
| dimension_type | enum_pool | key→按密钥/model→按模型/status→按状态码 |
| stream_mode | enum_pool | stream→流式/non_stream→非流式 |

## 4. Action 定义（src/api/actions.ts，与 D3 接口对齐）

| Action | 方法 | URL | 请求 | 响应 |
|--------|------|-----|------|------|
| getDashboard | GET | /api/v1/admin/dashboard | — | DashboardVo |
| listUpstreamKeys | GET | /api/v1/admin/upstream-keys | — | {records:UpstreamKeyListVo[]} |
| createUpstreamKey | POST | /api/v1/admin/upstream-keys | UpstreamKeySaveAo | DetailVo+secret |
| getUpstreamKey | GET | /api/v1/admin/upstream-keys/{id} | id | DetailVo |
| deleteUpstreamKey | DELETE | /api/v1/admin/upstream-keys/{id} | id | 204 |
| enableUpstreamKey | POST | /api/v1/admin/upstream-keys/{id}/enable | id | DetailVo |
| disableUpstreamKey | POST | /api/v1/admin/upstream-keys/{id}/disable | id | DetailVo |
| listClientKeys | GET | /api/v1/admin/client-keys | — | {records:ClientKeyListVo[]} |
| createClientKey | POST | /api/v1/admin/client-keys | ClientKeySaveAo | DetailVo+secret |
| deleteClientKey | DELETE | /api/v1/admin/client-keys/{id} | id | 204 |
| enableClientKey | POST | /api/v1/admin/client-keys/{id}/enable | id | DetailVo |
| disableClientKey | POST | /api/v1/admin/client-keys/{id}/disable | id | DetailVo |
| getUsage | GET | /api/v1/admin/usage | UsageQueryAo | {records:UsageVo[]} |
| listRequestLogs | GET | /api/v1/admin/request-logs | RequestLogQueryAo | PageVo<RequestLogListVo> |
| getConfig | GET | /api/v1/admin/config | — | ConfigVo |

> URL 不含 /api 前缀重复：client.ts baseURL 设为 origin，actions 写完整 /api/v1/...（react-vite-web 规则：全局 baseURL 自动补 /api 时 actions 不重复加；本工程 baseURL=origin，actions 含 /api/v1）。

## 5. 页面规格

### 5.1 LoginPage（code）
- 字段：token（password input，必填）
- 行为：提交 → 调 getDashboard 验证令牌 → 成功存 sessionStorage 跳 /admin；失败 Alert 显示错误
- 组件：MUI TextField/Button/Alert；无侧栏

### 5.2 DashboardPage（config）
- 数据：getDashboard
- 展示：StatCard×4（服务状态/上游地址/鉴权模式/密钥数）+ 今日计数卡（requests/errors/rate_limited）
- 组件：MUI Card/Grid；loading Skeleton；error Alert
- 字段来源：DashboardVo.{status,upstream,auth_mode,upstream_key_count,client_key_count,today}

### 5.3 UpstreamKeysPage（master_data）
- 查询：无（全量列表）
- 表格列：序号(index,60) → label(text,180) → secret_masked(text) → enabled(dict key_status,colorTag) → last_error_status(text) → consecutive_failures(text) → last_used_at(text,180) → 操作(action,fixed right)
- 工具栏：新增（createUpstreamKey）
- 行操作：启用/停用（enable/disable，按 enabled 互斥显示）、删除（deleteUpstreamKey，确认弹窗）
- 表单（Dialog，<5 字段）：label(input,必填)、secret(password input,必填,nvapi- 前缀校验)；按钮 保存/取消
- 创建成功：弹窗展示完整 secret 一次（提示「仅显示一次」）
- 字段来源：UpstreamKeyListVo / UpstreamKeySaveAo

### 5.4 ClientKeysPage（master_data）
- 表格列：序号 → name(text,180) → secret_masked → enabled(dict client_key_status,colorTag) → last_used_at(180) → revoked_at(180) → 操作
- 工具栏：新增（createClientKey）
- 行操作：启用/停用（revoked 行禁用）、撤销（deleteClientKey，确认）
- 表单（Dialog）：name(input,必填)；secret 服务端生成；按钮 保存/取消
- 创建成功：展示完整 secret 一次
- 字段来源：ClientKeyListVo / ClientKeySaveAo

### 5.5 UsagePage（code）
- 查询条件：dimensionType(select dimension_type,默认 key)、bucketType(select bucket_type,默认 day)、start/end(dateRange)
- 数据：getUsage
- 展示：Recharts 柱状/折线（requests/errors/tokens 随 dimension）+ 明细表（bucket,dimension_value,requests,errors,rate_limited,prompt_tokens,completion_tokens）
- 字段来源：UsageQueryAo / UsageVo

### 5.6 RequestLogsPage（台账）
- 查询条件：clientKeyId(select,来自 listClientKeys)、model(input,like)、status(select/input)、start/end(dateRange)、pageNum/pageSize
- 表格列：序号 → ts(180) → client_key_name → upstream_key_label → method → path → model → status(colorTag) → latency_ms → stream(dict stream_mode) → tokens(prompt/completion)
- 分页：MUI TablePagination（pageNum/pageSize/total）
- 字段来源：RequestLogQueryAo / RequestLogListVo / PageVo

### 5.7 ConfigPage（config，只读）
- 数据：getConfig
- 展示：MUI Descriptions/List 只读（upstream,connect_timeout,read_timeout,auth_mode,port,db_backend）
- 无编辑操作

## 6. 全局一致性

- 所有 Action URL 与 api-admin.md 接口路径一致（GR-05/CT-001）
- 列表/表单字段来源于 VO/AO，无臆造字段（CT-005/006）
- 枚举显示与 enum_pool 一致（CT-003/007）
- 异步均有 loading/error 反馈（react-vite-web R3）
- 接口地址/密钥不写死组件，统一 client.ts/actions.ts（R2）

## 7. 更新记录

| 版本 | 日期 | 更新说明 |
|------|------|---------|
| v1.0 | 2026-11-23 | 初始生成（7 页面 + 15 Action，React 映射） |
