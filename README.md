<div align="center">

<img src="assets/logo-256.png" width="120" alt="NIM Proxy logo" />

# NIM Proxy

**NVIDIA NIM 的 OpenAI 兼容 API 中转服务，自带管理台 · 一套代码双目标部署（自建服务器 / Cloudflare Workers）**

[![CI](https://github.com/xyztony999/nim-proxy/actions/workflows/ci.yml/badge.svg)](https://github.com/xyztony999/nim-proxy/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Cloudflare Workers](https://img.shields.io/badge/Cloudflare-Workers-F38020.svg)](https://workers.cloudflare.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://docs.astral.sh/ruff/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

</div>

---

## 简介

NIM Proxy 把 [NVIDIA NIM](https://build.nvidia.com/)（`integrate.api.nvidia.com`）的 OpenAI 兼容接口中转给你自己的客户端：

- 客户端用**你自定义的密钥**访问代理，真实的 `nvapi-` 密钥只存在服务端，绝不外泄。
- `/v1/*` 请求**原样透传**（流式 SSE / 非流式 / 多模态都支持），NIM 升级参数无需改代码。
- 自带 **Web 管理台**：密钥治理、用量统计、请求日志、运行看板，首次启动有**界面向导**引导初始化。
- **一套 Python 代码**同时部署到自建服务器（uvicorn + SQLite）和 Cloudflare Workers（Python Workers + D1）。

任何支持「自定义 OpenAI API 地址」的客户端（LobeChat / NextChat / OpenAI SDK / 自写脚本）都能直接接入。

## 特性

- 🔁 **完全透传**：`/v1/*` 全接口原样转发，流式与非流式、多模态（`image_url`）均支持。
- 🔑 **密钥解耦**：客户端密钥与上游 NIM 密钥分离；上游密钥多把轮询，遇 401/403/429 自动换钥重试。
- 🖥️ **管理台**：运行看板、上游/客户端密钥增删启停、按密钥/模型/状态维度的用量统计、请求日志查询。
- 🧙 **首次启动向导**：纯界面初始化——填 NVIDIA 密钥（向 NIM 验证所有权）→ 设管理员密码 → 可选签发客户端密钥；设完永久锁定。
- 🌗 **暗色 / 亮色主题**：跟随系统，可手动切换并记忆。
- 🚀 **双目标部署**：服务器（systemd + SQLite）与 Cloudflare Workers（D1 + 静态资源），共用迁移 SQL 与业务代码。
- 🤖 **CI/CD**：GitHub Actions 自动测试 + 部署；缺配置时只构建跳过部署，不发失败通知。
- 🔒 **安全**：密码 PBKDF2 哈希、会话令牌 SHA-256 存储、恒定时间比较、密钥脱敏展示。

## 架构

```
                         ┌─────────────────────────────────────────┐
   客户端 (LobeChat 等)   │              NIM Proxy (FastAPI)         │
  ──────────────────────▶│  /v1/*  透传 + 鉴权 + 轮询 + 重试         │──▶ NVIDIA NIM
   Bearer 客户端密钥      │  /admin 管理台 (React SPA)               │   integrate.api.nvidia.com
                         │  /api/v1/admin/*  管理接口 (会话鉴权)     │
                         │  /api/v1/setup/*  首次设置 (公开)         │
                         └───────────────┬─────────────────────────┘
                                         │ 仓储接口（平台无关）
                          ┌──────────────┴──────────────┐
                          ▼                             ▼
                   自建服务器                      Cloudflare Workers
                   uvicorn + SQLite               Python Workers + D1
                   httpx 出站                      workers.fetch 出站
```

业务层（`app/services`、`app/schemas`）平台无关；平台差异收敛在组合根与适配器（`app/adapters`、`workers/`）。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.10+ · FastAPI · Pydantic v2 · httpx（服务器）/ workers.fetch（Workers） |
| 存储 | SQLite（服务器）· Cloudflare D1（Workers），共用迁移 SQL |
| 前端 | React 19 · Vite · TypeScript · MUI v7 · Recharts · react-router v7 |
| 部署 | systemd + uvicorn（服务器）· Cloudflare Workers + 静态资源 · GitHub Actions |
| 质量 | pytest（17 测试，覆盖 89%）· ruff · tsc · ESLint |

## 快速开始

### 方式一：自建服务器

```bash
git clone https://github.com/xyztony999/nim-proxy.git
cd nim-proxy
# 上传到服务器后一键部署（Ubuntu/Debian，root）
NVIDIA_API_KEYS="nvapi-你的密钥" PROXY_API_KEYS="sk-自定义访问密钥" bash deploy.sh
```

部署脚本会安装依赖、生成 `.env`（含管理令牌）、注册 systemd 服务。管理台在 `http://<服务器IP>:8000/admin/`。

### 方式二：Cloudflare Workers

> 需 **Workers Paid**（免费版 10ms CPU 不足以运行 Python）。

```bash
# WSL/Linux 内（需 uv + wrangler + Cloudflare API Token）
mv requirements.txt /tmp/req.txt && uvx --from workers-py pywrangler sync && mv /tmp/req.txt requirements.txt
(cd web && npm ci && npm run build && cd dist && mkdir -p admin && cp -r assets admin/ && cp index.html admin/)
cp -r app workers/app
wrangler d1 migrations apply nim-proxy --remote
wrangler deploy
rm -rf workers/app
```

打开 `https://<你的域名>/admin/`，首次进入会自动走向导。详见 [DEPLOYMENT.md](DEPLOYMENT.md)。

### 接入客户端

| 参数 | 值 |
|------|-----|
| API Base | `http://<服务器IP>:8000/v1` 或 `https://<你的域名>/v1` |
| API Key | 你的客户端密钥（`sk-...`） |
| Model | NIM 上的任意模型，如 `minimaxai/minimax-m3.1-flash` |

```python
from openai import OpenAI
client = OpenAI(base_url="https://<你的域名>/v1", api_key="sk-你的客户端密钥")
stream = client.chat.completions.create(
    model="minimaxai/minimax-m3.1-flash",
    messages=[{"role": "user", "content": "你好"}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

## 项目结构

```
nim-proxy/
├── app/                    # 后端（平台无关业务 + 适配器）
│   ├── api/                #   路由：admin / relay / setup / deps / errors
│   ├── core/               #   配置 / 安全 / 异常 / HTTP 客户端接口
│   ├── schemas/            #   Pydantic Ao/Vo
│   ├── services/           #   keys / telemetry / relay / auth
│   ├── repositories/       #   SQLite 仓储 + 迁移 SQL
│   └── adapters/           #   httpx（服务器）/ workers.fetch / D1（Workers）
├── workers/                # Workers 入口 + D1 迁移
├── web/                    # React 管理台（Vite + TS）
├── tests/                  # pytest（17 测试）
├── .github/workflows/      # CI + Workers 部署 + 服务器部署
├── deploy.sh               # 服务器一键部署
├── wrangler.jsonc          # Workers 配置
└── profiles/               # AI 引擎设计产物（架构/PRD/API/交互/门控报告）
```

## 文档

- 📦 [DEPLOYMENT.md](DEPLOYMENT.md) — 部署指南（服务器 / Workers / CI/CD secrets）
- 🛠️ [OPERATIONS.md](OPERATIONS.md) — 运维手册（日常操作 / 密钥管理 / 排障 / 升级 / 备份）

## 开发

```bash
# 后端
pip install -r requirements.txt -r requirements-dev.txt
ruff check app workers tests
python -m pytest --cov=app

# 前端
cd web && npm ci
npm run typecheck && npm run lint && npm run build
```

## 已知限制

- NVIDIA 限速是**账户级**（免费账户约 40 RPM）；同账户多密钥不提升吞吐，轮换只在多账户间有效（多账户违反 ToS，风险自担）。
- NIM 推理模型首 token 可能需 20–30 秒（上游行为，非代理问题）。
- Workers 需付费版；`workers.dev` 域名在中国大陆不可达，生产请用自定义域名。
- 用量统计的 token 数为「尽力统计」（流式需客户端开启 `include_usage`）。

## 贡献

欢迎 Issue 与 PR！请确保 `ruff check`、`pytest`、前端 `typecheck/lint/build` 全部通过。

## 许可证

[MIT](LICENSE) © 2026 Xinyi Zhang (xyztony999)
