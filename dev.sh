#!/usr/bin/env bash
set -euo pipefail

SESSION_NAME="trade-dev"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.dev-run"
DEV_LOG_MODE="${DEV_LOG_MODE:-file}" # file | none
DEV_CLEAN_ON_DOWN="${DEV_CLEAN_ON_DOWN:-1}" # 1 | 0

SERVICES=(
  "backend|$ROOT_DIR/backend|DEV_MODE=1 python3 -m uvicorn main:app --host 127.0.0.1 --port 8000"
  "frontend|$ROOT_DIR/frontend|npm run dev"
  "notes|$ROOT_DIR/frontend-notes|npm run dev"
  "monitor|$ROOT_DIR/frontend-monitor|npm run dev"
)
PYTHON_CMD=""

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
  require_cmd npm
  resolve_python_cmd
  SERVICES[0]="backend|$ROOT_DIR/backend|DEV_MODE=1 $PYTHON_CMD -m uvicorn main:app --host 127.0.0.1 --port 8000"
}

resolve_python_cmd() {
  local candidates=("python3" "python" "py -3")
  local cand
  for cand in "${candidates[@]}"; do
    if bash -lc "$cand -c 'import sys; print(sys.version_info[0])'" >/dev/null 2>&1; then
      PYTHON_CMD="$cand"
      return
    fi
  done
  echo "缺少可用的 Python 解释器（尝试了: python3 / python / py -3）"
  exit 1
}

parse_service() {
  local line="$1"
  SERVICE_NAME="${line%%|*}"
  local rest="${line#*|}"
  SERVICE_DIR="${rest%%|*}"
  SERVICE_CMD="${rest#*|}"
}

cleanup_run_artifacts() {
  [[ -d "$RUN_DIR" ]] || return 0

  for svc in "${SERVICES[@]}"; do
    parse_service "$svc"
    rm -f "$RUN_DIR/$SERVICE_NAME.pid" "$RUN_DIR/$SERVICE_NAME.log"
  done

  # 若目录为空则顺手移除，避免残留空目录
  if [[ -z "$(ls -A "$RUN_DIR" 2>/dev/null)" ]]; then
    rmdir "$RUN_DIR" 2>/dev/null || true
  fi
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
      if [[ "$DEV_LOG_MODE" == "none" ]]; then
        nohup bash -lc "$SERVICE_CMD" >/dev/null 2>&1 &
        rm -f "$log_file"
      else
        nohup bash -lc "$SERVICE_CMD" >"$log_file" 2>&1 &
      fi
      echo $! >"$pid_file"
    )
    echo "已启动: $SERVICE_NAME"
  done

  if [[ "$DEV_LOG_MODE" == "none" ]]; then
    echo "已启动(后台模式)，日志文件已禁用"
  else
    echo "已启动(后台模式)，日志目录: .dev-run/"
  fi
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
  if [[ "$DEV_CLEAN_ON_DOWN" == "1" ]]; then
    cleanup_run_artifacts
    echo "已清理调试产物: .dev-run/{*.pid,*.log}"
  fi
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

  if [[ "$DEV_LOG_MODE" == "none" ]]; then
    echo "后台日志已禁用(DEV_LOG_MODE=none)"
    return
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

环境变量:
  DEV_LOG_MODE=file|none   后台模式日志输出方式(默认 file)
  DEV_CLEAN_ON_DOWN=1|0    down 后是否自动清理 .dev-run 下 pid/log(默认 1)
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
