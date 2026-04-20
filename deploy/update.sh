#!/bin/bash
set -e
cd /opt/tradingRecords

run_privileged() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
    return
  fi

  if command -v sudo >/dev/null 2>&1; then
    # Non-interactive sudo keeps remote automation predictable.
    sudo -n "$@"
    return
  fi

  echo "缺少管理员权限: 请使用 root 执行，或为当前用户配置 sudo。"
  exit 1
}

echo "=== 拉取最新代码 ==="
git pull

echo "=== 安装后端依赖 ==="
cd backend
pip3 install -r requirements.txt --break-system-packages -q

echo "=== 构建交易前端 ==="
cd ../frontend
npm install
npm run build

echo "=== 构建笔记前端 ==="
cd ../frontend-notes
npm install
npm run build

echo "=== 构建监控前端 ==="
cd ../frontend-monitor
npm install
npm run build

echo "=== 构建记账前端 ==="
cd ../frontend-ledger
npm install
npm run build

echo "=== 同步门户页面 ==="
for src in ../portal/*.html; do
  dst="/opt/tradingRecords/portal/$(basename "$src")"
  if [ "$(readlink -f "$src")" = "$(readlink -f "$dst")" ]; then
    continue
  fi
  cp "$src" "$dst"
done

echo "=== 重启服务 ==="
run_privileged cp /opt/tradingRecords/deploy/nginx.conf /etc/nginx/sites-available/trading
run_privileged nginx -t
run_privileged systemctl restart nginx
run_privileged systemctl restart trading

echo "=== 更新完成 ==="
