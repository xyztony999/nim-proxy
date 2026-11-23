# Go/No-Go 验证报告 — NIM 中转服务上 Cloudflare Workers（Python）

| 属性 | 值 |
|------|-----|
| 日期 | 2026-11-23 |
| 结论 | **GO** —— 双目标（自建服务器 + Cloudflare Workers）可行，一套 Python |
| 验证方式 | spike Worker 实机部署实测（nim-proxy-spike） |
| 生产探针地址 | https://spike.tonyxyz.com（spike.tonyxyz.com 自定义域名，验证期保留） |
| 代码 | spikes/cf-workers/（已入 git） |

## 1. 结论矩阵

| 验证项 | 判定 | 证据 |
|--------|------|------|
| NVIDIA NIM 出口接受 Workers IP | ✅ GO | GET /v1/models：200、33 个模型、Worker 内 25–107 ms；伪密钥 POST 403 仅 101 ms |
| SSE 流式中转（核心链路） | ✅ GO | workers.fetch + ReadableStream reader：60 个 `data:` 块、15 KB 逐块送达；中文提问/回答字节级正确（UTF-8） |
| 非流式中转 | ✅ GO | 完整 JSON completion，模型理解中文（回答"蓝色"） |
| D1 从 Python 直接读写 | ✅ GO | `request.scope["env"].DB.prepare/bind/run`：建表、插入、COUNT 查询全通（绑定类型 workers.rpc._BindingWrapper） |
| 请求体桥接（1 MB） | ✅ GO | ASGI 适配层完整缓冲 1 MB 并回传 |
| 鉴权守卫 | ✅ GO | 无令牌 401；恒定时间比较 |
| CPU 预算 | ⚠️ 有条件 | 探针全部未触顶；但冷启动 ~3.7–4 s，**Workers 付费版（$5/月）是前提**（免费版 10 ms CPU/请求不可能覆盖 Python 冷启动） |
| workers.dev 域名 | ❌ 不可用 | DNS 污染 + SNI 阻断（本机与 WSL 均不可达）→ 必须自定义域名（spike.tonyxyz.com 已验证可行） |

## 2. 过程中的关键发现（进入栈规则）

| # | 发现 | 应对（已验证） |
|---|------|---------------|
| F-1 | httpx 的 jsfetch 传输层（Cloudflare 补丁版）**带请求体的 POST 在部分隔离实例上挂起**（连接超时假象；GET 永远正常，同实例先 GET 后 POST 不受影响与否不稳定） | 中转出口在 Workers 上**统一改用 `workers.fetch`**（SDK 官方封装，基于 pyfetch）；实测 POST/SSE 均稳定 |
| F-2 | ASGI lifespan 在 Workers 上**每个请求执行一遍**（启动+关闭），非进程级一次 | lifespan 只做轻量装配；常驻连接/缓存不放 lifespan（跨请求无意义） |
| F-3 | ASGI 适配层把整个请求体缓冲后才进应用（内存 128 MB/实例） | 大体量多模态请求的理论上限 ~百 MB 级；设计上接受、报告里注明 |
| F-4 | 绑定（D1/密钥）经 `request.scope["env"]` 进入 FastAPI，可依赖注入 | 新增 `env` 依赖模式；D1 用 prepare/bind/run 风格 |
| F-5 | 部署报告的 Worker Startup Time 3.7–4 s（快照加载） | 冷启动计入付费版 CPU；免费版不可行 |
| F-6 | minimax-m3.1（推理模型）在 NIM 免费账户上：有效密钥 POST 响应头 19–31 s（推理完成后才开始吐 SSE），72 s 首跑为新隔离实例叠加 | 属上游行为（伪密钥 101 ms 证明平台无关）；设计 KPI 不把首 token 延迟记在代理头上，客户端要能接受推理模型的等待 |
| F-7 | wrangler OAuth 回调端口 8976 在本机不可绑定（Hyper-V 保留段）+ WSL NAT localhost 转发不生效 → 本机 OAuth 不可用 | 改用 API Token（CLOUDFLARE_API_TOKEN 环境变量，存于 WSL ~/.cloudflare-token，600 权限）；「Edit Cloudflare Workers」模板需**手动补 D1 Edit 权限** |
| F-8 | pywrangler sync（Pyodide 依赖打包）Windows 原生失败（uv 无法查询 wasm32 解释器） | 打包在 **WSL** 内执行；jsdelivr 主 CDN 被阻断时用本地改写镜像（fastly.jsdelivr.net）+ 本地索引服务。本次实测：pydantic-core 已有 PyPI PyEmscripten wheel，仅 httpx 需 Pyodide 索引 |
| F-9 | wrangler tail 走 workers.dev 域名，本网络不可用 | 日志排障用仪表盘 Observability（部署时已启用）或异常自捕获探针 |
| F-10 | Git Bash(mintty) 无 Windows 控制台 → WSL 内 `/dev/tty` 读输入失败；嵌套引号经 wsl.exe 传递会被剥离 | 交互式输入一律走**脚本文件**（spikes/cf-workers/scripts/），终端只调用脚本 |

## 3. 遗留与限制

- spike Worker / D1 库（nim-proxy-spike）暂保留：管理台落地前它是唯一的 Workers 实机参照；正式版上线后删除。
- `X-Spike-Token` 为临时探针令牌（spikes/cf-workers/spike-token.txt，git 已忽略）。
- 未测：>10 MB 请求体（客户端→Workers 上限 100 MB，内存 128 MB/实例）、WebSocket 透传（NIM 不涉 WS，无需求）。
- 未测：国内访问 spike.tonyxyz.com 的实际延迟/丢包（本机能通；正式版用自有域名 + 可选优选 IP 方案）。

## 4. 产物清单

- `spikes/cf-workers/worker/`：可移植 FastAPI 应用（spike_app.py）+ Workers 入口（entry.py，`workers.asgi.entrypoint`）+ wrangler.jsonc（D1 绑定 + 自定义域名）
- `spikes/cf-workers/scripts/`：WSL 工具链脚本（环境探测/索引镜像/依赖打包/密钥设置）
- 决策记录：knowledge/design-decisions ADR-009/010/011
