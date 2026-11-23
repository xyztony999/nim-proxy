# 贡献指南

欢迎 Issue 与 Pull Request！

## 开发环境

```bash
# 后端
pip install -r requirements.txt -r requirements-dev.txt
# 前端
cd web && npm ci
```

## 提交前请确保全部通过

```bash
# 后端
ruff check app workers tests
python -m compileall -q app workers tests
python -m pytest --cov=app

# 前端
cd web
npm run typecheck
npm run lint
npm run build
```

CI（`.github/workflows/ci.yml`）会在 push / PR 时自动跑这些检查。

## 约定

- 后端业务层（`app/services`、`app/schemas`）保持**平台无关**；平台差异放 `app/adapters` 与 `workers/`。
- 新增接口需补 pytest 全链路测试（save→list→detail→update→delete）。
- 密钥/口令不得硬编码；日志与响应中的密钥须脱敏。
- 数据库变更走迁移文件（`app/repositories/migrations` 与 `workers/migrations` 同步）。
- 提交信息建议用 `feat/fix/docs/ci/refactor/test` 前缀。

## 设计产物

`profiles/nim-proxy/workspace/` 下有架构、PRD、API、交互设计与门控报告，改动设计时请参考并同步更新。
