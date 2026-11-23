# backend-04 — 合规验证清单（后端）

> **层级**：L2 技术栈 profile skills。与 `rules/backend-rules.md` §8 对应；编排 agent T07 / Gate 2 扫描以此为清单。
> 执行方式：先跑 grep 快扫，命中项人工核对上下文；全部通过才算合规。`{module}` = 应用包名，命令在 `{BACKEND_ROOT}` 下执行。

## CRITICAL（一项不合规即 FAIL）

- [ ] **C1 无 shell 拼接**：`grep -rnE "shell\s*=\s*True|os\.system\(|os\.popen\(" --include="*.py" {module}` 0 命中；逐个核对 `subprocess.run/Popen/call/check_output` 调用均为参数数组，用户输入未进入 shell 字符串
- [ ] **C2 无 SQL 拼接**：`grep -rnE "execute\(\s*f[\"']" --include="*.py" {module}` 0 命中；`grep -rnE "(SELECT|INSERT|UPDATE|DELETE)[^\"']*(\+|%[sd]|\{\})" --include="*.py" {module}` 0 命中；repositories 层抽查参数化 `?` 占位，动态标识符走白名单
- [ ] **C3 无硬编码凭据**：`grep -rnEi "(password|passwd|secret|token|api_?key)\s*=\s*[\"'][^\"'\{\}]{8,}[\"']" --include="*.py" {module}` 0 命中
- [ ] **C4 SQL 只在 repositories 层**：`grep -rliE "insert into|select .* from|update .* set|delete from" --include="*.py" {module} | grep -v "repositories/"` 0 命中
- [ ] **C5 无异常吞噬**：`grep -rnE "except\s*:" --include="*.py" {module}` 0 命中；`grep -rnE -A2 "except\s+(Exception|BaseException)" --include="*.py" {module}` 命中处逐个核对（无 `pass` 吞异常；有意忽略须有日志与理由注释）
- [ ] **C6 async 无阻塞调用**：`grep -rnE "requests\.|urllib\.request|time\.sleep\(|sqlite3\.connect|\bopen\(" --include="*.py" {module}/api {module}/services` 命中处逐个核对，均已下沉线程池
- [ ] **C7 输入服务端校验**：逐个端点核对——请求体为 Pydantic 模型并带约束；路径/查询参数类型化；透传型端点有"原样透传、不解析"注释
- [ ] **C8 受保护路由有鉴权依赖**：`grep -rn "APIRouter(" --include="*.py" {module}/api` 逐个核对；未受保护的端点有"公开端点"注释及理由
- [ ] **C9 密钥脱敏**：`grep -rnE "log(ger)?\.(info|debug|warning|error|exception)\(.*(key|token|secret)" --include="*.py" {module}` 命中处逐个核对已脱敏；响应模型无明文密钥字段
- [ ] **C10 业务代码不读裸环境变量**：`grep -rnE "os\.getenv|os\.environ" --include="*.py" {module} | grep -v "core/config.py"` 0 命中
- [ ] **C11 编译与测试全绿**：`python -m compileall -q {module}` 与 `python -m pytest` 均通过（实际运行后才可勾选）
- [ ] **C12 业务代码平台无关（双目标）**：`grep -rnE "^(from|import) (workers|js|pyodide|httpx)" --include="*.py" {module}/services` 0 命中；出站 HTTP 经注入的 HttpClient；Workers 入口（entry）只做装配，lifespan 无跨请求资源

## WARNING（需说明理由或修复）

- [ ] W1 非测试、非 CLI 入口代码无 `print(` 调试输出
- [ ] W2 公开函数/方法有类型注解；对外模型字段无裸 `Any`
- [ ] W3 `ruff check {module} tests` 通过（未安装 ruff 时在报告说明）
- [ ] W4 日志统一 `logging`；`basicConfig` 仅出现在入口模块
- [ ] W5 时间字段 UTC aware、ISO 8601 传输；无 naive datetime
- [ ] W6 跨重启状态落 SQLite；模块级可变全局有"单进程内存态"注释
- [ ] W7 后台任务由 lifespan 持有并在 shutdown 取消
- [ ] W8 公开模块/类/函数有 docstring

## 记录格式

```
扫描时间：{ts}
CRITICAL：C1 ✅ / C2 ✅ / ... （不合规项附文件:行号与修复建议）
WARNING：W1 ✅ / ... （豁免项附理由）
结论：PASS / FAIL
```
