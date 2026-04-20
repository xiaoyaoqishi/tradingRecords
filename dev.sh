#!/usr/bin/env bash
set -euo pipefail

SESSION_NAME="trade-dev"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.dev-run"
DEV_LOG_MODE="${DEV_LOG_MODE:-file}" # file | none
DEV_CLEAN_ON_DOWN="${DEV_CLEAN_ON_DOWN:-1}" # 1 | 0

SERVICES=(
  "backend|$ROOT_DIR/backend|DEV_MODE=1 python3 -m uvicorn main:app --host 127.0.0.1 --port 8000"
)
PYTHON_CMD=""
ORPHAN_PIDS=()

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少命令: $1"
    exit 1
  fi
}

has_tmux() {
  command -v tmux >/dev/null 2>&1
}

is_windows_shell() {
  local uname_s
  uname_s="$(uname -s 2>/dev/null | tr '[:upper:]' '[:lower:]')"
  case "$uname_s" in
    msys*|mingw*|cygwin*) return 0 ;;
    *) return 1 ;;
  esac
}

ensure_base_deps() {
  require_cmd npm
  require_cmd node
  resolve_python_cmd
  build_services
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

has_dev_script() {
  local pkg="$1"
  node -e '
const fs = require("fs");
const pkg = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
process.exit(pkg.scripts && pkg.scripts.dev ? 0 : 1);
' "$pkg"
}

service_name_for_frontend_dir() {
  local dir_name="$1"
  case "$dir_name" in
    frontend) echo "frontend" ;;
    frontend-*) echo "${dir_name#frontend-}" ;;
    *) echo "$dir_name" ;;
  esac
}

has_service_name() {
  local candidate="$1"
  local svc
  for svc in "${SERVICES[@]}"; do
    parse_service "$svc"
    if [[ "$SERVICE_NAME" == "$candidate" ]]; then
      return 0
    fi
  done
  return 1
}

next_unique_service_name() {
  local base="$1"
  local candidate="$base"
  local idx=2
  while has_service_name "$candidate"; do
    candidate="${base}${idx}"
    idx=$((idx + 1))
  done
  echo "$candidate"
}

build_services() {
  SERVICES=(
    "backend|$ROOT_DIR/backend|DEV_MODE=1 $PYTHON_CMD -m uvicorn main:app --host 127.0.0.1 --port 8000"
    "portal|$ROOT_DIR/portal|PORTAL_DEV_PORT=${PORTAL_DEV_PORT:-5172} PORTAL_BACKEND_PORT=${PORTAL_BACKEND_PORT:-8000} PORTAL_TRADING_PORT=${PORTAL_TRADING_PORT:-5173} PORTAL_NOTES_PORT=${PORTAL_NOTES_PORT:-5174} PORTAL_MONITOR_PORT=${PORTAL_MONITOR_PORT:-5175} PORTAL_LEDGER_PORT=${PORTAL_LEDGER_PORT:-5176} $PYTHON_CMD dev_server.py"
  )

  local dir
  for dir in "$ROOT_DIR"/frontend*; do
    [[ -d "$dir" ]] || continue
    local pkg="$dir/package.json"
    [[ -f "$pkg" ]] || continue
    if ! has_dev_script "$pkg"; then
      continue
    fi
    local name
    name="$(service_name_for_frontend_dir "$(basename "$dir")")"
    name="$(next_unique_service_name "$name")"
    SERVICES+=("$name|$dir|npm run dev")
  done
}

append_orphan_pid() {
  local pid="$1"
  [[ -n "$pid" ]] || return 0
  [[ "$pid" =~ ^[0-9]+$ ]] || return 0
  [[ "$pid" -eq $$ ]] && return 0

  local existing
  for existing in "${ORPHAN_PIDS[@]-}"; do
    [[ "$existing" == "$pid" ]] && return 0
  done
  ORPHAN_PIDS+=("$pid")
}

collect_descendant_pids() {
  local parent_pid="$1"
  [[ -n "$parent_pid" ]] || return 0
  [[ "$parent_pid" =~ ^[0-9]+$ ]] || return 0

  local child_pid
  while read -r child_pid; do
    [[ -n "$child_pid" ]] || continue
    echo "$child_pid"
    collect_descendant_pids "$child_pid"
  done < <(
    ps -eo pid=,ppid= | awk -v parent="$parent_pid" '$2 == parent { print $1 }'
  )
}

terminate_pid_tree() {
  local root_pid="${1:-}"
  [[ -n "$root_pid" ]] || return 0
  [[ "$root_pid" =~ ^[0-9]+$ ]] || return 0
  [[ "$root_pid" -eq $$ ]] && return 0

  local descendants_raw=""
  local pid
  descendants_raw="$(collect_descendant_pids "$root_pid" | tr '\n' ' ' | xargs 2>/dev/null || true)"

  if [[ -n "$descendants_raw" ]]; then
    # shellcheck disable=SC2086
    kill $descendants_raw 2>/dev/null || true
  fi
  kill "$root_pid" 2>/dev/null || true
  sleep 1

  local survivors=()
  for pid in $descendants_raw "$root_pid"; do
    [[ -n "$pid" ]] || continue
    if kill -0 "$pid" 2>/dev/null; then
      survivors+=("$pid")
    fi
  done

  if [[ ${#survivors[@]} -gt 0 ]]; then
    kill -9 "${survivors[@]}" 2>/dev/null || true
  fi
}

collect_orphan_pids() {
  ORPHAN_PIDS=()
  local repo_name
  repo_name="$(basename "$ROOT_DIR" | tr '[:upper:]' '[:lower:]')"

  while read -r pid ppid; do
    append_orphan_pid "$pid"
    local parent_cmd
    parent_cmd="$(ps -p "$ppid" -o command= 2>/dev/null || true)"
    if [[ "$parent_cmd" == *"npm run dev"* ]]; then
      append_orphan_pid "$ppid"
    fi
  done < <(
    ps -eo pid=,ppid=,command= | awk -v repo="$repo_name" '
      {
        line=tolower($0)
        if (index(line, "node_modules") && index(line, "vite") && index(line, repo)) {
          print $1 " " $2
        }
      }
    '
  )

  while read -r pid; do
    append_orphan_pid "$pid"
  done < <(
    ps -eo pid=,command= | awk -v root="$ROOT_DIR/" '
      index($0, root) && index($0, "uvicorn main:app --host 127.0.0.1 --port 8000") { print $1 }
    '
  )

  while read -r pid; do
    append_orphan_pid "$pid"
  done < <(
    ps -eo pid=,command= | awk -v root="$ROOT_DIR/" '
      index($0, root) && index($0, "dev_server.py") { print $1 }
    '
  )
}

stop_orphan_dev_processes() {
  collect_orphan_pids
  if [[ ${#ORPHAN_PIDS[@]} -eq 0 ]]; then
    echo "未发现残留调试进程"
    return 0
  fi

  local pid
  for pid in "${ORPHAN_PIDS[@]}"; do
    terminate_pid_tree "$pid"
  done

  echo "已清理残留调试进程: ${ORPHAN_PIDS[*]}"
}

stop_orphan_dev_processes_windows() {
  if ! is_windows_shell || ! command -v powershell.exe >/dev/null 2>&1; then
    return 0
  fi

  local repo_name ps_out
  repo_name="$(basename "$ROOT_DIR")"
  ps_out="$(powershell.exe -NoProfile -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; \$repo='${repo_name}'; \$procs=Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -and \$_.CommandLine -like \"*\$repo*\" -and ((\$_.CommandLine -like '*node_modules*' -and \$_.CommandLine -like '*vite*') -or \$_.CommandLine -like '*npm run dev*' -or \$_.CommandLine -like '*uvicorn main:app*' -or \$_.CommandLine -like '*dev_server.py*') }; if (-not \$procs) { Write-Output '__NONE__'; exit 0 }; \$ids = \$procs | Select-Object -ExpandProperty ProcessId -Unique; Stop-Process -Id \$ids -Force -ErrorAction SilentlyContinue; Write-Output (\$ids -join ' ')" 2>/dev/null | tr -d '\r')"

  if [[ -n "$ps_out" && "$ps_out" != "__NONE__" ]]; then
    echo "Windows fallback cleaned dev processes: $ps_out"
  fi
}

cleanup_run_artifacts() {
  [[ -d "$RUN_DIR" ]] || return 0

  # 全量清理 .dev-run 下调试产物（含历史 manual 日志）
  rm -f "$RUN_DIR"/*.pid "$RUN_DIR"/*.log

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
      terminate_pid_tree "$pid"
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
  stop_orphan_dev_processes
  stop_orphan_dev_processes_windows
  if [[ "$DEV_CLEAN_ON_DOWN" == "1" ]]; then
    cleanup_run_artifacts
    echo "已全量清理调试产物: .dev-run/{*.pid,*.log}"
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
