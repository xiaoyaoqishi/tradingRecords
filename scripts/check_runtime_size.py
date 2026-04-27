#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
RUNTIME_FILE = ROOT_DIR / "backend" / "services" / "runtime.py"
MAX_LINES = 3994


def main() -> int:
    if os.environ.get("RUNTIME_SIZE_ALLOW_GROWTH") == "1":
        print("[check_runtime_size] skipped: RUNTIME_SIZE_ALLOW_GROWTH=1")
        return 0

    if not RUNTIME_FILE.exists():
        print(f"[check_runtime_size] FAIL: missing file: {RUNTIME_FILE}")
        return 1

    line_count = sum(1 for _ in RUNTIME_FILE.open("r", encoding="utf-8-sig"))
    print(f"[check_runtime_size] runtime.py lines: {line_count}")
    print(f"[check_runtime_size] allowed max lines: {MAX_LINES}")

    if line_count > MAX_LINES:
        print("[check_runtime_size] FAIL: runtime.py grew beyond the allowed ceiling")
        print("[check_runtime_size] hint: split logic out of backend/services/runtime.py")
        print("[check_runtime_size] hint: temporary bypass is available via RUNTIME_SIZE_ALLOW_GROWTH=1")
        return 1

    print("[check_runtime_size] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
