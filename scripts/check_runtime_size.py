#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
RUNTIME_FILE = ROOT_DIR / "backend" / "services" / "runtime.py"
CURRENT_BASELINE_LINES = 510
MAX_RUNTIME_LINES = 550


def main() -> int:
    if os.environ.get("RUNTIME_SIZE_ALLOW_GROWTH") == "1":
        print("[check_runtime_size] skipped: RUNTIME_SIZE_ALLOW_GROWTH=1")
        return 0

    if not RUNTIME_FILE.exists():
        print(f"[check_runtime_size] FAIL: missing file: {RUNTIME_FILE}")
        return 1

    line_count = sum(1 for _ in RUNTIME_FILE.open("r", encoding="utf-8-sig"))
    print(f"[check_runtime_size] current lines: {line_count}")
    print(f"[check_runtime_size] baseline lines: {CURRENT_BASELINE_LINES}")
    print(f"[check_runtime_size] hard max lines: {MAX_RUNTIME_LINES}")

    if line_count > MAX_RUNTIME_LINES:
        print("[check_runtime_size] FAIL: runtime.py grew beyond the hard max ceiling")
        print("[check_runtime_size] hint: split logic out of backend/services/runtime.py")
        print("[check_runtime_size] hint: run python3 scripts/check_runtime_boundaries.py for boundary details")
        print("[check_runtime_size] hint: temporary bypass is available via RUNTIME_SIZE_ALLOW_GROWTH=1")
        return 1

    if line_count > CURRENT_BASELINE_LINES:
        print(
            "[check_runtime_size] WARN: runtime.py is above baseline; confirm this is only "
            "compatibility glue, not business logic."
        )

    print("[check_runtime_size] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
