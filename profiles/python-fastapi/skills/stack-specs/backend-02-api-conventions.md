# backend-02 — API 设计规约（api_spec）

> **层级**：L2 技术栈 profile skills。引擎 design skill D3 阶段引用本文件（`{stack.api_spec}`）。
> 所有 REST 端点设计与端点生成（backend-orchestrator T04）以此为唯一约定。📎 示例为通用示例。

## 1. 总则

- **REST 语义 + 真实 HTTP 状态码**：成功响应直接返回数据（不包信封），失败返回统一错误体（§4）
- 透传型接口（原样转发上游）**不适用**本规约的响应结构：请求体与响应体保持上游原样，仅鉴权失败由本服务返回错误体

## 2. 路径与命名

- 资源路径：`/api/v1/{module}/{resource}`；集合 GET/POST，单体 GET/PUT/PATCH/DELETE 按 REST 语义
- 动作类端点（非 CRUD 语义，如 test/rotate/reset）：`POST /api/v1/{module}/{resource}/{id}/{action}`
- 资源名复数、小写连字符（`/api/v1/admin/upstream-keys` 📎）；路径参数与查询参数 snake_case
- **禁止**路径含动词混排 CRUD（`GET /api/v1/getKeyList` ❌）
- 应用自身的端点前缀均为**保留前缀**；存在透传/通配路由时必须显式排除（规则见 `rules/backend-rules.md` §2）

## 3. HTTP 方法与状态码

| 操作 | 方法 | 成功状态 | 响应体 |
|------|------|---------|--------|
| 查询列表 | GET | 200 | 分页结构（§5） |
| 查询详情 | GET | 200 | 资源 Vo |
| 新建 | POST | 201 | 资源 Vo |
| 全量更新 | PUT | 200 | 资源 Vo |
| 部分更新 | PATCH | 200 | 资源 Vo |
| 删除 | DELETE | 204 | 无 |
| 动作 | POST | 200 | 动作结果 |

## 4. 统一错误体

```json
{
  "error": {
    "code": "upstream_key_not_found",
    "message": "上游密钥不存在",
    "details": [{ "field": "id", "reason": "记录不存在" }]
  }
}
```

| 字段 | 说明 |
|------|------|
| code | 机器可读、稳定、snake_case；集中定义在 `services/errors.py`，经 `api/errors.py` 映射，**禁止**在端点内裸写 |
| message | 人读信息；错误时给可操作的提示；不得泄露内部细节 |
| details | 可选；校验错误时为字段级数组 `[{ field, reason }]` |

| 状态码 | 含义 | 典型 code |
|--------|------|----------|
| 400 | 请求错误 | bad_request |
| 401 | 未认证（缺失/无效凭据） | unauthorized |
| 403 | 已认证但无权限 | forbidden |
| 404 | 资源不存在 | not_found |
| 409 | 状态冲突（重复、非法流转） | conflict |
| 422 | 参数校验失败 | validation_error / invalid_input |
| 500 | 内部错误 | internal_error |
| 503 | 依赖不可用（上游不可达） | upstream_unavailable |

- Pydantic 校验错误由全局异常处理器转换为同一错误体（`code = validation_error`，`details` 为字段级明细）
- 错误体与 OpenAI 风格同形（`error.message` / `error.code`），便于复用同一套客户端错误处理

## 5. 分页

- 请求：`pageNum`（1 起，默认 1）/ `pageSize`（默认 20，上限 100）；排序 `sortBy` / `sortOrder`（`asc` | `desc`），`sortBy` 取值必须是服务端白名单
- 响应：

```json
{ "records": [], "total": 0, "pageNum": 1, "pageSize": 20 }
```

- **禁止** `list` / `data` / `items` 等异名列表字段；前端类型以本规约对齐

## 6. 鉴权

- 凭据经 `Authorization: Bearer <token>` 传输
- 受保护路由在 `APIRouter(dependencies=[Depends(<鉴权依赖>)])` 上统一声明；公开端点单独分组并在定义处注释理由
- 管理类接口与业务类接口使用**不同的凭据**，不得混用；权限不足返回 403 而非 404
- 凭据比较使用 `secrets.compare_digest`（恒定时间），**禁止** `==`

## 7. 校验

- 请求体用 Pydantic 模型 + 约束（`Field(min_length, max_length, ge, le, pattern)`、`field_validator`）
- 路径/查询参数类型化并约束（`Path` / `Query` / `Annotated`）
- service 层做语义校验（存在性/状态/权限），错误映射为领域异常
- **不信任前端**：所有输入服务端再校验；路径类参数必须过防逃逸校验后才可触达文件系统

## 8. 时间与枚举

- 时间字段传输 ISO 8601 UTC（`2026-11-23T08:00:00Z` 📎）；SQLite 以 UTC ISO 文本存储；禁止 naive datetime
- 枚举传输 string code，定义在 `schemas/`（`StrEnum`），取值与业务枚举池一致
- 金额不适用本栈默认场景；如有，用整数最小单位或 `Decimal`，**禁止** float

## 9. 模型命名与设计文档对齐

- 请求模型 `XxxAo`（如 `KeySaveAo`、`KeyPageAo` 📎），响应模型 `XxxVo`（如 `KeyDetailVo`、`KeyListVo` 📎），与 D3 文档 / PageSpec 中的 AO/VO 一一对应
- D3 设计文档中每个接口给出：方法、路径、请求/响应 JSON 示例、错误码列表
- 端点生成（backend-orchestrator T04）逐接口对照设计文档，**禁止**自行增删字段

## 10. D3 文档通用章节在本栈的映射

引擎 D3 模板的部分章节面向特定企业栈，本栈按下列口径取用（设计文档中注明"按栈规约"即可）：

| D3 模板条目 | 本栈口径 |
|-------------|---------|
| 接口规范（路径/方法/响应） | 以本文 §1~§5 为准（REST + 状态码 + 错误体），不采用"统一 POST + Result 包装" |
| 主键 | `TEXT` 主键，32 位小写十六进制（`uuid4().hex`）或 ULID；**禁止**自增整数主键 |
| 标准字段 | 主表必含 `id` / `created_at` / `updated_at`；软删除 `deleted_at`（可空）与乐观锁 `version` 按需 |
| 审计字段（created_by 等） | 单管理员场景可省略，省略须在文档注明 |
| 领域事件 / MQ | 默认不引入消息队列：标注"不适用"，或映射为进程内发布订阅 |
| 审批流 / 工作流回调 / 子流程 | 默认不适用（标注 N/A 并说明理由） |
| 错误码格式 | snake_case 字符串（§4），不是 `{BIZ}_{OBJECT}_{ERROR}` 大写格式 |
