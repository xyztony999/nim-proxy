# backend-01 — 分层架构（Python / FastAPI）

> **层级**：L2 技术栈 profile skills。配套规则：`rules/backend-rules.md` §3。📎 代码为通用示例。

## 1. 工程布局

```
{BACKEND_ROOT}/
├─ {module}/                      # 应用包（默认 app）
│  ├─ main.py                # 唯一入口：create_app()、lifespan、中间件、路由注册；暴露 app
│  ├─ core/                  # config.py（配置加载）/ security.py（鉴权、脱敏）/ logging.py
│  ├─ api/                   # 传输层：APIRouter 端点（薄壳）+ deps.py + errors.py
│  ├─ schemas/               # Pydantic 模型：请求 Ao / 响应 Vo / 枚举（StrEnum）
│  ├─ services/              # 业务逻辑层（不感知 HTTP；errors.py 定义领域异常）
│  ├─ repositories/          # 数据访问层（SQL 只在此层）
│  │  └─ migrations/         # DDL 递增编号 + 版本表
│  └─ models/                # 领域对象（dataclass / Pydantic；按需建立）
├─ static/                   # 静态资源（可选；由应用挂载）
├─ tests/                    # 与 {module}/ 镜像；conftest.py 提供公共夹具
├─ requirements.txt          # 运行依赖
└─ requirements-dev.txt      # 开发依赖（pytest 等）
```

**依赖方向**（单向，禁止反向）：

```
main.py → api → services → repositories / models
                     └──────────→ core
```

- 端点**薄壳**：解析输入 → 调 service → 返回 Vo；不写业务逻辑
- service 返回数据或抛领域异常；**禁止** import `fastapi` / `starlette`，**禁止**出现 HTTP 概念（状态码、请求对象）
- repository 以类提供、构造注入到 service；测试用临时 SQLite，不 mock 数据库
- 配置经 `core.config` 提供并以 `Depends` 分发；业务代码不读裸环境变量

## 2. 错误处理

```python
# services/errors.py：领域异常集中定义
class DomainError(Exception):
    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, message: str, *, details: list[dict] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []

class NotFound(DomainError):
    status_code = 404
    code = "not_found"

class Conflict(DomainError):
    status_code = 409
    code = "conflict"

class InvalidInput(DomainError):
    status_code = 422
    code = "invalid_input"

# service：转换异常语义，保留异常链
def load_items(repo: ItemRepository) -> list[Item]:          # 📎
    try:
        return repo.list_enabled()
    except sqlite3.Error as e:
        raise DomainError("数据读取失败", details=[]) from e  # 不外泄内部细节
```

```python
# api/errors.py：统一映射为错误体（结构见 backend-02 §4）
def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def on_domain(request: Request, exc: DomainError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(Exception)
    async def on_unknown(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error: %s %s", request.method, request.url.path)
        return error_response(500, "internal_error", "服务器内部错误")
```

- 🔴 `raise ... from e` 保留异常链；按异常**类型**分支，**禁止**匹配错误文本
- 🔴 **禁止** `except: pass`；有意忽略必须记录日志并注释理由
- 🔴 未知异常兜底：日志记全量 traceback，响应只给脱敏信息（不外泄堆栈、SQL、路径）

## 3. lifespan 与依赖注入

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_config()
    app.state.http = httpx.AsyncClient(base_url=cfg.upstream, timeout=cfg.timeout)
    app.state.db = await run_in_threadpool(open_database, cfg.db_path)   # 阻塞打开下沉线程池
    try:
        yield
    finally:                                   # 每个资源都有清理路径
        await app.state.http.aclose()
        await run_in_threadpool(app.state.db.close)

def create_app() -> FastAPI:
    app = FastAPI(title="service", lifespan=lifespan, docs_url=None, redoc_url=None)   # 📎
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(items.router, prefix="/api/v1/items")                        # 📎
    return app

app = create_app()
```

- 资源在 lifespan 中创建、由 `app.state` 持有、经 `Depends` 分发；🟡 **禁止**在模块导入期建立连接或读取外部状态
- **路由按注册顺序匹配**：具体路由先注册，透传/通配路由（`/{path:path}`）最后注册，并排除应用自身的保留前缀（backend-03 §3）
- 运行：`uvicorn {module}.main:app --host 0.0.0.0 --port {port} --workers 1`

## 4. 单 worker 约束

- 默认 `--workers 1` 部署：进程内可变全局只能承载**可丢失的内存态**（计数器、游标、节流缓冲），并在定义处注释"单进程内存态，重启丢失"
- 必须跨重启保留的状态**一律落 SQLite**；不得以"反正只有一个进程"为由把业务数据放在内存
- 若将来改为多 worker，内存态方案全部失效——涉及内存态的设计须在设计文档"设计决策"中写明该前提

## 5. 双目标组合根（服务器 + Cloudflare Workers，ADR-009/010）

同一份业务代码，两个部署目标的差异收敛在**组合根与适配层**：

```
{BACKEND_ROOT}/
├─ {module}/
│  ├─ main.py            # 服务器组合根：create_app()；装配 httpx 出站客户端 + sqlite 仓储
│  ├─ core/
│  │  ├─ http_client.py  # HttpClient 接口（服务消费）+ HttpxAdapter（服务器实现）
│  │  └─ db.py           # 仓储接口 + 平台实现选择
│  └─ ...                # api / schemas / services / repositories 平台无关
├─ workers/
│  ├─ entry.py           # Workers 组合根：Default = entrypoint(create_app(worker_bindings))
│  ├─ http_client.py     # WorkersFetchAdapter（workers.fetch 实现，ADR-010）
│  └─ d1_repository.py   # D1 仓储实现（scope["env"].DB）
├─ python_modules/       # pywrangler sync 产物（Workers 依赖，git 忽略）
└─ pyproject.toml        # 双端共享依赖声明（须有 Pyodide wheel）
```

- 服务器：`uvicorn {module}.main:app --workers 1`；Workers：`wrangler deploy`（打包经 WSL 内 `pywrangler sync`）
- 平台判据由组合根显式装配，业务代码不判断运行环境
- Workers 上 lifespan **每请求执行一遍**：lifespan 只做轻量装配与清理，不得建立"进程级"连接池或缓存（每请求即建即弃）
- Workers 上无线程/子进程/本地文件写；`run_in_threadpool` 包装只出现在服务器仓储实现内部
- 出站请求统一经 `HttpClient` 接口：服务器实现 = httpx；Workers 实现 = `workers.fetch`（httpx 的 jsfetch 传输层带请求体 POST 在部分隔离实例上挂起——ADR-010，实测结论）
- 迁移 SQL 一套两用：服务器启动时对 SQLite 文件执行；Workers 用 `wrangler d1 migrations apply`（或启动探针执行）对 D1 执行
