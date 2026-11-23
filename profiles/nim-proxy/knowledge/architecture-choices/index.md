<!-- kb-generated: 2026-11-23 | sources: 5 | assumptions: 1 | open: 0 -->

# 架构选择知识库

> 领域划分与技术栈版本。来源见 [source-index.md](../source-index.md)。

## 领域划分

| 领域 | 英文 | 类型 | 职责 | 模块 |
|------|------|------|------|------|
| 中转 | Relay | core | 客户端鉴权、上游密钥轮询、请求透传、流式回传、健康检查 | relay（既有实现，状态见 workspace/INDEX.md） |
| 管理台 | Admin | supporting | 密钥管理、用量统计、运行状态可视化 —— 候选，未立项，范围待 D0 澄清 | admin（未建设） |

应用是单体服务，当前只有中转一个领域，所有代码在单文件 `app.py` 中。

## 技术栈版本

| 组件 | 开发机实测版本 | 声明约束（requirements.txt） | 备注 |
|------|--------------|---------------------------|------|
| Python | 3.12.6 | 未声明 | ⚠️假设：语法基线 3.10+（A4）；服务器安装发行版 python3 |
| FastAPI | 0.163.1 | >=0.111 | |
| uvicorn | 0.54.0 | >=0.30（standard extras） | 单 worker |
| httpx | 0.28.1 | >=0.27 | 上游转发 + 测试客户端 |
| pydantic | 2.14.3 | 随 FastAPI 引入 | |
| starlette | 1.10.0 | 随 FastAPI 引入 | |
| pytest | 9.1.1 | 未列入依赖 | 开发机已装；项目目前没有测试 |
| 部署 | systemd + uvicorn；可选 nginx + certbot | — | 服务器目录 `/opt/nim-proxy`，服务名 `nim-proxy` |
