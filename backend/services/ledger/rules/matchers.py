from __future__ import annotations


def text_match(match_mode: str, pattern: str, text: str) -> bool:
    mode = (match_mode or "contains").lower()
    p = (pattern or "").strip().lower()
    t = (text or "").strip().lower()
    if not p:
        return False
    if mode == "exact":
        return t == p
    if mode == "prefix":
        return t.startswith(p)
    if mode == "regex":
        import re

        try:
            return re.search(pattern, text or "", re.IGNORECASE) is not None
        except re.error:
            return False
    return p in t
