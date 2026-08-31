from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def set_request_id(rid: str) -> None:
    _request_id_ctx.set(rid)


def get_request_id() -> str:
    return _request_id_ctx.get()


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


def _build_formatter(fmt: str) -> logging.Formatter:
    if fmt == "json":
        try:
            from pythonjsonlogger.json import JsonFormatter

            return JsonFormatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
                rename={"levelname": "level", "asctime": "timestamp"},
            )
        except Exception:
            fmt = "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"
            return logging.Formatter(fmt)
    fmt = "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"
    return logging.Formatter(fmt)


def configure_logging(level: str = "INFO", fmt: str = "json") -> logging.Logger:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    # remove existing handlers to avoid duplicates on reload
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_build_formatter(fmt))
    handler.addFilter(_RequestIdFilter())
    root.addHandler(handler)
    return logging.getLogger("ultimate_rag")


logger = configure_logging()
