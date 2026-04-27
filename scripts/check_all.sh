#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

status=0

run_step() {
  local label="$1"
  shift
  echo "[check_all] START: ${label}"
  if "$@"; then
    echo "[check_all] PASS: ${label}"
  else
    local exit_code=$?
    echo "[check_all] FAIL(${exit_code}): ${label}"
    status=1
  fi
  echo
}

require_cmd_or_fail() {
  local cmd="$1"
  local hint="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    return 0
  fi
  echo "[check_all] FAIL: missing command '${cmd}'"
  echo "[check_all] hint: ${hint}"
  status=1
  return 1
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "[check_all] FAIL: missing command 'python3'"
  echo "[check_all] hint: install python3 before running checks."
  exit 1
fi

run_step "python3 scripts/check_router_style.py" python3 scripts/check_router_style.py

if python3 -m pytest --version >/dev/null 2>&1; then
  run_step "python3 -m pytest -q backend/tests" python3 -m pytest -q backend/tests
else
  echo "[check_all] FAIL: pytest is not available for python3"
  echo "[check_all] hint: install backend test dependencies, for example 'cd backend && python3 -m pip install -r requirements.txt pytest'."
  echo
  status=1
fi

if require_cmd_or_fail "npm" "install Node.js and npm first."; then
  for app in frontend-trading frontend-notes frontend-monitor frontend-ledger; do
    if [[ ! -f "${ROOT_DIR}/${app}/package.json" ]]; then
      echo "[check_all] FAIL: missing package.json in ${app}"
      status=1
      echo
      continue
    fi
    if [[ ! -d "${ROOT_DIR}/${app}/node_modules" ]]; then
      echo "[check_all] FAIL: dependencies not installed in ${app}"
      echo "[check_all] hint: run 'cd ${app} && npm install' first."
      status=1
      echo
      continue
    fi
    run_step "npm run build (${app})" bash -lc "cd '$ROOT_DIR/${app}' && npm run build"
  done
fi

run_step "bash scripts/check_naming.sh" bash scripts/check_naming.sh
run_step "bash scripts/check_deploy.sh" bash scripts/check_deploy.sh
run_step "python3 scripts/check_runtime_size.py" python3 scripts/check_runtime_size.py

if [[ "$status" -ne 0 ]]; then
  echo "[check_all] result: FAILED"
  exit 1
fi

echo "[check_all] result: PASSED"
