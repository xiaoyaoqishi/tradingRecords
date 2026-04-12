#!/usr/bin/env bash
set -euo pipefail

SESSION_NAME="trade-dev"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.dev-run"

SERVICES=(
  "backend|$ROOT_DIR/backend|DEV_MODE=1 python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"
  "frontend|$ROOT_DIR/frontend|npm run dev"
  "notes|$ROOT_DIR/frontend-notes|npm run dev"
  "monitor|$ROOT_DIR/frontend-monitor|npm run dev"
)

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少命令: $1"
    exit 1
  fi
}

has_tmux() {
  command -v tmux >/dev/null 2>&1
}

ensure_base_deps() {
  require_cmd python3
  require_cmd npm
}

parse_service() {
  local line="$1"
  SERVICE_NAME="${line%%|*}"
  local rest="${line#*|}"
  SERVICE_DIR="${rest%%|*}"
  SERVICE_CMD="${rest#*|}"
}

start_tmux() {
  if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "会话已存在: $SESSION_NAME"
    echo "执行: ./dev.sh attach"
    return
  fi

  local first=1
  for svc in "${SERVICES[@]}"; do
    parse_service "$svc"
    if [[ $first -eq 1 ]]; then
      tmux new-session -d -s "$SESSION_NAME" -n "$SERVICE_NAME" \
        "cd '$SERVICE_DIR' && $SERVICE_CMD"
      first=0
    else
      tmux new-window -t "$SESSION_NAME" -n "$SERVICE_NAME" \
        "cd '$SERVICE_DIR' && $SERVICE_CMD"
    fi
  done

  echo "已启动(tmux): $SESSION_NAME"
}

start_bg() {
  mkdir -p "$RUN_DIR"

  for svc in "${SERVICES[@]}"; do
    parse_service "$svc"
    local pid_file="$RUN_DIR/$SERVICE_NAME.pid"
    local log_file="$RUN_DIR/$SERVICE_NAME.log"

    if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
      echo "$SERVICE_NAME 已在运行(pid=$(cat "$pid_file"))"
      continue
    fi

    (
      cd "$SERVICE_DIR"
      nohup bash -lc "$SERVICE_CMD" >"$log_file" 2>&1 &
      echo $! >"$pid_file"
    )
    echo "已启动: $SERVICE_NAME"
  done

  echo "已启动(后台模式)，日志目录: .dev-run/"
}

start_session() {
  ensure_base_deps
  if has_tmux; then
    start_tmux
  else
    start_bg
  fi
  echo "查看状态: ./dev.sh status"
  echo "查看日志: ./dev.sh attach"
}

stop_tmux() {
  if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    tmux kill-session -t "$SESSION_NAME"
    echo "已停止: $SESSION_NAME"
  else
    echo "未找到会话: $SESSION_NAME"
  fi
}

stop_bg() {
  if [[ ! -d "$RUN_DIR" ]]; then
    echo "未运行: 后台模式"
    return
  fi

  local any=0
  for pid_file in "$RUN_DIR"/*.pid; do
    [[ -e "$pid_file" ]] || continue
    any=1
    local name
    name="$(basename "$pid_file" .pid)"
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      echo "已停止: $name (pid=$pid)"
    else
      echo "已退出: $name"
    fi
    rm -f "$pid_file"
  done

  if [[ $any -eq 0 ]]; then
    echo "未运行: 后台模式"
  fi
}

stop_session() {
  if has_tmux; then
    stop_tmux
  fi
  stop_bg
}

attach_session() {
  if has_tmux && tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    tmux attach -t "$SESSION_NAME"
    return
  fi

  if [[ -d "$RUN_DIR" ]]; then
    if ls "$RUN_DIR"/*.log >/dev/null 2>&1; then
      tail -f "$RUN_DIR"/*.log
      return
    fi
  fi

  echo "没有可附着的会话或日志"
}

status_tmux() {
  if has_tmux && tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "运行中(tmux): $SESSION_NAME"
    tmux list-windows -t "$SESSION_NAME"
  else
    echo "未运行(tmux): $SESSION_NAME"
  fi
}

status_bg() {
  if [[ ! -d "$RUN_DIR" ]]; then
    echo "未运行(后台模式)"
    return
  fi

  local any=0
  for pid_file in "$RUN_DIR"/*.pid; do
    [[ -e "$pid_file" ]] || continue
    any=1
    local name
    name="$(basename "$pid_file" .pid)"
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "运行中: $name (pid=$pid)"
    else
      echo "已退出: $name (pid=$pid)"
    fi
  done

  if [[ $any -eq 0 ]]; then
    echo "未运行(后台模式)"
  fi
}

status_session() {
  status_tmux
  status_bg
}

restart_session() {
  stop_session
  start_session
}

usage() {
  cat <<USAGE
用法: ./dev.sh [up|down|attach|status|restart]
  up       一键启动全部本地调试服务
  down     停止全部服务
  attach   tmux附着或后台日志跟随
  status   查看运行状态
  restart  重启全部服务
USAGE
}

cmd="${1:-up}"
case "$cmd" in
  up) start_session ;;
  down) stop_session ;;
  attach) attach_session ;;
  status) status_session ;;
  restart) restart_session ;;
  *) usage; exit 1 ;;
esac
