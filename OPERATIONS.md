# 运维手册

日常操作、密钥管理、排障、升级与备份。分「自建服务器」与「Cloudflare Workers」两个目标。

---

## 一、日常操作

### 服务管理（服务器）

```bash
systemctl status nim-proxy            # 状态
systemctl restart nim-proxy           # 重启（改 .env 后）
journalctl -u nim-proxy -f            # 实时日志
journalctl -u nim-proxy -n 200 --no-pager   # 最近 200 行
```

### 服务管理（Workers）

```bash
wrangler deployments list             # 部署历史
wrangler rollback                     # 回滚到上一版本
wrangler tail                         # 实时日志（需 workers.dev 可达；国内用仪表盘 Observability）
```

仪表盘 → Workers & Pages → nim-proxy → **Logs / Observability** 看请求与异常（国内推荐）。

### 健康检查

```bash
curl https://<域名>/health
# {"status":"ok","upstream":"...","upstream_keys":N,"proxy_auth":true/false}
```

---

## 二、密钥管理（管理台）

登录 `/admin/`（管理员密码或 env 令牌）：

- **上游密钥**：新增（填 `nvapi-`）/ 启用 / 停用 / 删除；列表显示脱敏值、最近错误码、连续失败次数。
- **客户端密钥**：签发（自动生成 `sk-`，**完整值仅显示一次**）/ 启用 / 停用 / 撤销（软删除，终态）。
- 停用的上游密钥不参与轮询；停用的客户端密钥无法鉴权。

> 密钥完整值仅在创建时返回一次，之后只能看脱敏值。请妥善保存客户端密钥。

### 命令行改密钥（服务器）

```bash
vim /opt/nim-proxy/.env               # 改 NVIDIA_API_KEYS / PROXY_API_KEYS / ADMIN_TOKEN
systemctl restart nim-proxy
```

> 注意：env 里的密钥是**首次种子**；管理台界面增删的密钥存在数据库。两者并存时以数据库为运行依据。

---

## 三、用量与日志

管理台：

- **运行看板**：服务状态、鉴权模式、密钥数、今日请求/错误/429 计数。
- **用量统计**：按密钥/模型/状态维度，小时/天粒度图表（token 为尽力统计）。
- **请求日志**：最近请求明细，按模型/状态码筛选，分页；保留 30 天。

---

## 四、升级

### 服务器

```bash
cd nim-proxy && git pull
# 重新构建前端（如需）
(cd web && npm ci && npm run build)
bash deploy.sh                        # 保留已有 .env，覆盖代码并重启
```

### Workers

```bash
git pull
# 走 CI：push main 自动部署；或手动
gh workflow run deploy-workers.yml
```

升级会保留 D1 数据与已设的管理员凭证/密钥。新增迁移由 CI `wrangler d1 migrations apply` 自动应用。

---

## 五、备份与恢复

### 服务器（SQLite）

```bash
# 备份（WAL 模式建议用 .backup 或停服拷贝）
sqlite3 /opt/nim-proxy/data/nim-proxy.db ".backup '/root/nim-proxy-backup.db'"
# 恢复
systemctl stop nim-proxy
cp /root/nim-proxy-backup.db /opt/nim-proxy/data/nim-proxy.db
systemctl start nim-proxy
```

### Workers（D1）

```bash
wrangler d1 export nim-proxy --remote --output nim-proxy-backup.sql   # 导出
wrangler d1 execute nim-proxy --remote --file nim-proxy-backup.sql    # 恢复到同名库
```

D1 自带 Time Travel（付费版 30 天），可在仪表盘按时间点恢复。

---

## 六、排障

| 现象 | 原因 / 处理 |
|------|------|
| 客户端 401 `Invalid or missing API key` | 客户端密钥不对（应是 `sk-` 自定义密钥，不是 `nvapi-`）；或密钥已停用/撤销 |
| 上游 401/403 | NIM 密钥失效；管理台看上游密钥「最近错误码」，更换密钥 |
| 上游 429 | 账户级限速（免费约 40 RPM）；降低并发或申请提额 |
| 流式卡顿/一次性吐出 | 反代层缓冲了 SSE；nginx 必须 `proxy_buffering off`（用本仓库配置） |
| Workers 503 `exceededCpu` | 免费版 10ms CPU 不够；升级 Workers Paid |
| Workers 500 `D1_EXEC_ERROR` | 运行时不应执行多行 DDL；schema 走 `wrangler d1 migrations apply` |
| 首次设置 422「密钥验证失败」 | NVIDIA 密钥无效（上游 401/403）；检查密钥 |
| 首次设置 409「已锁定」 | 已初始化过；用管理员密码登录，或重置数据库（见下） |
| 国内打不开 workers.dev | 该域名被阻断；用自定义域名 |
| 管理台打不开 | 确认前端已构建（`web/dist`）且部署包含；Workers 看 assets 配置 |

### 重置首次设置（谨慎，会清空密钥与凭证）

```bash
# Workers
wrangler d1 execute nim-proxy --remote --command "DELETE FROM np_admin_credential"
wrangler d1 execute nim-proxy --remote --command "DELETE FROM np_admin_session"
wrangler d1 execute nim-proxy --remote --command "DELETE FROM np_upstream_key"
wrangler d1 execute nim-proxy --remote --command "DELETE FROM np_client_key"
# 服务器：删除 data/nim-proxy.db 后重启（会重新种子 env 密钥）
```

---

## 七、监控建议

- 外部 uptime 监控定期打 `/health`（如 UptimeRobot）。
- Workers 仪表盘 Observability 看错误率与 CPU；关注 `exceededCpu`。
- 管理台看板每日扫一眼错误/429 计数；上游密钥连续失败次数升高时及时换钥。

## 八、安全清单

- ✅ 生产用 HTTPS（服务器 certbot / Workers 自带）。
- ✅ 管理台用强密码；`ADMIN_TOKEN`（若用）足够随机。
- ✅ 客户端密钥按需签发、不用即撤销；完整值仅创建时可见。
- ✅ `.env` 权限 600，不入仓库（`.gitignore` 已排除）。
- ✅ 首次设置以 NVIDIA 密钥验证所有权，设完永久锁定，防公网抢占。
