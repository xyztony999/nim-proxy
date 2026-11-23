# backend-03 — 常用模式（Python / FastAPI）

> **层级**：L2 技术栈 profile skills。📎 示例为通用参考，可按项目替换命名。

## 1. 配置加载（fail-fast）

```python
# core/config.py
import os
from collections.abc import Mapping
from functools import lru_cache
from pydantic import BaseModel, Field

class Config(BaseModel):
    model_config = {"frozen": True}            # 启动期一次加载，运行期只读

    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    upstream: str                              # 无默认值：缺失即报错
    db_path: str = "data/app.db"
    read_timeout: float = Field(default=600, gt=0)

def load_config(env: Mapping[str, str] | None = None) -> Config:
    """环境变量名 = 字段名大写（UPSTREAM / DB_PATH ...）；类型转换与约束校验由 Pydantic 完成。"""
    env = os.environ if env is None else env
    raw = {name: env[name.upper()] for name in Config.model_fields if name.upper() in env}
    return Config.model_validate(raw)

@lru_cache(maxsize=1)
def get_config() -> Config:
    return load_config()
```

- 启动期校验，非法即退出；🔴 **禁止**业务代码运行期读裸环境变量（统一走 `Depends(get_config)`）
- 环境变量名与字段名不一致时用 `Field(validation_alias="SERVICE_UPSTREAM")` 显式映射
- 逗号分隔的多值配置（密钥池等）声明为 `str`，用 `field_validator(mode="before")` 拆分去空，得到 `list[str]`
- 测试中改动环境后调用 `get_config.cache_clear()`

## 2. SQLite 访问与迁移

| 设计文档类型 | SQLite | Python |
|-------------|--------|--------|
| 主键 / ID | TEXT | str |
| 短文本 / 长文本 | TEXT | str |
| 整数 | INTEGER | int |
| 布尔 | INTEGER (0/1) | bool |
| 时间 | TEXT（ISO 8601 UTC） | datetime / str |
| JSON 结构 | TEXT（序列化） | dict / list |

```python
# repositories/db.py
import sqlite3

def open_database(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
```

```python
# repositories/item_repository.py
class ItemRepository:                                                   # 📎
    def __init__(self, conn: sqlite3.Connection, lock: threading.Lock) -> None:
        self._conn = conn
        self._lock = lock

    def list_enabled(self) -> list[sqlite3.Row]:
        with self._lock:                                                # 连接共享，串行访问
            return self._conn.execute(
                "SELECT id, name FROM items WHERE enabled = ? ORDER BY name", (1,)
            ).fetchall()
```

- 连接在 lifespan 中打开（经 `run_in_threadpool`）；`async` 端点调用 repository 一律 `await run_in_threadpool(repo.list_enabled)`
- 迁移：`repositories/migrations/NNN_name.sql` 递增编号 + `schema_migrations` 版本表，启动时按序执行未应用的迁移；已应用的迁移不得修改

```python
def migrate(conn: sqlite3.Connection, migrations_dir: Path) -> list[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = {row["name"] for row in conn.execute("SELECT name FROM schema_migrations")}
    done = []
    for script in sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.sql")):
        if script.name in applied:
            continue
        conn.executescript(script.read_text(encoding="utf-8"))         # 脚本内用 BEGIN; ... COMMIT; 包裹
        conn.execute(
            "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
            (script.name, utc_now()),
        )
        done.append(script.name)
    return done
```

- 🔴 **禁止** f-string / `str.format` / `%` 拼 SQL；标识符（表名/列名/排序字段）动态化必须白名单映射：

```python
SORTABLE = {"created_at": "created_at", "name": "name"}                # 📎 白名单
column = SORTABLE.get(page.sort_by, "created_at")
direction = "DESC" if page.sort_order == "desc" else "ASC"            # 不直接拼接用户输入
sql = f"SELECT id, name FROM items ORDER BY {column} {direction} LIMIT ? OFFSET ?"   # 标识符来自白名单，值走参数
rows = conn.execute(sql, (page.page_size, offset)).fetchall()
```

## 3. 透传与流式响应

```python
req = client.build_request(request.method, url, headers=req_headers, content=body)
resp = await client.send(req, stream=True)

if "text/event-stream" in resp.headers.get("content-type", ""):
    return StreamingResponse(
        resp.aiter_raw(),
        status_code=resp.status_code,
        headers=resp_headers,
        background=BackgroundTask(resp.aclose),       # 流结束必须关闭上游响应
    )

content = await resp.aread()
await resp.aclose()
return Response(content=content, status_code=resp.status_code, headers=resp_headers)
```

- 透传请求**不解析请求体**；转发前剔除 hop-by-hop 头（host / content-length / connection / transfer-encoding 等）
- 重试（换密钥/换节点）只允许发生在**尚未向客户端写出任何字节**之前
- 透传/通配路由最后注册，并在入口处断言路径不属于保留前缀（API、管理页、健康检查、静态资源）

## 4. 鉴权依赖

```python
# core/security.py
from secrets import compare_digest

def mask_secret(value: str, keep: int = 4) -> str:
    return "****" + value[-keep:] if len(value) > keep else "****"

def bearer_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    return auth[7:].strip() if auth.lower().startswith("bearer ") else None
```

```python
# api/deps.py
def require_admin(
    token: str | None = Depends(bearer_token),
    cfg: Config = Depends(get_config),
) -> None:
    if not token or not any(compare_digest(token, t) for t in cfg.admin_tokens):
        raise Unauthorized("无效的管理令牌")
```

- 受保护路由：`router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(require_admin)])`
- 401（未认证）与 403（无权限）严格区分；凭据比较恒定时间

## 5. 密钥脱敏

- 响应与日志中出现的密钥一律 `mask_secret()`（仅保留末 4 位）；完整值只在鉴权与转发时使用
- 新建密钥的接口：完整值**仅在创建响应中返回一次**，之后只能读脱敏值

## 6. 后台任务

- 周期任务（聚合/刷盘）：`asyncio.create_task` 在 lifespan 中创建并由其持有，shutdown 时取消并收尾

```python
flusher = asyncio.create_task(flush_loop(app.state))
try:
    yield
finally:
    flusher.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await flusher
```

- 高频事件（请求日志/计数）先写内存缓冲，按周期批量落库（节流）；shutdown 时刷盘
- 防并发重入：任务体内用 `asyncio.Lock` 或"单实例 + 周期"设计

## 7. 测试模板

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    get_config.cache_clear()
    from app.main import create_app                 # 📎 {module}.main
    with TestClient(create_app()) as c:             # 触发 lifespan；退出时清理资源
        yield c
    get_config.cache_clear()
```

- API 测试用 `TestClient`（同步驱动 ASGI 应用，无需额外插件）；上游调用用 `httpx.MockTransport`，经 `app.dependency_overrides[<http 客户端依赖>] = ...` 注入
- service 测试直接构造，repository 用临时 SQLite（不 mock 数据库）；用 `@pytest.mark.parametrize` 组织用例
- 全链路用例（规则 GR-03）：save → list → detail → update → delete；**错误路径必须有用例**

```python
def test_item_full_chain(client):
    created = client.post("/api/v1/items", json={"name": "a"})          # 📎
    assert created.status_code == 201
    item_id = created.json()["id"]

    assert client.get("/api/v1/items").json()["total"] == 1
    assert client.get(f"/api/v1/items/{item_id}").json()["name"] == "a"

    updated = client.patch(f"/api/v1/items/{item_id}", json={"name": "b"})
    assert updated.status_code == 200 and updated.json()["name"] == "b"

    assert client.delete(f"/api/v1/items/{item_id}").status_code == 204
    assert client.get(f"/api/v1/items/{item_id}").status_code == 404     # 错误路径
```

- 覆盖率目标：service 层 ≥80%、api 层 ≥60%；测试不依赖网络

## 8. 双目标运行时模式（服务器 + Cloudflare Workers）

### 8.1 平台 env 注入（组合根装配，业务代码不感知来源）

```python
# Workers 组合根：bindings/secrets 经 scope["env"] 进入应用
from workers.asgi import entrypoint
from app.main import create_app
from workers_runtime.d1_repository import D1RelayRepository      # 📎 workers/ 平台目录
from workers_runtime.http_client import WorkersFetchAdapter

def asgi_app(scope, receive, send):
    ...  # 见 entry.py：app 通过 middleware/依赖把 scope["env"] 的 DB 与密钥注入容器

Default = entrypoint(create_app(platform="workers"))
```

```python
# core/env.py：统一变量读取（服务器=os.environ；Workers=scope env 对象）
def env_get(env, name: str, default=None): ...
def env_binding(env, name: str): ...   # 对象绑定（D1）保持原始代理
```

### 8.2 出站 HTTP 适配器（ADR-010：Workers 上禁用 httpx）

```python
# core/http_client.py
class HttpClient(Protocol):
    async def request(self, method: str, url: str, *, headers: dict, content: bytes) -> HttpClientResponse: ...

# workers_runtime/http_client.py：workers.fetch 实现（实测 POST/SSE 稳定）
from workers import fetch as cf_fetch

class WorkersFetchAdapter:
    async def request(self, method, url, *, headers, content):
        return await cf_fetch(url, method=method, headers=headers, body=content)

# 服务器实现：httpx.AsyncClient（连接/读超时可配，流式读 aiter_raw）
```

- 🔴 services 通过注入的 `HttpClient` 发起出站请求，禁止直接 import httpx / workers
- 流式响应接口：`stream()` 返回逐块字节迭代器（httpx 用 `aiter_raw`；Workers 用 `resp.body.getReader()` 循环 `read()`，`chunk.value.to_bytes()`）

### 8.3 D1 仓储实现（与 SQLite 实现共用接口与迁移 SQL）

```python
class D1RelayRepository:
    def __init__(self, db) -> None:          # db = scope["env"].DB
        self._db = db

    async def count_events(self) -> int:
        row = to_py(await self._db.prepare(
            "SELECT COUNT(*) AS n FROM relay_events"
        ).first())
        return row.get("n", 0)
```

- 方法全部 `async`；服务器实现内部用 `run_in_threadpool` 包装同步 sqlite3，Workers 实现天然异步
- 迁移：服务器走启动期迁移函数；Workers 用 `wrangler d1 migrations apply <name> --remote`（SQL 文件两目标共享）

### 8.4 Workers 部署门禁（WSL 内执行）

```bash
# 依赖打包（Windows 原生会失败——Pyodide 解释器无法在 Windows 上被 uv 查询）
uvx --from workers-py pywrangler sync        # 需 uv ≥ 支持 pyodide 的版本；在 WSL 内跑
# 部署（API Token：CLOUDFLARE_API_TOKEN；OAuth 回调端口在本机不可用）
wrangler deploy
# 排障：wrangler tail 走 workers.dev（国内不可达）——用仪表盘 Observability
```
