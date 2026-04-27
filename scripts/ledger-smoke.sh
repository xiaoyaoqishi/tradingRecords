#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/4] 检查 portal 是否包含账务管理入口"
if ! rg -n 'href="/ledger/"' "$ROOT_DIR/portal/index.html" >/dev/null; then
  echo "FAIL: portal/index.html 未找到 /ledger/ 入口"
  exit 1
fi

echo "[2/4] 检查 nginx 是否包含 /ledger/ 静态路由"
if ! rg -n 'location /ledger/' "$ROOT_DIR/deploy/nginx.conf" >/dev/null; then
  echo "FAIL: deploy/nginx.conf 缺少 location /ledger/"
  exit 1
fi
if ! rg -n 'location = /ledger' "$ROOT_DIR/deploy/nginx.conf" >/dev/null; then
  echo "FAIL: deploy/nginx.conf 缺少 /ledger -> /ledger/ 重定向"
  exit 1
fi
if ! rg -n '/opt/tradingRecords/frontend-ledger/dist/' "$ROOT_DIR/deploy/nginx.conf" >/dev/null; then
  echo "FAIL: deploy/nginx.conf 缺少 frontend-ledger dist alias"
  exit 1
fi
if ! rg -n '/ledger/index.html' "$ROOT_DIR/deploy/nginx.conf" >/dev/null; then
  echo "FAIL: deploy/nginx.conf 缺少 /ledger/index.html fallback"
  exit 1
fi

echo "[3/4] 检查 frontend-ledger 构建产物"
if [[ ! -f "$ROOT_DIR/frontend-ledger/dist/index.html" ]]; then
  echo "FAIL: frontend-ledger/dist/index.html 不存在，请先执行 frontend-ledger npm run build"
  exit 1
fi
if ! rg -n '/ledger/assets/' "$ROOT_DIR/frontend-ledger/dist/index.html" >/dev/null; then
  echo "FAIL: dist/index.html 未引用 /ledger/assets/，请检查 vite base 配置"
  exit 1
fi

echo "[4/5] 检查 /ledger/imports /ledger/merchants /ledger/rules /ledger/analytics 路由入口"
if ! rg -n 'path=\"/imports\"' "$ROOT_DIR/frontend-ledger/src/App.jsx" >/dev/null; then
  echo "FAIL: frontend-ledger 缺少 /ledger/imports 路由"
  exit 1
fi
if ! rg -n 'path=\"/merchants\"' "$ROOT_DIR/frontend-ledger/src/App.jsx" >/dev/null; then
  echo "FAIL: frontend-ledger 缺少 /ledger/merchants 路由"
  exit 1
fi
if ! rg -n 'path=\"/rules\"' "$ROOT_DIR/frontend-ledger/src/App.jsx" >/dev/null; then
  echo "FAIL: frontend-ledger 缺少 /ledger/rules 路由"
  exit 1
fi
if ! rg -n 'path=\"/analytics\"' "$ROOT_DIR/frontend-ledger/src/App.jsx" >/dev/null; then
  echo "FAIL: frontend-ledger 缺少 /ledger/analytics 路由"
  exit 1
fi
if ! rg -n "key: '/imports'" "$ROOT_DIR/frontend-ledger/src/components/IconSidebar.jsx" >/dev/null; then
  echo "FAIL: frontend-ledger 侧边栏缺少导入入口"
  exit 1
fi
if ! rg -n "key: '/merchants'" "$ROOT_DIR/frontend-ledger/src/components/IconSidebar.jsx" >/dev/null; then
  echo "FAIL: frontend-ledger 侧边栏缺少商户词典入口"
  exit 1
fi
if ! rg -n "key: '/rules'" "$ROOT_DIR/frontend-ledger/src/components/IconSidebar.jsx" >/dev/null; then
  echo "FAIL: frontend-ledger 侧边栏缺少规则入口"
  exit 1
fi
if ! rg -n "key: '/analytics'" "$ROOT_DIR/frontend-ledger/src/components/IconSidebar.jsx" >/dev/null; then
  echo "FAIL: frontend-ledger 侧边栏缺少分析入口"
  exit 1
fi

echo "[5/5] （可选）在线检查"
BASE_URL="${BASE_URL:-}"
if [[ -n "$BASE_URL" ]]; then
  BASE_URL="${BASE_URL%/}"
  portal_html="$(curl -fsSL "$BASE_URL/")"
  echo "$portal_html" | rg -n 'href="/ledger/"' >/dev/null || {
    echo "FAIL: 在线 portal 页面未找到 /ledger/ 入口"
    exit 1
  }

  ledger_html="$(curl -fsSL "$BASE_URL/ledger/")"
  asset_path="$(echo "$ledger_html" | rg -o '/ledger/assets/[^" ]+\.(js|css)' | head -n 1 || true)"
  if [[ -z "$asset_path" ]]; then
    echo "FAIL: 在线 /ledger/ 页面未解析到资源路径"
    exit 1
  fi
  ledger_redirect_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/ledger")"
  if [[ "$ledger_redirect_code" != "301" && "$ledger_redirect_code" != "302" ]]; then
    echo "FAIL: 在线 /ledger 未返回重定向，当前状态码: $ledger_redirect_code"
    exit 1
  fi
  curl -fsSL "$BASE_URL$asset_path" >/dev/null || {
    echo "FAIL: 在线资源不可访问: $asset_path"
    exit 1
  }
fi

echo "PASS: ledger smoke checks passed"
