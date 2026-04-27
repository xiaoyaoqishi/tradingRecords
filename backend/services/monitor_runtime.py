from __future__ import annotations

from collections import deque
from datetime import datetime
import os
import platform
import threading
import time as _time
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Query, Request
import httpx
import psutil
from sqlalchemy.orm import Session

from core import context
from core.db import SessionLocal, get_db
from core.security import ensure_admin
from models import BrowseLog, MonitorSite, MonitorSiteResult
from schemas.monitor import MonitorSiteCreateBody, MonitorSiteUpdateBody


_monitor_history: deque = deque(maxlen=720)
_prev_net = psutil.net_io_counters()
_prev_disk_io = psutil.disk_io_counters()
_prev_ts = _time.time()
_net_speed = {"up": 0.0, "down": 0.0}
_disk_speed = {"read": 0.0, "write": 0.0}
_MONITOR_RUNTIME_INITIALIZED = False


def _current_username() -> str:
    return context.username()


def _current_role() -> str:
    return context.role()


def _current_is_admin() -> bool:
    return context.is_admin()


def _require_admin():
    ensure_admin(is_admin=_current_is_admin())


def _write_browse_log(
    db: Session,
    *,
    username: str,
    role: str,
    event_type: str,
    path: str,
    module: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    detail: Optional[str] = None,
):
    normalized_role = (role or "").strip().lower() or "user"
    if normalized_role == "admin":
        return
    db.add(
        BrowseLog(
            username=(username or "").strip() or "unknown",
            role=normalized_role,
            event_type=(event_type or "").strip() or "action",
            path=(path or "").strip() or "/",
            module=(module or "").strip() or None,
            ip=(ip or "").strip() or None,
            user_agent=(user_agent or "").strip() or None,
            detail=(detail or "").strip() or None,
        )
    )


def _bytes_fmt(b):
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} PB"


def _seconds_fmt(s):
    d, s = divmod(int(s), 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    parts = []
    if d:
        parts.append(f"{d}天")
    if h:
        parts.append(f"{h}小时")
    if m:
        parts.append(f"{m}分钟")
    parts.append(f"{s}秒")
    return " ".join(parts)


def _sample():
    global _prev_net, _prev_disk_io, _prev_ts, _net_speed, _disk_speed
    now = _time.time()
    dt = now - _prev_ts
    if dt <= 0:
        dt = 1

    net = psutil.net_io_counters()
    _net_speed = {
        "up": (net.bytes_sent - _prev_net.bytes_sent) / dt,
        "down": (net.bytes_recv - _prev_net.bytes_recv) / dt,
    }
    _prev_net = net

    try:
        dio = psutil.disk_io_counters()
        if dio:
            _disk_speed = {
                "read": (dio.read_bytes - _prev_disk_io.read_bytes) / dt,
                "write": (dio.write_bytes - _prev_disk_io.write_bytes) / dt,
            }
            _prev_disk_io = dio
    except Exception:
        pass

    _prev_ts = now

    cpu_pct = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    _monitor_history.append(
        {
            "ts": datetime.now().strftime("%H:%M:%S"),
            "cpu": cpu_pct,
            "mem": mem.percent,
            "net_up": round(_net_speed["up"] / 1024, 1),
            "net_down": round(_net_speed["down"] / 1024, 1),
        }
    )


def _monitor_loop():
    psutil.cpu_percent(interval=None)
    while True:
        try:
            _sample()
        except Exception:
            pass
        _time.sleep(5)


_monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)


def _check_single_site(site: MonitorSite) -> Dict[str, Any]:
    started = _time.time()
    timeout_sec = max(2, min(60, int(site.timeout_sec or 8)))
    try:
        with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
            resp = client.get(site.url)
            elapsed_ms = int((_time.time() - started) * 1000)
            ok = 200 <= int(resp.status_code) < 400
            return {
                "status_code": int(resp.status_code),
                "response_ms": elapsed_ms,
                "ok": ok,
                "error": None if ok else f"http {resp.status_code}",
            }
    except Exception as exc:
        elapsed_ms = int((_time.time() - started) * 1000)
        return {"status_code": None, "response_ms": elapsed_ms, "ok": False, "error": str(exc)[:500]}


def _site_monitor_loop():
    while True:
        db = SessionLocal()
        try:
            now = datetime.now()
            rows = db.query(MonitorSite).filter(MonitorSite.enabled == True).all()  # noqa: E712
            for site in rows:
                interval_sec = max(10, min(3600, int(site.interval_sec or 60)))
                if site.last_checked_at and (now - site.last_checked_at).total_seconds() < interval_sec:
                    continue
                result = _check_single_site(site)
                site.last_checked_at = now
                site.last_status_code = result["status_code"]
                site.last_response_ms = result["response_ms"]
                site.last_ok = bool(result["ok"])
                site.last_error = result["error"]
                db.add(
                    MonitorSiteResult(
                        site_id=site.id,
                        status_code=result["status_code"],
                        response_ms=result["response_ms"],
                        ok=bool(result["ok"]),
                        error=result["error"],
                    )
                )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        _time.sleep(5)


_site_monitor_thread = threading.Thread(target=_site_monitor_loop, daemon=True)


def init_monitor_runtime() -> None:
    global _MONITOR_RUNTIME_INITIALIZED
    if _MONITOR_RUNTIME_INITIALIZED:
        return
    _monitor_thread.start()
    _site_monitor_thread.start()
    _MONITOR_RUNTIME_INITIALIZED = True


def _get_system_info():
    boot = psutil.boot_time()
    uptime = _time.time() - boot
    hostname = platform.node()
    platform_name = platform.system()
    kernel = platform.release()
    arch = platform.machine()
    try:
        with open("/etc/os-release") as f:
            lines = f.readlines()
        distro = dict(l.strip().split("=", 1) for l in lines if "=" in l)
        os_name = distro.get("PRETTY_NAME", "").strip('"')
    except Exception:
        os_name = f"{platform.system()} {platform.version()}"
    return {
        "hostname": hostname,
        "os": os_name,
        "platform": platform_name,
        "kernel": kernel,
        "arch": arch,
        "uptime": _seconds_fmt(uptime),
        "uptime_seconds": int(uptime),
        "boot_time": datetime.fromtimestamp(boot).strftime("%Y-%m-%d %H:%M:%S"),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _get_cpu_info():
    freq = psutil.cpu_freq()
    try:
        load = os.getloadavg()
        load_1, load_5, load_15 = round(load[0], 2), round(load[1], 2), round(load[2], 2)
    except (AttributeError, OSError):
        load_1 = load_5 = load_15 = 0.0
    temps = {}
    try:
        t = psutil.sensors_temperatures()
        if t:
            for name, entries in t.items():
                for e in entries:
                    if e.current > 0:
                        temps[e.label or name] = round(e.current, 1)
    except (AttributeError, Exception):
        pass
    return {
        "percent": psutil.cpu_percent(interval=None),
        "per_cpu": psutil.cpu_percent(interval=None, percpu=True),
        "cores_physical": psutil.cpu_count(logical=False),
        "cores_logical": psutil.cpu_count(logical=True),
        "freq_current": round(freq.current, 0) if freq else None,
        "freq_max": round(freq.max, 0) if freq and freq.max else None,
        "load_1": load_1,
        "load_5": load_5,
        "load_15": load_15,
        "temps": temps,
    }


def _get_memory_info():
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    return {
        "total": vm.total,
        "used": vm.used,
        "available": vm.available,
        "percent": vm.percent,
        "total_fmt": _bytes_fmt(vm.total),
        "used_fmt": _bytes_fmt(vm.used),
        "available_fmt": _bytes_fmt(vm.available),
        "swap_total": sw.total,
        "swap_used": sw.used,
        "swap_percent": sw.percent,
        "swap_total_fmt": _bytes_fmt(sw.total),
        "swap_used_fmt": _bytes_fmt(sw.used),
    }


def _get_disk_info():
    partitions = []
    for p in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(p.mountpoint)
            partitions.append(
                {
                    "device": p.device,
                    "mountpoint": p.mountpoint,
                    "fstype": p.fstype,
                    "total": u.total,
                    "used": u.used,
                    "free": u.free,
                    "percent": u.percent,
                    "total_fmt": _bytes_fmt(u.total),
                    "used_fmt": _bytes_fmt(u.used),
                    "free_fmt": _bytes_fmt(u.free),
                }
            )
        except Exception:
            pass
    return {
        "partitions": partitions,
        "io_read_speed": round(_disk_speed["read"] / 1024 / 1024, 2),
        "io_write_speed": round(_disk_speed["write"] / 1024 / 1024, 2),
    }


def _get_network_info():
    net = psutil.net_io_counters()
    return {
        "bytes_sent": net.bytes_sent,
        "bytes_recv": net.bytes_recv,
        "bytes_sent_fmt": _bytes_fmt(net.bytes_sent),
        "bytes_recv_fmt": _bytes_fmt(net.bytes_recv),
        "speed_up": round(_net_speed["up"] / 1024, 1),
        "speed_down": round(_net_speed["down"] / 1024, 1),
        "speed_up_fmt": _bytes_fmt(_net_speed["up"]) + "/s",
        "speed_down_fmt": _bytes_fmt(_net_speed["down"]) + "/s",
    }


def _get_top_processes(n=10):
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "username"]):
        try:
            info = p.info
            procs.append(
                {
                    "pid": info["pid"],
                    "name": info["name"],
                    "cpu": round(info["cpu_percent"] or 0, 1),
                    "mem": round(info["memory_percent"] or 0, 1),
                    "user": info["username"] or "",
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x["cpu"], reverse=True)
    return procs[:n]


def _get_services_status():
    targets = ["nginx", "uvicorn", "python"]
    result = {}
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            cmdline = " ".join(p.info["cmdline"] or []).lower()
            for svc in targets:
                if svc in p.info["name"].lower() or svc in cmdline:
                    result[svc] = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    for svc in targets:
        if svc not in result:
            result[svc] = False
    return result


def monitor_realtime():
    _require_admin()
    system = _get_system_info()
    cpu = _get_cpu_info()
    memory = _get_memory_info()
    disk = _get_disk_info()
    network = _get_network_info()
    sampled_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    disk_percent = None
    disk_used_gb = None
    disk_total_gb = None
    try:
        partitions = disk.get("partitions") or []
        primary = next((x for x in partitions if x.get("mountpoint") == "/"), None) or (partitions[0] if partitions else None)
        if primary:
            disk_percent = primary.get("percent")
            total = primary.get("total")
            used = primary.get("used")
            if isinstance(total, (int, float)):
                disk_total_gb = round(total / 1024 / 1024 / 1024, 2)
            if isinstance(used, (int, float)):
                disk_used_gb = round(used / 1024 / 1024 / 1024, 2)
    except Exception:
        pass

    load_avg = None
    try:
        raw_load = os.getloadavg()
        load_avg = {
            "1m": round(raw_load[0], 2),
            "5m": round(raw_load[1], 2),
            "15m": round(raw_load[2], 2),
        }
    except (AttributeError, OSError):
        load_avg = None

    return {
        "system": system,
        "cpu": cpu,
        "memory": memory,
        "disk": disk,
        "network": network,
        "processes": _get_top_processes(),
        "services": _get_services_status(),
        "disk_percent": disk_percent,
        "disk_used_gb": disk_used_gb,
        "disk_total_gb": disk_total_gb,
        "load_avg": load_avg,
        "uptime_seconds": system.get("uptime_seconds"),
        "boot_time": system.get("boot_time"),
        "platform": system.get("platform"),
        "architecture": system.get("arch"),
        "sampled_at": sampled_at,
    }


def monitor_history():
    _require_admin()
    return list(_monitor_history)


def monitor_sites(db: Session = Depends(get_db)):
    _require_admin()
    rows = db.query(MonitorSite).order_by(MonitorSite.updated_at.desc(), MonitorSite.id.desc()).all()
    return [
        {
            "id": x.id,
            "name": x.name,
            "url": x.url,
            "enabled": bool(x.enabled),
            "interval_sec": x.interval_sec,
            "timeout_sec": x.timeout_sec,
            "last_checked_at": x.last_checked_at,
            "last_status_code": x.last_status_code,
            "last_response_ms": x.last_response_ms,
            "last_ok": x.last_ok,
            "last_error": x.last_error,
            "created_at": x.created_at,
            "updated_at": x.updated_at,
        }
        for x in rows
    ]


def create_monitor_site(payload: MonitorSiteCreateBody, request: Request, db: Session = Depends(get_db)):
    _require_admin()
    name = (payload.name or "").strip()
    url = (payload.url or "").strip()
    if not name:
        raise HTTPException(400, "name 不能为空")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "url 必须以 http:// 或 https:// 开头")
    row = MonitorSite(
        name=name,
        url=url,
        enabled=bool(payload.enabled),
        interval_sec=max(10, min(3600, int(payload.interval_sec or 60))),
        timeout_sec=max(2, min(60, int(payload.timeout_sec or 8))),
    )
    db.add(row)
    _write_browse_log(
        db,
        username=_current_username(),
        role=_current_role(),
        event_type="action",
        path="/api/monitor/sites",
        module="monitor_site",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail=f"create site {name}",
    )
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id}


def update_monitor_site(site_id: int, payload: MonitorSiteUpdateBody, request: Request, db: Session = Depends(get_db)):
    _require_admin()
    row = db.query(MonitorSite).filter(MonitorSite.id == site_id).first()
    if not row:
        raise HTTPException(404, "site not found")
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        row.name = (updates.get("name") or "").strip() or row.name
    if "url" in updates:
        url = (updates.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise HTTPException(400, "url 必须以 http:// 或 https:// 开头")
        row.url = url
    if "enabled" in updates:
        row.enabled = bool(updates.get("enabled"))
    if "interval_sec" in updates and updates.get("interval_sec") is not None:
        row.interval_sec = max(10, min(3600, int(updates.get("interval_sec"))))
    if "timeout_sec" in updates and updates.get("timeout_sec") is not None:
        row.timeout_sec = max(2, min(60, int(updates.get("timeout_sec"))))
    _write_browse_log(
        db,
        username=_current_username(),
        role=_current_role(),
        event_type="action",
        path=f"/api/monitor/sites/{site_id}",
        module="monitor_site",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail=f"update site {row.name}",
    )
    db.commit()
    return {"ok": True}


def delete_monitor_site(site_id: int, request: Request, db: Session = Depends(get_db)):
    _require_admin()
    row = db.query(MonitorSite).filter(MonitorSite.id == site_id).first()
    if not row:
        raise HTTPException(404, "site not found")
    db.query(MonitorSiteResult).filter(MonitorSiteResult.site_id == site_id).delete(synchronize_session=False)
    db.delete(row)
    _write_browse_log(
        db,
        username=_current_username(),
        role=_current_role(),
        event_type="action",
        path=f"/api/monitor/sites/{site_id}",
        module="monitor_site",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail=f"delete site {site_id}",
    )
    db.commit()
    return {"ok": True}


def monitor_site_results(site_id: int, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    _require_admin()
    rows = (
        db.query(MonitorSiteResult)
        .filter(MonitorSiteResult.site_id == site_id)
        .order_by(MonitorSiteResult.created_at.desc(), MonitorSiteResult.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": x.id,
            "site_id": x.site_id,
            "status_code": x.status_code,
            "response_ms": x.response_ms,
            "ok": bool(x.ok),
            "error": x.error,
            "created_at": x.created_at,
        }
        for x in rows
    ]
