#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import ModuleType


ROOT_DIR = Path(__file__).resolve().parents[1]
CHECK_RUNTIME_SIZE_FILE = ROOT_DIR / "scripts" / "check_runtime_size.py"
BANNED_PREFIXES = (
    "create_",
    "update_",
    "delete_",
    "restore_",
    "purge_",
    "list_",
    "get_",
    "import_",
    "search_",
    "count_",
)
ALLOWED_FUNCTION_NAMES = {
    "init_runtime",
}


def _load_check_runtime_size_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_runtime_size", CHECK_RUNTIME_SIZE_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {CHECK_RUNTIME_SIZE_FILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _runtime_line_count(runtime_file: Path) -> int:
    return sum(1 for _ in runtime_file.open("r", encoding="utf-8-sig"))


def _find_banned_function_defs(runtime_file: Path) -> list[tuple[int, str]]:
    tree = ast.parse(runtime_file.read_text(encoding="utf-8-sig"), filename=str(runtime_file))
    violations: list[tuple[int, str]] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name in ALLOWED_FUNCTION_NAMES:
            continue
        if node.name.startswith(BANNED_PREFIXES):
            violations.append((node.lineno, node.name))
    return violations


def main() -> int:
    size_module = _load_check_runtime_size_module()
    runtime_file = Path(size_module.RUNTIME_FILE)
    max_lines = int(size_module.MAX_LINES)

    failures: list[str] = []
    if not runtime_file.exists():
        failures.append(f"missing file: {runtime_file}")
    else:
        line_count = _runtime_line_count(runtime_file)
        if line_count > max_lines:
            failures.append(
                f"runtime.py line count {line_count} exceeds allowed max {max_lines}"
            )

        violations = _find_banned_function_defs(runtime_file)
        if violations:
            failures.append("business-style top-level function definitions found in backend/services/runtime.py")
            for lineno, name in violations:
                failures.append(f"line {lineno}: def {name}(...)")

    if failures:
        for item in failures:
            print(f"[check_runtime_boundaries] FAIL: {item}")
        print(
            "[check_runtime_boundaries] hint: 新业务逻辑必须放入对应 "
            "backend/services/*_runtime.py，不得写回 backend/services/runtime.py。"
        )
        return 1

    print("Runtime boundary checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
