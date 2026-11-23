# 部署与 CI/CD

远端仓库：`https://github.com/xyztony999/nim-proxy`（私有）。

## 流水线（.github/workflows/）

| 工作流 | 触发 | 作用 |
|--------|------|------|
| `ci.yml` | push main / PR | 后端 ruff+compile+pytest(coverage)；前端 typecheck+lint+build |
| `deploy-workers.yml` | push main（app/workers/web/pyproject/wrangler 变更）/ 手动 | pywrangler sync → 构建前端 → 拷 app 进 workers/app → D1 迁移 → wrangler deploy |
| `deploy-server.yml` | push main（同上）/ 手动 | 构建前端 → scp 到 VPS → 远端 `sudo bash deploy.sh` |

## 所需 Repository Secrets

GitHub → Settings → Secrets and variables → Actions：

**Workers（deploy-workers.yml）**
- `CLOUDFLARE_API_TOKEN`：API Token，需 Workers Scripts Edit + D1 Edit（「Edit Cloudflare Workers」模板 + 手动补 D1）
- `CLOUDFLARE_ACCOUNT_ID`：`ab0d5c99221819d5d58a670af6ac5876`

**服务器（deploy-server.yml）**
- `SERVER_HOST`：VPS IP/域名
- `SERVER_USER`：SSH 用户（需免密 sudo）
- `SSH_PRIVATE_KEY`：服务器上授权的私钥
- `SERVER_PORT`：SSH 端口（可选，默认 22）

用 gh 设置示例：
```bash
gh secret set CLOUDFLARE_API_TOKEN --body "<token>"
gh secret set CLOUDFLARE_ACCOUNT_ID --body "ab0d5c99221819d5d58a670af6ac5876"
gh secret set SERVER_HOST --body "<vps-ip>"
gh secret set SERVER_USER --body "root"
gh secret set SSH_PRIVATE_KEY < ~/.ssh/id_ed25519
```
第二台 VPS：复制 `deploy-server.yml` 改用另一组 secret（或 GitHub Environment）。

## 一次性设置

**Workers**
1. 生产 D1 已创建：`nim-proxy`（id `f5d90c2c-fa8e-4fc9-95bf-f5633b2ece88`，已写入 wrangler.jsonc）。schema 由 CI `wrangler d1 migrations apply` 管理（D1 运行时不执行多行 DDL）。
2. **首次初始化走界面向导**：打开 `https://nim-proxy.tonyxyz.com/admin/`，未配置时自动进入欢迎向导——填 NVIDIA 密钥（向 NIM 验证所有权）→ 设管理员密码（哈希存 D1）→ 可选签发客户端密钥。完成后设置入口永久锁定，**无需再 `wrangler secret put`**。
   - 仍可选手动设 `wrangler secret put ADMIN_TOKEN`（设后向导跳过，直接用该令牌登录）。
3. 自定义域名 `nim-proxy.tonyxyz.com`：首次 deploy 自动创建关联；确认 tonyxyz.com 区已托管在 Cloudflare。
4. 前端静态：CI 构建后把产物布局成 `web/dist/admin/`，wrangler assets 以 `/admin` 前缀托管，`/api/* /v1/* /health` 走 Worker。

**服务器**
1. 首次 `bash deploy.sh` 生成 `/opt/nim-proxy/.env`（含 NVIDIA_API_KEYS / PROXY_API_KEYS / ADMIN_TOKEN / PORT）；后续部署保留已有 .env。
2. systemd 服务 `nim-proxy`，入口 `uvicorn app.main:app`；管理台 `/admin/`。
3. 可选 nginx + certbot HTTPS（见 nginx-nim-proxy.conf，SSE 需 `proxy_buffering off`）。

## 手动部署（不走 CI）

```bash
# 服务器
bash deploy.sh

# Workers（WSL 内，需 uv + wrangler + API Token）
mv requirements.txt /tmp/req.txt && uvx --from workers-py pywrangler sync && mv /tmp/req.txt requirements.txt
(cd web && npm ci && npm run build && cd dist && mkdir -p admin && cp -r assets admin/ && cp index.html admin/)
cp -r app workers/app
wrangler d1 migrations apply nim-proxy --remote
wrangler deploy
rm -rf workers/app
```

## 注意

- Workers 免费版 CPU 10ms/请求不足以跑 Python 冷启动，需 Workers Paid（$5/月）。
- `workers.dev` 域名国内不可达，生产用自定义域名。
- NIM 推理模型首 token 20–30s 属上游行为，非平台问题。
