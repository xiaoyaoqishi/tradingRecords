import contextvars

current_username: contextvars.ContextVar[str] = contextvars.ContextVar("current_username", default="xiaoyao")
current_role: contextvars.ContextVar[str] = contextvars.ContextVar("current_role", default="admin")
current_is_admin: contextvars.ContextVar[bool] = contextvars.ContextVar("current_is_admin", default=True)


def username() -> str:
    return current_username.get() or "xiaoyao"


def role() -> str:
    val = (current_role.get() or "admin").strip().lower()
    return val if val in {"admin", "user"} else "user"


def is_admin() -> bool:
    return bool(current_is_admin.get()) or role() == "admin"
