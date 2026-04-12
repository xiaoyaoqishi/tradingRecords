#!/bin/bash
set -e

echo "=== 1. 系统依赖 ==="
apt update && apt install -y python3 python3-pip nginx nodejs npm

echo "=== 2. 拉取代码 ==="
cd /opt
git clone https://github.com/xiaoyaoqishi/tradingRecords.git
cd tradingRecords

echo "=== 3. 后端 ==="
cd backend
pip3 install -r requirements.txt
mkdir -p data

echo "=== 4. 前端构建 ==="
cd ../frontend
npm install
npm run build

cd ../frontend-notes
npm install
npm run build

cd ../frontend-monitor
npm install
npm run build

echo "=== 5. 配置 Nginx ==="
cp ../deploy/nginx.conf /etc/nginx/sites-available/trading
ln -sf /etc/nginx/sites-available/trading /etc/nginx/sites-enabled/trading
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo "=== 6. 配置后端服务 ==="
cp ../deploy/trading.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable trading
systemctl start trading

echo "=== 部署完成 ==="
echo "访问 http://$(curl -s ifconfig.me)"
