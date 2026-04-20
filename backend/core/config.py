import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Settings:
    base_dir: Path = Path(__file__).resolve().parents[1]
    data_dir: Path = Path(__file__).resolve().parents[1] / "data"
    db_name: str = "trading.db"
    auth_cookie: str = "session_token"
    auth_whitelist: tuple[str, ...] = ("/api/auth/login", "/api/auth/check", "/api/auth/setup")
    dev_mode: bool = os.environ.get("DEV_MODE", "0") == "1"
    cookie_secure: bool = os.environ.get("COOKIE_SECURE", "0" if os.environ.get("DEV_MODE", "0") == "1" else "1") == "1"
    timezone: ZoneInfo = ZoneInfo("Asia/Shanghai")
    app_title: str = "交易记录系统"
    app_version: str = "2.0.0-refactor"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
