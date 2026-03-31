#!/bin/bash
set -e
cd /opt/tradingRecords

echo "=== 拉取最新代码 ==="
git pull

echo "=== 安装后端依赖 ==="
cd backend
pip3 install -r requirements.txt --break-system-packages -q

echo "=== 构建前端 ==="
cd ../frontend
npm install
npm run build

echo "=== 重启服务 ==="
cp ../deploy/nginx.conf /etc/nginx/sites-available/trading
nginx -t && systemctl restart nginx
systemctl restart trading

echo "=== 更新完成 ==="
