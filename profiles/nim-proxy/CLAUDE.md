# NIM Proxy — 项目知识注入

> 本文件由根 CLAUDE.md「Profile 绑定」节引入。只放最关键的事实与索引，明细在 `knowledge/` 与 `workspace/`。

## 项目一句话

NVIDIA NIM（`integrate.api.nvidia.com`）的 OpenAI 兼容 API 中转服务：`/v1/*` 原样透传，客户端用自定义密钥访问，真实 NIM 密钥只存在服务器上。

## 必读事实

- **技术栈**：Python + FastAPI + uvicorn + httpx；当前无持久化（全部配置来自环境变量，重启生效）；部署 systemd 单 worker，可选 nginx + HTTPS。栈规范见激活栈 `python-fastapi`。
- **核心原则**：请求体与响应体不解析、原样透传；真实上游密钥永不出服务器。
- **部署拓扑**：两台海外 VPS 各跑一个实例，互为备份，实例之间不共享状态。
- **限速现实**：NVIDIA 限速是账户级（免费账户约 40 RPM），同一账户多密钥不提升吞吐。

## 知识索引

@knowledge/business-concepts/index.md
@knowledge/design-decisions/index.md
@knowledge/service-pool/index.md
@knowledge/architecture-choices/index.md

## 工作区

- 状态索引：`workspace/INDEX.md`（流水线断点续跑的唯一事实源，每阶段归档后立即更新）
- 设计产物：`workspace/00-architecture`（架构）、`workspace/01-solution/common-spec`（枚举池 / 选择服务池）、`workspace/02-detailed`（PRD / API / 交互）、`workspace/05-reports`（门控报告）
