"""网络抖动重试基准脚本。

这个脚本用于对照 raw 调用与 retry 调用在真实 `efinance` 原子请求上的表现，
输出可复跑的 JSON 报告，并支持从命令行调节轮数、抖动率和是否跳过 sleep。
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import efinance
from efinance.utils import MarketType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from opentrade.retry_utils import with_network_retry


DEFAULT_ROUNDS = 30
DEFAULT_FLAKE_RATE = 0.15
DEFAULT_SEED = 20260528


@dataclass(slots=True)
class BenchmarkCase:
    """描述一条真实网络原子调用基准用例。"""

    name: str
    func: Callable[..., Any]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


@dataclass(slots=True)
class AttemptResult:
    """描述单次调用结果。"""

    mode: str
    success: bool
    attempts: int
    duration_seconds: float
    error_type: str | None
    error_message: str | None


def build_cases() -> list[BenchmarkCase]:
    """构造可用于重复对照的真实 efinance 原子调用样本。"""

    return [
        BenchmarkCase(
            name="common.get_latest_quote(105.AAPL)",
            func=efinance.common.get_latest_quote,
            args=("105.AAPL",),
            kwargs={},
        ),
        BenchmarkCase(
            name="utils.search_quote(AAPL, US_stock)",
            func=efinance.utils.search_quote,
            args=("AAPL",),
            kwargs={
                "market_type": MarketType.US_stock,
                "count": 2,
                "use_local": False,
            },
        ),
        BenchmarkCase(
            name="stock.get_quote_history(AAPL, US_stock)",
            func=efinance.stock.get_quote_history,
            args=("AAPL",),
            kwargs={
                "market_type": MarketType.US_stock,
                "beg": "20250501",
                "end": "20250528",
            },
        ),
    ]


def percentile(values: list[float], ratio: float) -> float:
    """计算简单分位数。"""

    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * ratio))))
    return ordered[index]


def run_once(case: BenchmarkCase, mode: str, inject_flake: bool, disable_retry_sleep: bool) -> AttemptResult:
    """执行一次 raw/retry 对照调用。"""

    attempts = 0
    flaked = False

    def counted_call() -> Any:
        nonlocal attempts, flaked
        attempts += 1
        if inject_flake and not flaked:
            flaked = True
            raise ConnectionError("synthetic transient network jitter")
        return case.func(*case.args, **case.kwargs)

    caller = counted_call if mode == "raw" else with_network_retry(counted_call)
    started = time.perf_counter()
    try:
        if disable_retry_sleep and mode == "retry":
            from unittest.mock import patch

            with patch("vortezwohl.func.retry.sleep", return_value=None):
                caller()
        else:
            caller()
        return AttemptResult(
            mode=mode,
            success=True,
            attempts=attempts,
            duration_seconds=time.perf_counter() - started,
            error_type=None,
            error_message=None,
        )
    except Exception as exc:  # noqa: BLE001
        return AttemptResult(
            mode=mode,
            success=False,
            attempts=attempts,
            duration_seconds=time.perf_counter() - started,
            error_type=exc.__class__.__name__,
            error_message=str(exc),
        )


def summarize(case: BenchmarkCase, results: list[AttemptResult]) -> dict[str, Any]:
    """汇总单个用例的 raw/retry 对比结果。"""

    grouped = {
        "raw": [item for item in results if item.mode == "raw"],
        "retry": [item for item in results if item.mode == "retry"],
    }
    summary: dict[str, Any] = {"case": case.name}
    for mode, items in grouped.items():
        durations = [item.duration_seconds for item in items]
        successes = [item for item in items if item.success]
        failures = [item for item in items if not item.success]
        recovered_successes = [item for item in successes if item.attempts > 1]
        attempt_histogram = Counter(item.attempts for item in items)
        error_histogram = Counter(item.error_type for item in failures if item.error_type)
        summary[mode] = {
            "rounds": len(items),
            "successes": len(successes),
            "failures": len(failures),
            "success_rate": len(successes) / len(items) if items else 0.0,
            "failure_rate": len(failures) / len(items) if items else 0.0,
            "recovered_successes": len(recovered_successes),
            "recovered_success_rate": len(recovered_successes) / len(items) if items else 0.0,
            "avg_attempts": statistics.mean(item.attempts for item in items) if items else 0.0,
            "max_attempts": max(item.attempts for item in items) if items else 0,
            "attempt_histogram": dict(sorted(attempt_histogram.items())),
            "error_histogram": dict(error_histogram),
            "avg_duration_seconds": statistics.mean(durations) if durations else 0.0,
            "median_duration_seconds": statistics.median(durations) if durations else 0.0,
            "p95_duration_seconds": percentile(durations, 0.95) if durations else 0.0,
        }

    raw_failures = summary["raw"]["failures"]
    retry_failures = summary["retry"]["failures"]
    summary["comparison"] = {
        "success_rate_delta": summary["retry"]["success_rate"] - summary["raw"]["success_rate"],
        "failure_count_delta": retry_failures - raw_failures,
        "failure_reduction_ratio": (
            (raw_failures - retry_failures) / raw_failures if raw_failures else None
        ),
        "recovered_failures": raw_failures - retry_failures,
    }
    return summary


def benchmark_case(
    case: BenchmarkCase,
    rounds: int,
    rng: random.Random,
    flake_rate: float,
    disable_retry_sleep: bool,
) -> tuple[list[AttemptResult], dict[str, Any]]:
    """对单个用例执行成对 raw/retry 基准。"""

    results: list[AttemptResult] = []
    for round_index in range(rounds):
        inject_flake = rng.random() < flake_rate
        modes = ("raw", "retry") if round_index % 2 == 0 else ("retry", "raw")
        for mode in modes:
            result = run_once(case, mode, inject_flake, disable_retry_sleep)
            results.append(result)
            print(
                json.dumps(
                    {
                        "case": case.name,
                        "round": round_index + 1,
                        "mode": mode,
                        "inject_flake": inject_flake,
                        **asdict(result),
                    },
                    ensure_ascii=False,
                )
            )
    return results, summarize(case, results)


def build_parser() -> argparse.ArgumentParser:
    """构造 benchmark 脚本的命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="efinance 网络抖动 retry benchmark")
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS, help="每个模式执行的轮数")
    parser.add_argument("--flake-rate", type=float, default=DEFAULT_FLAKE_RATE, help="注入瞬时抖动故障的概率")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="控制抖动注入的随机种子")
    parser.add_argument(
        "--disable-retry-sleep",
        action="store_true",
        help="跳过 retry 内部的 sleep，以便缩短基准执行时间",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs"),
        help="JSON 报告输出目录",
    )
    return parser

def main() -> None:
    """运行网络抖动 retry benchmark 并落盘 JSON 报告。"""

    args = build_parser().parse_args()
    rng = random.Random(args.seed)
    started_at = datetime.now().astimezone()
    summaries: list[dict[str, Any]] = []
    all_results: dict[str, list[dict[str, Any]]] = {}

    for case in build_cases():
        print(f"\n### START {case.name} ###")
        results, summary = benchmark_case(
            case=case,
            rounds=args.rounds,
            rng=rng,
            flake_rate=args.flake_rate,
            disable_retry_sleep=args.disable_retry_sleep,
        )
        summaries.append(summary)
        all_results[case.name] = [asdict(item) for item in results]
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    ended_at = datetime.now().astimezone()
    report = {
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "rounds_per_mode": args.rounds,
        "flake_rate": args.flake_rate,
        "seed": args.seed,
        "disable_retry_sleep": args.disable_retry_sleep,
        "summaries": summaries,
        "results": all_results,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"retry-benchmark-{started_at.strftime('%Y%m%d-%H%M%S')}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nREPORT_SAVED={output_path}")


if __name__ == "__main__":
    main()
