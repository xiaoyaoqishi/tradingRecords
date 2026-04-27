#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
PROHIBITED_TRADING_PREFIX = "/api" + "/trading"

MIGRATED_ROUTER_FILES = [
    "backend/routers/monitor.py",
    "backend/routers/notes.py",
    "backend/routers/notebook.py",
    "backend/routers/todo.py",
    "backend/routers/review.py",
    "backend/routers/review_sessions.py",
    "backend/routers/trade_plans.py",
    "backend/routers/knowledge.py",
    "backend/routers/trading.py",
    "backend/routers/ledger.py",
]

LEGACY_INFRA_ROUTER_FILES = [
    "backend/routers/auth.py",
    "backend/routers/admin.py",
    "backend/routers/audit.py",
    "backend/routers/health.py",
    "backend/routers/upload.py",
    "backend/routers/recycle.py",
    "backend/routers/poem.py",
]

SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "venv",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def line_number_for(content: str, needle: str) -> int:
    index = content.find(needle)
    return content.count("\n", 0, index) + 1 if index >= 0 else 1


def iter_repo_text_files(root_dir: Path):
    for path in root_dir.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        yield path


def main() -> int:
    errors: list[str] = []

    for relative_path in MIGRATED_ROUTER_FILES:
        path = ROOT_DIR / relative_path
        if not path.exists():
            errors.append(f"Missing migrated router file: {relative_path}")
            continue

        content = read_text(path)

        if ".add_api_route" in content:
            line_no = line_number_for(content, ".add_api_route")
            errors.append(f"{relative_path}:{line_no}: migrated router must not use add_api_route")

        uses_root_api_prefix = 'APIRouter(prefix="/api"' in content
        if relative_path == "backend/routers/trading.py":
            if not uses_root_api_prefix:
                errors.append(
                    f'{relative_path}: expected compatibility exception APIRouter(prefix="/api", tags=["trading"])'
                )
            if 'APIRouter(prefix="/api", tags=["trading"])' not in content:
                errors.append(
                    f'{relative_path}: trading compatibility exception must remain APIRouter(prefix="/api", tags=["trading"])'
                )
        elif uses_root_api_prefix:
            line_no = line_number_for(content, 'APIRouter(prefix="/api"')
            errors.append(f'{relative_path}:{line_no}: migrated router must not use APIRouter(prefix="/api")')

    for relative_path in LEGACY_INFRA_ROUTER_FILES:
        path = ROOT_DIR / relative_path
        if not path.exists():
            errors.append(f"Missing legacy infrastructure router file: {relative_path}")
            continue
        print(f"Legacy infrastructure router not yet migrated: {relative_path}")

    for path in iter_repo_text_files(ROOT_DIR):
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        if PROHIBITED_TRADING_PREFIX not in content:
            continue

        relative_path = path.relative_to(ROOT_DIR).as_posix()
        line_no = line_number_for(content, PROHIBITED_TRADING_PREFIX)
        errors.append(
            f"{relative_path}:{line_no}: prohibited trading API prefix detected. "
            f"禁止新增 {PROHIBITED_TRADING_PREFIX}/*，除非单独发起 API v2 迁移。"
        )

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("Router style checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
