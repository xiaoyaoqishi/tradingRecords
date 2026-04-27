#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
PROHIBITED_TRADING_PREFIX = "/api" + "/trading"
ROUTERS_DIR = ROOT_DIR / "backend/routers"
ROOT_PREFIX_EXCEPTIONS = {
    "backend/routers/trading.py": 'APIRouter(prefix="/api", tags=["trading"])',
    "backend/routers/health.py": None,
    "backend/routers/upload.py": None,
}

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

    for path in sorted(ROUTERS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        relative_path = path.relative_to(ROOT_DIR).as_posix()
        content = read_text(path)

        if ".add_api_route" in content:
            line_no = line_number_for(content, ".add_api_route")
            errors.append(f"{relative_path}:{line_no}: router must not use add_api_route")

        uses_root_api_prefix = 'APIRouter(prefix="/api"' in content
        expected_root_prefix = ROOT_PREFIX_EXCEPTIONS.get(relative_path)

        if expected_root_prefix is not None:
            if not uses_root_api_prefix:
                errors.append(f"{relative_path}: expected root /api compatibility prefix")
            elif expected_root_prefix not in content:
                errors.append(f"{relative_path}: compatibility exception must remain {expected_root_prefix}")
        elif relative_path in ROOT_PREFIX_EXCEPTIONS:
            if not uses_root_api_prefix:
                errors.append(f"{relative_path}: expected root /api compatibility prefix")
        elif uses_root_api_prefix:
            line_no = line_number_for(content, 'APIRouter(prefix="/api"')
            errors.append(f'{relative_path}:{line_no}: router must not use APIRouter(prefix="/api")')

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
