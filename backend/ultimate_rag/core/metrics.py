"""In-process metrics counters.

Lightweight, dependency-free metrics so the platform is observable without
Prometheus. The values feed the /metrics endpoint and are used during
evaluations. Counters are process-scoped; in a multi-worker deployment
each worker reports its own counters.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

_lock = Lock()
_counters: dict[str, int] = defaultdict(int)
_gauges: dict[str, float] = {}
_histograms: dict[str, list[float]] = defaultdict(list)


def inc(name: str, amount: int = 1) -> None:
    with _lock:
        _counters[name] += amount


def gauge(name: str, value: float) -> None:
    with _lock:
        _gauges[name] = value


def histogram(name: str, value: float) -> None:
    with _lock:
        _histograms[name].append(value)


class measure:
    """Context manager that records latency in milliseconds under ``name``."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.t0 = 0.0

    def __enter__(self) -> measure:
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc) -> None:
        ms = (time.perf_counter() - self.t0) * 1000
        histogram(self.name, ms)


def get_metrics_snapshot() -> dict:
    with _lock:
        return {
            "counters": dict(_counters),
            "gauges": dict(_gauges),
            "histograms": {
                name: {
                    "count": len(vals),
                    "mean_ms": sum(vals) / len(vals) if vals else 0.0,
                    "max_ms": max(vals) if vals else 0.0,
                }
                for name, vals in _histograms.items()
            },
        }


def reset_metrics() -> None:
    with _lock:
        _counters.clear()
        _gauges.clear()
        _histograms.clear()
