# NIM Proxy — NVIDIA NIM API 中转服务

在你的 Vultr / 搬瓦工海外服务器上部署一个 OpenAI 兼容的反代，
把请求转发到 NVIDIA NIM（`https://integrate.api.nvidia.com/v1/...`）。

特点：

- **完全透传** `/v1/*` 所有接口（chat/completions、models、embeddings 等），
  流式（SSE）与非流式都支持，多模态（image_url）请求原样转发
- **客户端鉴权**：访问代理用你自己定的密钥，真实 NVIDIA 密钥只存在服务器上
- **多密钥轮询**：填多个 `nvapi-` 密钥自动轮换，遇到 401/403/429 自动换下一个重试
  ⚠️ 注意：NVIDIA 限速是**账户级**（免费账户约 40 RPM）——同一个账户里建多个 key
  共享同一额度，轮换**不能**提升吞吐，只在多账户的 key 之间有效（多账户违反 ToS，
  封号风险自担）。正规提额途径：NVIDIA 开发者论坛发帖申请（有人 40→180+ RPM 成功）
- **不解析转发**：原样透传请求体和响应体，NIM 升级参数无需改代码

---

## 一、上传并部署

在你本机（Windows Git Bash）执行，把目录传到服务器：

```bash
scp -r /c/Users/zhang/.zcode/workspace/draft-acbca4ee-0eea-4cf4-b446-f2479cdfd9e2/nim-proxy root@<服务器IP>:/root/
```

登录服务器，一键部署（Ubuntu/Debian，root）：

```bash
cd /root/nim-proxy
NVIDIA_API_KEYS="nvapi-你的NIM密钥" \
PROXY_API_KEYS="sk-你自己定的访问密钥" \
PORT=8000 \
bash deploy.sh
```

不带参数运行 `bash deploy.sh` 会交互式询问（访问密钥回车可自动生成）。

两台服务器（Vultr、搬瓦工）重复同样步骤即可，互为备份。
国内访问推荐走搬瓦工 CN2 GIA 线路，延迟更低。

> ⚠️ Vultr 记得在控制台的 Firewall（如果启用了）放行端口 8000。

## 二、测试

```bash
# 健康检查
curl http://<服务器IP>:8000/health

# 非流式
curl http://<服务器IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-你自己定的访问密钥" \
  -d '{
    "model": "minimaxai/minimax-m3.1-flash",
    "messages": [{"role": "user", "content": "你好，介绍一下你自己"}],
    "max_tokens": 256
  }'
```

带图片的多模态请求（和你给的样例一致，改个地址即可）：

```python
import requests

invoke_url = "http://<服务器IP>:8000/v1/chat/completions"   # 原来是 integrate.api.nvidia.com
stream = True

headers = {
    "Authorization": "Bearer sk-你自己定的访问密钥",        # 原来是 nvapi-xxx
    "Accept": "text/event-stream" if stream else "application/json",
}

payload = {
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is in this image?"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://assets.ngc.nvidia.com/products/api-catalog/phi-3-5-vision/example1b.jpg"
                    },
                },
            ],
        }
    ],
    "model": "minimaxai/minimax-m3.1-flash",
    "max_tokens": 16384,
    "stream": stream,
    "temperature": 1,
    "top_p": 0.95,
}

response = requests.post(invoke_url, headers=headers, json=payload, stream=stream)
for line in response.iter_lines():
    if line:
        print(line.decode("utf-8"))
```

## 三、接入常见客户端

任何支持"自定义 OpenAI API 地址"的软件都能直接用：

| 参数 | 值 |
|---|---|
| API Base / Base URL | `http://<服务器IP>:8000/v1` |
| API Key | `sk-你自己定的访问密钥` |
| Model | NIM 上的任意模型名，如 `minimaxai/minimax-m3.1-flash` |

Python OpenAI SDK 示例：

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://<服务器IP>:8000/v1",
    api_key="sk-你自己定的访问密钥",
)

stream = client.chat.completions.create(
    model="minimaxai/minimax-m3.1-flash",
    messages=[{"role": "user", "content": "你好"}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

## 四、可选：域名 + HTTPS

浏览器端前端（LobeChat 网页版等）调用需要 HTTPS，绑个域名：

```bash
apt install -y nginx certbot python3-certbot-nginx
# 编辑 /etc/nginx/sites-available/nim-proxy（本目录有现成模板），改 server_name
cp nginx-nim-proxy.conf /etc/nginx/sites-available/nim-proxy
ln -s /etc/nginx/sites-available/nim-proxy /etc/nginx/sites-enabled/
sed -i 's/api.example.com/你的域名/' /etc/nginx/sites-available/nim-proxy
nginx -t && systemctl reload nginx
certbot --nginx -d 你的域名    # 自动签发证书并续期
```

之后 Base URL 用 `https://你的域名/v1`。已配置 `proxy_buffering off`，SSE 不受影响。

## 五、日常运维

```bash
systemctl restart nim-proxy                     # 改 .env 后重启
journalctl -u nim-proxy -f                      # 看实时日志
journalctl -u nim-proxy -n 200 --no-pager       # 看最近日志
vim /opt/nim-proxy/.env                         # 改密钥/端口
```

升级代码：本地重新 `scp` 覆盖 `app.py`，再在服务器上重跑 `bash deploy.sh`（保留已有 `.env`）。

## 六、常见问题

- **连不上？** 依次检查：服务是否在跑（`systemctl status nim-proxy`）→ 服务器防火墙（ufw / Vultr 控制台 Firewall / 搬瓦工 KiwiVM 面板）→ 本地 `curl http://127.0.0.1:8000/health` 是否正常。
- **401 Invalid or missing API key**：客户端密钥不对，它应该是 `PROXY_API_KEYS` 里定义的值，不是 `nvapi-` 开头的真实密钥。
- **流式输出卡顿/一次性吐出**：确认前面没有带缓冲的 CDN/代理层；nginx 必须用本目录给的配置（`proxy_buffering off`）。
- **想换上游地址**（比如自建 NIM）：`.env` 里加 `NIM_UPSTREAM=https://xxx`。
