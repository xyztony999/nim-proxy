# 部署指南

NIM Proxy 支持两种部署目标，共用一套代码与迁移 SQL：

| 目标 | 运行时 | 存储 | 出站 HTTP | 适用 |
|------|--------|------|-----------|------|
| 自建服务器 | uvicorn + systemd | SQLite 文件 | httpx | 已有 VPS、需要完全掌控 |
| Cloudflare Workers | Python Workers | D1 | workers.fetch | 免运维、全球边缘、按量付费 |

> ⚠️ Workers 需 **Workers Paid**（$5/月）。免费版每请求 10ms CPU，无法运行 Python（冷启动与密码哈希都会超限）。

---

## 一、自建服务器

### 1. 一键部署（Ubuntu/Debian，root）

```bash
git clone https://github.com/xyztony999/nim-proxy.git
cd nim-proxy
NVIDIA_API_KEYS="nvapi-你的密钥" \
PROXY_API_KEYS="sk-自定义访问密钥" \
PORT=8000 \
bash deploy.sh
```

不带参数运行会交互式询问（访问密钥回车自动生成）。脚本会：

- 安装 python3/venv/pip，创建 `/opt/nim-proxy`，拷贝 `app/`、`workers/`、`web/dist`（如有）。
- 生成 `/opt/nim-proxy/.env`（含 `NVIDIA_API_KEYS`、`PROXY_API_KEYS`、`ADMIN_TOKEN`、`PORT`），权限 600；**已有 .env 会保留**。
- 注册并启动 systemd 服务 `nim-proxy`（入口 `uvicorn app.main:app --workers 1`）。
- 放行 ufw 端口（如启用），本地 `/health` 自检。

部署完成输出管理台地址 `http://<IP>:8000/admin/` 与管理令牌。

### 2. 管理台登录

- 服务器部署时 `.env` 已生成 `ADMIN_TOKEN` → 打开 `/admin/` 直接用该令牌登录（向导自动跳过）。
- 若清空 `ADMIN_TOKEN`，则首次进入走**界面向导**（填 NVIDIA 密钥 + 设密码）。

### 3. 域名 + HTTPS（可选，浏览器端客户端必需）

```bash
apt install -y nginx certbot python3-certbot-nginx
cp nginx-nim-proxy.conf /etc/nginx/sites-available/nim-proxy
ln -s /etc/nginx/sites-available/nim-proxy /etc/nginx/sites-enabled/
sed -i 's/api.example.com/你的域名/' /etc/nginx/sites-available/nim-proxy
nginx -t && systemctl reload nginx
certbot --nginx -d 你的域名
```

配置已含 `proxy_buffering off`（SSE 流式必需）、`client_max_body_size 64m`（多模态）。

### 4. 日常运维

```bash
systemctl restart nim-proxy                 # 改 .env 后重启
journalctl -u nim-proxy -f                  # 实时日志
vim /opt/nim-proxy/.env                     # 改密钥/端口
```

详见 [OPERATIONS.md](OPERATIONS.md)。

---

## 二、Cloudflare Workers

### 1. 前置

- Cloudflare 账号，**Workers Paid** 订阅。
- 一个托管在 Cloudflare 的域名（如 `tonyxyz.com`）。`workers.dev` 默认域名在中国大陆不可达，生产必须用自定义域名。
- 本机（建议 WSL/Linux）：`uv`、`wrangler`、Node 22+、Cloudflare API Token（Workers Scripts Edit + D1 Edit）。

### 2. 资源准备

```bash
# 创建生产 D1（记录返回的 database_id，填入 wrangler.jsonc）
wrangler d1 create nim-proxy
```

`wrangler.jsonc` 关键配置：

```jsonc
{
  "name": "nim-proxy",
  "main": "workers/entry.py",
  "compatibility_flags": ["python_workers"],
  "limits": { "cpu_ms": 300000 },
  "d1_databases": [{ "binding": "DB", "database_name": "nim-proxy",
                     "database_id": "<你的D1 id>", "migrations_dir": "workers/migrations" }],
  "routes": [{ "pattern": "nim-proxy.你的域名", "custom_domain": true }],
  "assets": { "directory": "./web/dist", "binding": "ASSETS",
              "not_found_handling": "single-page-application",
              "run_worker_first": ["/api/*", "/v1/*", "/health"] }
}
```

### 3. 构建与部署

```bash
# 1) 打包 Python 依赖（pywrangler 拒绝根目录 requirements.txt，临时移开）
mv requirements.txt /tmp/req.txt
uvx --from workers-py pywrangler sync
mv /tmp/req.txt requirements.txt

# 2) 构建前端并布局 /admin 前缀（镜像整个 dist 根，含 favicon/logo/manifest）
(cd web && npm ci && npm run build && cd dist && mkdir -p admin && for f in *; do [ "$f" != "admin" ] && cp -r "$f" admin/; done)

# 3) 把 app 拷进 Workers 打包目录
cp -r app workers/app

# 4) 迁移 + 部署
wrangler d1 migrations apply nim-proxy --remote
wrangler deploy

# 5) 清理临时副本
rm -rf workers/app
```

> D1 schema 由 `wrangler d1 migrations apply` 管理；运行时不执行多行 DDL（D1 `.exec()` 按换行拆分会报错）。

### 4. 首次初始化

打开 `https://nim-proxy.你的域名/admin/` → 自动进入向导：

1. 填 NVIDIA 密钥（向 NIM 验证所有权，假密钥会被拒）。
2. 设管理员密码（PBKDF2 哈希存 D1）。
3. 可选签发客户端密钥。

完成后设置入口**永久锁定**，用管理员密码登录。**无需 `wrangler secret put`**。

---

## 三、CI/CD（GitHub Actions）

`.github/workflows/` 三条流水线：

| 工作流 | 触发 | 作用 |
|--------|------|------|
| `ci.yml` | push main / PR | 后端 ruff+pytest(coverage)；前端 typecheck+lint+build |
| `deploy-workers.yml` | push main（相关路径）/ 手动 | sync→构建前端→拷 app→D1 迁移→wrangler deploy |
| `deploy-server.yml` | push main（相关路径）/ 手动 | 构建前端→scp→远端 `sudo bash deploy.sh` |

**缺配置只构建、跳过部署**（不会发失败通知）：部署步骤由检查步骤输出的布尔值守卫。

### 所需 Repository Secrets

GitHub → Settings → Secrets and variables → Actions：

```bash
# Workers
gh secret set CLOUDFLARE_API_TOKEN --body "<API Token>"
gh secret set CLOUDFLARE_ACCOUNT_ID --body "<账户 ID>"

# 服务器
gh secret set SERVER_HOST --body "<VPS IP>"
gh secret set SERVER_USER --body "root"
gh secret set SSH_PRIVATE_KEY < ~/.ssh/id_ed25519
gh secret set SERVER_PORT --body "22"        # 可选
```

第二台 VPS：复制 `deploy-server.yml` 改用另一组 secret（或 GitHub Environment）。

### 手动触发

```bash
gh workflow run deploy-workers.yml
gh workflow run deploy-server.yml
```

---

## 四、部署后验证

```bash
curl https://nim-proxy.你的域名/health           # {"status":"ok",...}
curl https://nim-proxy.你的域名/api/v1/setup/status   # 未初始化时 {"configured":false,...}
# 浏览器打开 /admin/ 走向导
```
