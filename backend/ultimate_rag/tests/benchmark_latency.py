"""Production benchmark for RAG pipeline latency measurement.

Measures end-to-end latency breakdown for chat streaming requests.
Run against a local or production deployment.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

BASE_URL = os.getenv("RAG_BASE_URL", "http://localhost:8000")
PASSWORD = os.getenv("RAG_BENCH_PASSWORD", "BenchPass123!")
TENANT_BASE = os.getenv("RAG_BENCH_TENANT", "bench_tenant")

QUERIES = [
    "What is the main conclusion?",
    "Explain the methodology used in the study.",
    "Summarize the key findings across all documents.",
    "What are the exact numbers reported in table 3?",
    "Based on previous context, what are the implications?",
]


@dataclass
class StageTiming:
    name: str
    start: float = 0.0
    end: float = 0.0

    @property
    def ms(self) -> float:
        if self.start == 0 or self.end == 0:
            return 0.0
        return (self.end - self.start) * 1000


@dataclass
class BenchmarkResult:
    query: str
    success: bool
    error: str | None = None
    total_ms: float = 0.0
    ttft_ms: float = 0.0
    token_count: int = 0
    tokens_per_sec: float = 0.0
    stages: dict[str, float] = field(default_factory=dict)
    status_code: int | None = None


async def get_token(client: httpx.AsyncClient) -> str | None:
    try:
        suffix = int(__import__("time").time())
        email = f"bench_{suffix}@example.com"
        tenant = f"{TENANT_BASE}_{suffix}"
        r = await client.post(
            "/auth/register",
            json={"email": email, "password": PASSWORD, "tenant_name": tenant},
        )
        if r.status_code == 201:
            return r.json().get("access_token")
        r = await client.post(
            "/auth/login",
            json={"email": email, "password": PASSWORD},
        )
        if r.status_code == 200:
            return r.json().get("access_token")
    except Exception:
        pass
    return None


async def stream_chat(
    client: httpx.AsyncClient,
    token: str,
    query: str,
    stages: dict[str, float],
) -> BenchmarkResult:
    result = BenchmarkResult(query=query, success=False)
    t0 = time.perf_counter()

    try:
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"query": query, "conversation_id": None}

        async with client.stream(
            "POST", "/chat/stream", json=payload, headers=headers, timeout=120.0
        ) as response:
            result.status_code = response.status_code
            if response.status_code != 200:
                body = await response.aread()
                result.error = body.decode()[:300]
                result.total_ms = (time.perf_counter() - t0) * 1000
                return result

            reader = response.aiter_raw()
            buffer = ""
            first_token = True
            token_count = 0
            full_text = ""

            async for raw_line in reader:
                line = raw_line.strip()
                if not line:
                    continue
                now = time.perf_counter()
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                etype = event.get("type")
                if etype == "token":
                    if first_token:
                        stages["ttft_ms"] = (now - t0) * 1000
                        first_token = False
                    token_count += len(event.get("data", ""))
                    full_text += event.get("data", "")
                elif etype == "done":
                    stages["done_at_ms"] = (now - t0) * 1000

            result.token_count = token_count
            result.ttft_ms = stages.get("ttft_ms", 0.0)
            total_ms = (time.perf_counter() - t0) * 1000
            result.total_ms = total_ms
            if token_count > 0 and total_ms > 0:
                result.tokens_per_sec = (token_count / total_ms) * 1000
            result.success = True

    except Exception as exc:
        result.error = str(exc)
        result.total_ms = (time.perf_counter() - t0) * 1000

    return result


async def run_benchmark(rounds: int = 3) -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []
    async with httpx.AsyncClient(
        base_url=BASE_URL, follow_redirects=True, timeout=120.0
    ) as client:
        token = await get_token(client)
        if not token:
            print("FATAL: could not obtain auth token")
            return results

        for i in range(rounds):
            for q in QUERIES:
                print(f"  [{i+1}/{rounds}] query: {q[:50]}...")
                r = await stream_chat(client, token, q, {})
                results.append(r)
                print(f"    -> total={r.total_ms:.0f}ms ttft={r.ttft_ms:.0f}ms "
                      f"tokens={r.token_count} tps={r.tokens_per_sec:.1f} "
                      f"success={r.success}")
                if not r.success:
                    print(f"    ERROR: {r.error}")
                await asyncio.sleep(0.5)

    return results


def summarize(results: list[BenchmarkResult]) -> None:
    successful = [r for r in results if r.success]
    if not successful:
        print("No successful results")
        return

    totals = [r.total_ms for r in successful]
    ttfts = [r.ttft_ms for r in successful]
    tps = [r.tokens_per_sec for r in successful if r.tokens_per_sec > 0]

    print("\n=== BENCHMARK SUMMARY ===")
    print(f"Total requests: {len(results)} (success: {len(successful)})")
    print(f"Total latency  P50={sorted(totals)[len(totals)//2]:.0f}ms "
          f"P95={sorted(totals)[int(len(totals)*0.95)]:.0f}ms "
          f"P99={sorted(totals)[int(len(totals)*0.99)]:.0f}ms")
    print(f"TTFT          P50={sorted(ttfts)[len(ttfts)//2]:.0f}ms "
          f"P95={sorted(ttfts)[int(len(ttfts)*0.95)]:.0f}ms "
          f"P99={sorted(ttfts)[int(len(ttfts)*0.99)]:.0f}ms")
    if tps:
        print(f"Tokens/sec    P50={sorted(tps)[len(tps)//2]:.1f} "
              f"P95={sorted(tps)[int(len(tps)*0.95)]:.1f}")
    print("========================\n")


if __name__ == "__main__":
    res = asyncio.run(run_benchmark(rounds=2))
    summarize(res)
