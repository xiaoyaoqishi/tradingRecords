#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import ModuleType


ROOT_DIR = Path(__file__).resolve().parents[1]
CHECK_RUNTIME_SIZE_FILE = ROOT_DIR / "scripts" / "check_runtime_size.py"
ALLOWED_RUNTIME_FUNCTIONS = {
    "_apply_owner_role_scope",
    "_cleanup_old_browse_logs",
    "_column_names",
    "_current_is_admin",
    "_current_role",
    "_current_username",
    "_ensure_sqlite_column",
    "_index_links_for_existing_notes",
    "_init_default_notebooks",
    "_maintenance_loop",
    "_migrate_legacy_schema",
    "_migrate_reviews_to_review_sessions",
    "_owner_role_filter_for_admin",
    "_owner_role_value_for_create",
    "_rebuild_ledger_schema_if_incompatible",
    "_require_admin",
    "_table_exists",
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


def _find_non_whitelisted_function_defs(runtime_file: Path) -> list[tuple[int, str]]:
    tree = ast.parse(runtime_file.read_text(encoding="utf-8-sig"), filename=str(runtime_file))
    violations: list[tuple[int, str]] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in ALLOWED_RUNTIME_FUNCTIONS:
            violations.append((node.lineno, node.name))
    return violations


def main() -> int:
    size_module = _load_check_runtime_size_module()
    runtime_file = Path(size_module.RUNTIME_FILE)
    max_lines = int(size_module.MAX_RUNTIME_LINES)

    failures: list[str] = []
    if not runtime_file.exists():
        failures.append(f"missing file: {runtime_file}")
    else:
        line_count = _runtime_line_count(runtime_file)
        if line_count > max_lines:
            failures.append(
                f"runtime.py line count {line_count} exceeds allowed max {max_lines}"
            )

        violations = _find_non_whitelisted_function_defs(runtime_file)
        if violations:
            for lineno, name in violations:
                failures.append(
                    f"line {lineno}: top-level function '{name}' is not registered in "
                    "ALLOWED_RUNTIME_FUNCTIONS"
                )

    if failures:
        for item in failures:
            print(f"[check_runtime_boundaries] FAIL: {item}")
        print(
            "[check_runtime_boundaries] hint: runtime.py 只允许启动、迁移、兼容 glue；"
            "新业务逻辑必须进入对应 backend/services/*_runtime.py。"
        )
        return 1

    print("Runtime boundary checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
