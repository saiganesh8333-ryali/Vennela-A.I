"""Standalone performance and latency benchmark harness."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from statistics import fmean
import sys
import time
from typing import Callable, Iterable, Sequence

from .contracts import LLMRequest, LLMResponse, RoutingError
from .gateway import Gateway
from .router import LLMRouter


@dataclass(frozen=True)
class BenchmarkReport:
    name: str
    runs: int
    mean_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    mean_ttft_ms: float | None
    success_rate: float
    timeout_rate: float
    fallback_rate: float
    error_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "runs": self.runs,
            "mean_latency_ms": round(self.mean_latency_ms, 2),
            "p50_latency_ms": round(self.p50_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "mean_ttft_ms": round(self.mean_ttft_ms, 2) if self.mean_ttft_ms is not None else None,
            "success_rate": round(self.success_rate, 4),
            "timeout_rate": round(self.timeout_rate, 4),
            "fallback_rate": round(self.fallback_rate, 4),
            "error_count": self.error_count,
        }


def run_benchmark_suite(
    router: LLMRouter,
    prompts: Sequence[tuple[str, str]],  # (name, prompt_text)
    runs_per_prompt: int = 5,
    streaming: bool = False,
) -> dict[str, BenchmarkReport]:
    reports: dict[str, BenchmarkReport] = {}

    for name, prompt_text in prompts:
        latencies: list[float] = []
        ttfts: list[float] = []
        successes = 0
        timeouts = 0
        fallbacks = 0
        errors = 0

        req = LLMRequest(prompt=prompt_text, streaming=streaming)

        for _ in range(max(1, runs_per_prompt)):
            t0 = time.perf_counter()
            try:
                if streaming:
                    stream_iter = router.stream(req)
                    first = next(stream_iter)
                    if first.ttft_ms is not None:
                        ttfts.append(first.ttft_ms)
                    for _ in stream_iter:
                        pass
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    latencies.append(elapsed_ms)
                    successes += 1
                else:
                    resp = router.generate(req)
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    latencies.append(elapsed_ms)
                    successes += 1
                    if resp.fallback_used:
                        fallbacks += 1
            except RoutingError as exc:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                latencies.append(elapsed_ms)
                errors += 1
                if exc.failure.kind.value == "timeout":
                    timeouts += 1
            except Exception:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                latencies.append(elapsed_ms)
                errors += 1

        total_runs = len(latencies)
        sorted_lats = sorted(latencies) if latencies else [0.0]

        def percentile(p: float) -> float:
            idx = min(len(sorted_lats) - 1, int(len(sorted_lats) * p))
            return sorted_lats[idx]

        reports[name] = BenchmarkReport(
            name=name,
            runs=total_runs,
            mean_latency_ms=fmean(sorted_lats) if sorted_lats else 0.0,
            p50_latency_ms=percentile(0.50),
            p95_latency_ms=percentile(0.95),
            p99_latency_ms=percentile(0.99),
            mean_ttft_ms=fmean(ttfts) if ttfts else None,
            success_rate=successes / total_runs if total_runs else 0.0,
            timeout_rate=timeouts / total_runs if total_runs else 0.0,
            fallback_rate=fallbacks / total_runs if total_runs else 0.0,
            error_count=errors,
        )

    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM Router Performance Benchmark Harness")
    parser.add_argument("--mock", action="store_true", help="use deterministic mock providers")
    parser.add_argument("--real", action="store_true", help="use real providers with env keys")
    parser.add_argument("--runs", type=int, default=3, help="number of iterations per benchmark case")
    parser.add_argument("--streaming", action="store_true", help="benchmark streaming TTFT and duration")
    args = parser.parse_args()

    use_mock = args.mock or (not args.real)
    gateway = Gateway.create(mock=use_mock)

    prompts = [
        ("tiny_fast", "What is 2 + 2?"),
        ("coding_task", "Write a Python function to binary search an array"),
        ("reasoning_task", "Prove step by step why square root of 2 is irrational"),
        ("conversation", "Hello! Can you help summarize today's status?"),
    ]

    print(f"Running LLM Router Benchmark (mode={'MOCK' if use_mock else 'REAL'}, runs={args.runs})...")
    reports = run_benchmark_suite(gateway.router, prompts, runs_per_prompt=args.runs, streaming=args.streaming)

    output = {k: v.to_dict() for k, v in reports.items()}
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
