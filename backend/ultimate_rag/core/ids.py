from __future__ import annotations

import time

try:
    import ulid as _ulid  # pyulid2

    def new_id() -> str:
        return str(_ulid.new()).lower()
except Exception:  # pragma: no cover - fallback if pyulid2 absent
    import secrets

    _EPOCH = 1_600_000_000

    def new_id() -> str:
        ms = int((time.time() - _EPOCH) * 1000) & 0xFFFFFFFF
        rand = secrets.token_hex(8)
        return f"{ms:010x}{rand}"
