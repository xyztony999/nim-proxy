#!/usr/bin/env bash
#
# NIM Proxy 一键部署脚本（Ubuntu/Debian，需 root）
# 用法：
#   NVIDIA_API_KEYS="nvapi-xxx" PROXY_API_KEYS="sk-xxx" PORT=8000 ./deploy.sh
#   或者不带参数直接运行，脚本会交互式询问。
#
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/nim-proxy}"
SERVICE_NAME="nim-proxy"
PORT="${PORT:-8000}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ "$(id -u)" -eq 0 ] || { echo "请用 root 运行（sudo -i 或 sudo bash deploy.sh）"; exit 1; }

# ---------- 询问配置 ----------
if [ -f "$APP_DIR/.env" ]; then
  echo "检测到已有配置 $APP_DIR/.env，保留使用。"
  set -a; . "$APP_DIR/.env"; set +a
  PORT="${PORT:-$PORT}"
else
  if [ -z "${NVIDIA_API_KEYS:-}" ]; then
    read -rp "输入 NVIDIA NIM 密钥（nvapi-xxx，多个用逗号分隔）: " NVIDIA_API_KEYS
  fi
  if [ -z "${PROXY_API_KEYS:-}" ]; then
    read -rp "输入客户端访问密钥（自定义随机串，回车则自动生成）: " PROXY_API_KEYS
    [ -n "$PROXY_API_KEYS" ] || PROXY_API_KEYS="sk-$(head -c 24 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9')"
  fi
fi

# ---------- 安装系统依赖 ----------
if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y -qq
  apt-get install -y -qq python3 python3-venv python3-pip curl >/dev/null
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y -q python3 python3-pip curl >/dev/null
elif command -v yum >/dev/null 2>&1; then
  yum install -y -q python3 python3-pip curl >/dev/null
else
  echo "未识别的包管理器，请手动安装 python3 + venv + pip"; exit 1
fi

# ---------- 部署代码 ----------
mkdir -p "$APP_DIR"
rm -rf "$APP_DIR/app" "$APP_DIR/workers"
cp -r "$SRC_DIR/app" "$APP_DIR/app"
cp -r "$SRC_DIR/workers" "$APP_DIR/workers"
install -m 644 "$SRC_DIR/requirements.txt" "$APP_DIR/requirements.txt"
# 管理台前端构建产物（如已构建）
if [ -d "$SRC_DIR/web/dist" ]; then
  rm -rf "$APP_DIR/web/dist"
  mkdir -p "$APP_DIR/web"
  cp -r "$SRC_DIR/web/dist" "$APP_DIR/web/dist"
fi

if [ ! -f "$APP_DIR/.env" ]; then
  ADMIN_TOKEN="${ADMIN_TOKEN:-adm-$(head -c 24 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9')}"
  cat > "$APP_DIR/.env" <<EOF
NVIDIA_API_KEYS=$NVIDIA_API_KEYS
PROXY_API_KEYS=$PROXY_API_KEYS
ADMIN_TOKEN=$ADMIN_TOKEN
PORT=$PORT
EOF
  chmod 600 "$APP_DIR/.env"
fi

python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# ---------- systemd 服务 ----------
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=NVIDIA NIM API Proxy
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
Restart=always
RestartSec=3
# 安全加固
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null
systemctl restart "$SERVICE_NAME"

# ---------- 防火墙 ----------
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow "${PORT}/tcp" >/dev/null && echo "ufw 已放行端口 $PORT"
fi
# 注意：Vultr 还需在控制台 Firewall / 网页面板确认放行；搬瓦工一般默认不拦。

sleep 2
# ---------- 自检 ----------
if curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null; then
  echo
  echo "✅ 部署成功，服务已运行。"
else
  echo
  echo "⚠️ 本地健康检查未通过，查看日志：journalctl -u ${SERVICE_NAME} -n 50 --no-pager"
  exit 1
fi

echo
echo "================ 部署信息 ================"
echo "服务目录 : $APP_DIR"
echo "配置文件 : $APP_DIR/.env"
echo "端口     : $PORT"
echo "自检     : http://127.0.0.1:${PORT}/health"
echo "对外地址 : http://<服务器IP>:${PORT}"
echo
echo "客户端密钥: $PROXY_API_KEYS"
echo "管理令牌  : ${ADMIN_TOKEN:-（见 .env）}"
echo "管理台    : http://<服务器IP>:${PORT}/admin/"
echo
echo "测试（替换 <IP> 与密钥）:"
echo "  curl http://<IP>:${PORT}/v1/chat/completions -H 'Content-Type: application/json' -H \"Authorization: Bearer $PROXY_API_KEYS\" -d '{\"model\":\"minimaxai/minimax-m3.1-flash\",\"messages\":[{\"role\":\"user\",\"content\":\"你好\"}],\"max_tokens\":64}'"
echo
echo "修改配置后重启: systemctl restart ${SERVICE_NAME}"
echo "看日志        : journalctl -u ${SERVICE_NAME} -f"
