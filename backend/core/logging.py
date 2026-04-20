from typing import Optional

from sqlalchemy.orm import Session

from models import BrowseLog

MODULE_MAP = {
    "auth": "登录认证",
    "audit": "审计日志",
    "monitor_home": "网站监控首页",
    "monitor_site": "站点巡检",
    "user_admin": "用户管理",
    "notes": "笔记应用",
    "trading": "交易记录",
}


def normalize_path_detail(path: str, module: Optional[str], detail: Optional[str]) -> tuple[str, Optional[str]]:
    mod = module or ("monitor_home" if path == "/api/monitor/realtime" else None)
    return mod or "", detail.strip() if detail else None


def write_browse_log(db: Session, *, username: str, role: str, event_type: str, path: str, module: Optional[str] = None, ip: Optional[str] = None, user_agent: Optional[str] = None, detail: Optional[str] = None) -> None:
    mod, normalized_detail = normalize_path_detail(path, module, detail)
    db.add(BrowseLog(username=username, role=role, event_type=event_type, path=path, module=mod or None, ip=ip, user_agent=user_agent, detail=normalized_detail))
