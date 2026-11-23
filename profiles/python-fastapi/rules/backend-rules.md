# 后端编码规则（本栈：Python / FastAPI）

> **层级**：L2 技术栈 profile。激活含本栈的业务 profile 时由挂载机制生效。
> **分级**：🔴 CRITICAL = 违规即 Gate 2 FAIL，必须修复；🟡 WARNING = 需说明理由或修复。每条附可 grep 的检查方法（Gate 2 等价规则集）。
> **占位符**：`{module}` = 应用包名（栈 manifest `stack.scaffold.params.module`，默认 `app`）；`{BACKEND_ROOT}` = 代码根（BACKEND_ROOT）。grep 命令在 `{BACKEND_ROOT}` 下执行。

---

## 1. 编码规约

| 技术 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 语法基线 3.10（不得使用 3.11+ 专有特性，除非项目声明更高基线） |
| FastAPI | 0.111+ | HTTP 框架，端点薄壳 |
| Pydantic | v2 | 请求/响应模型与配置校验（不使用 v1 模式） |
| httpx | 0.27+ | 异步 HTTP 客户端（上游调用）+ 测试客户端 |
| uvicorn | 0.30+ | ASGI 服务器，默认单 worker |
| sqlite3 | 标准库 | 默认持久化；标准库优先，新增运行依赖需说明理由 |

### 1.1 语言风格

- 🔴 **禁止** `except:` 裸捕获，**禁止** `except Exception: pass` 吞异常 → `grep -rnE "except\s*:" --include="*.py" {module}` 0 命中；`grep -rnE -A2 "except\s+(Exception|BaseException)" --include="*.py" {module}` 命中处逐个核对（至少记录日志；有意忽略必须注释理由）
- 🔴 错误必须带上下文：`raise DomainError(...) from e` 或 `log.exception("...")`；**禁止**静默 `return None` 代替报错
- 🟡 非测试、非 CLI 入口代码**禁止** `print(` 调试输出 → `grep -rn "print(" --include="*.py" {module}`
- 🟡 公开函数、方法、Pydantic 字段必须有类型注解；对外模型字段**禁止**裸 `Any` → `grep -rnE ":\s*Any\b" --include="*.py" {module}/schemas`
- 🟡 公开模块、类、函数有 docstring（一句话说明职责即可）

### 1.2 并发与阻塞

- 🔴 `async def` 端点与 service 中**禁止**直接执行阻塞调用（`requests.*`、`urllib.request`、`time.sleep`、同步 `sqlite3`、同步文件 IO、CPU 密集循环）；必须经 `run_in_threadpool` / `anyio.to_thread.run_sync` 下沉线程池 → `grep -rnE "requests\.|urllib\.request|time\.sleep\(|sqlite3\.connect|\bopen\(" --include="*.py" {module}/api {module}/services` 命中处逐个核对
- 🔴 后台任务必须有退出路径：由 lifespan 创建并持有，shutdown 时取消；**禁止**模块导入期裸起任务（`asyncio.create_task` 出现在 import 时执行的代码中）→ `grep -rn "create_task\|ensure_future" --include="*.py" {module}` 逐个核对归属
- 🟡 共享可变状态须加锁（`threading.Lock` / `asyncio.Lock`）；跨协程共享的 httpx 客户端必须复用 lifespan 中的单例

---

## 2. 安全硬约束（本栈门禁核心）

- 🔴 **禁止 shell 拼接执行**：外部命令一律 `subprocess.run([可执行文件, *参数])` 参数数组；**禁止** `shell=True` / `os.system` / `os.popen`
  → `grep -rnE "shell\s*=\s*True|os\.system\(|os\.popen\(" --include="*.py" {module}` 0 命中；`grep -rnE "subprocess\.(run|Popen|call|check_output)" --include="*.py" {module}` 逐个核对为参数数组
- 🔴 **禁止 SQL 字符串拼接**：一律参数化 `?` 占位；表名/列名/排序字段等标识符动态化必须走白名单映射
  → `grep -rnE "execute\(\s*f[\"']" --include="*.py" {module}` 与 `grep -rnE "(SELECT|INSERT|UPDATE|DELETE)[^\"']*(\+|%[sd]|\{\})" --include="*.py" {module}` 0 命中
- 🔴 **禁止硬编码密钥/口令**：凭据来自环境变量或配置文件，默认值不得含真实凭据
  → `grep -rnEi "(password|passwd|secret|token|api_?key)\s*=\s*[\"'][^\"'\{\}]{8,}[\"']" --include="*.py" {module}` 0 命中
- 🔴 **受保护路由必须声明鉴权依赖**：管理类/受保护端点所在的 `APIRouter` 必须带 `dependencies=[Depends(<鉴权依赖>)]`，或端点签名显式声明；未受保护的端点必须在路由定义处注释说明"公开端点"及理由
  → `grep -rn "APIRouter(" --include="*.py" {module}/api` 逐个核对
- 🔴 **密钥不得明文出现在日志与响应中**：日志、错误信息、接口响应里的密钥一律经脱敏函数处理（仅保留末 4 位）
  → `grep -rnE "log(ger)?\.(info|debug|warning|error|exception)\(.*(key|token|secret)" --include="*.py" {module}` 命中处逐个核对已脱敏
- 🔴 口令/令牌比较使用恒定时间比较（`secrets.compare_digest`），**禁止** `==` 直接比较
- 🔴 文件路径操作必须防逃逸：用户输入路径先 `Path.resolve()` 并校验落在白名单目录内，再读写
- 🔴 所有输入服务端校验（Pydantic 模型 + 约束注解 + service 层语义校验），不信任前端；**禁止**用 `await request.json()` 取未校验的输入（透传型端点除外，须注释说明"原样透传、不解析"）
- 🔴 **通配路由必须排除保留前缀**：存在 `/{path:path}` 类 catch-all 路由时，必须显式排除应用自身端点前缀（API、管理页、健康检查、静态资源），并在透传入口处做前缀断言
- 🟡 监听地址/端口等部署参数由配置注入，业务代码不写死

---

## 3. 目录结构

```
{BACKEND_ROOT}/
├─ {module}/                      # 应用包（默认 app）
│  ├─ main.py                # 入口：create_app()、lifespan、中间件、路由注册；暴露 app
│  ├─ core/                  # 配置加载 / 鉴权与脱敏 / 日志
│  ├─ api/                   # 路由层：APIRouter 端点（薄壳）+ deps.py + errors.py
│  ├─ schemas/               # Pydantic 模型：请求 Ao / 响应 Vo / 枚举
│  ├─ services/              # 业务逻辑（不感知 HTTP）
│  ├─ repositories/          # 数据访问（SQL 只在此层）
│  │  └─ migrations/         # DDL 递增编号 + 版本表
│  └─ models/                # 领域对象（按需）
├─ static/                   # 静态资源（可选）
├─ tests/                    # 与 {module}/ 镜像；conftest.py 提供公共夹具
├─ requirements.txt          # 运行依赖
└─ requirements-dev.txt      # 开发依赖
```

- 分层依赖方向单向：`main → api → services → repositories / models`；`core` 供各层引用；**禁止**反向引用与跨层直连（端点不直接调 repository）
- 🔴 SQL 语句只允许出现在 `repositories/` → `grep -rliE "insert into|select .* from|update .* set|delete from" --include="*.py" {module} | grep -v "repositories/"` 0 命中
- 🟡 `services/` **禁止** import `fastapi` / `starlette` → `grep -rnE "^(from|import) (fastapi|starlette)" --include="*.py" {module}/services` 0 命中

---

## 4. HTTP 约定

- 端点薄壳：解析输入（Pydantic 模型 / 类型化参数）→ 调 service → 返回 Vo；**禁止**在端点写业务逻辑
- 接口规约以 `skills/stack-specs/backend-02-api-conventions.md`（`{stack.api_spec}`）为唯一约定：REST 语义 + 真实 HTTP 状态码 + 统一错误体
- 错误码集中在 `services/errors.py` 定义并经 `api/errors.py` 映射，**禁止**在端点内裸写错误码字符串
- 路由分组挂依赖：鉴权 → 其他横切关注点，顺序固定；公开端点单独分组显式声明
- 🟡 时间字段统一 UTC（aware datetime）存储与传输，ISO 8601 格式；**禁止** naive datetime

---

## 5. 配置与日志

- 配置集中在 `{module}/core/config.py`：启动期从环境变量一次性加载并校验（fail-fast），以依赖注入分发；🔴 **禁止**业务代码运行期读裸 `os.getenv` / `os.environ` → `grep -rnE "os\.getenv|os\.environ" --include="*.py" {module} | grep -v "core/config.py"` 0 命中
- 🔴 日志统一 `logging`（模块级 `log = logging.getLogger(__name__)`）；**禁止** `print` 与 `logging.basicConfig` 散落在业务模块（basicConfig 仅入口处）→ `grep -rn "basicConfig" --include="*.py" {module} | grep -v "main.py"` 0 命中
- 🟡 错误日志必须带请求上下文（路径、方法、请求 id）；日志不得输出敏感字段明文

---

## 6. 数据与并发

- 默认持久化为 SQLite（标准库 `sqlite3`）：连接初始化执行 `PRAGMA journal_mode=WAL` 与 `PRAGMA foreign_keys=ON`
- 🔴 默认**单 worker** 部署：进程内可变全局仅可用于"可丢失的内存态"（计数器、游标），且必须注释"单进程内存态，重启丢失"；**必须跨重启保留的状态一律落 SQLite**
- 🟡 迁移脚本递增编号、启动时按序执行未应用的迁移，已应用的迁移不得修改

---

## 7. 构建与门禁

| 门禁 | 命令 | 说明 |
|------|------|------|
| 编译 | `python -m compileall -q {module}` | Gate 2 必过（`{stack.build.command}`） |
| 静态检查 | `ruff check {module} tests` | 推荐；未安装时在报告中说明，按 WARNING 处理 |
| 测试 | `python -m pytest` | Gate 2 必过；错误路径必须有对应用例 |
| 覆盖率 | `python -m pytest --cov={module}` | service 层 ≥80%、api 层 ≥60%（未装 pytest-cov 时说明） |

- Windows 用 `python`，Linux/macOS 用 `python3`；测试不得依赖网络（外部调用用 `httpx.MockTransport` 或测试夹具替身）
- 测试数据库用临时文件或 `:memory:`，不触碰生产数据文件

---

## 8. Gate 2 扫描清单（CRITICAL 汇总）

| # | 检查 | grep 方法 | 判定 |
|---|------|----------|------|
| C-01 | 无 shell 拼接 | §2「禁止 shell 拼接执行」的 grep 命令 | 0 命中；`subprocess.*` 逐个核对 |
| C-02 | 无 SQL 拼接 | 见 §2；repositories 抽查参数化 | 0 命中 |
| C-03 | 无硬编码凭据 | 见 §2 | 0 命中 |
| C-04 | SQL 只在 repositories 层 | 见 §3 | 0 命中 |
| C-05 | 无异常吞噬 | `grep -rnE "except\s*:" --include="*.py" {module}` | 0 命中；`except Exception` 逐个核对 |
| C-06 | async 无阻塞调用 | 见 §1.2 | 命中处均已下沉线程池 |
| C-07 | 输入服务端校验 | 逐个端点核对模型与约束 | 全部端点有校验 |
| C-08 | 受保护路由有鉴权依赖 | 见 §2 | 全部声明 |
| C-09 | 密钥脱敏 | 见 §2 | 日志/响应无明文 |
| C-10 | 业务代码不读裸环境变量 | 见 §5 | 0 命中 |
| C-11 | 编译 + 测试全绿 | `python -m compileall -q {module} && python -m pytest` | 全绿 |
