#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""efinance-cli 全量真实 API 回归测试。

覆盖所有 CLI 命令、所有后端、所有模式，记录真实输出、耗时和失败率。
输出 JSON 结果文件供 HTML 报告生成使用。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
CLI_ENTRY = ["-m", "efinance_cli"]
OUTPUT_JSON = PROJECT_ROOT / "docs" / "20260601-raw-results.json"
TIMEOUT_SECONDS = 90  # 单条命令最大执行秒数
WATCH_TIMEOUT = 15    # watch 模式最大秒数
TZ = timezone(timedelta(hours=8))  # Asia/Shanghai

# ---------------------------------------------------------------------------
# 测试用例定义
# ---------------------------------------------------------------------------

@dataclass
class TestCase:
    """一条测试用例。"""
    id: str
    command: str                     # 命令路径 (如 "stock price history")
    args: list[str] = field(default_factory=list)
    backend: str = "default"         # explicit backend or "default"/"auto"
    format: str = "table"            # output format
    view: str = "observation"        # raw or observation
    extra_flags: list[str] = field(default_factory=list)
    category: str = ""               # stock/fund/bond/futures/quote/market/resolve/search
    note: str = ""                   # 备注
    allow_failure: bool = False      # 是否允许失败


def build_test_suite() -> list[TestCase]:
    """构建完整的测试用例集。"""
    tests: list[TestCase] = []

    def add(cmd: str, args: list[str] | None = None, **kw: Any) -> None:
        tests.append(TestCase(
            id=f"{cmd.replace(' ', '-')}-{kw.get('backend', 'default')}-{kw.get('format', 'table')}",
            command=cmd,
            args=args or [],
            **{k: v for k, v in kw.items() if k != 'backend_override'},
        ))

    # ---- search ----
    add("search", ["--query", "平安银行", "--result-count", "3"], category="search", note="基础搜索")
    add("search", ["--query", "平安银行", "--result-count", "3", "--format", "json"], format="json", category="search", note="JSON 格式搜索")
    add("search", ["--query", "AAPL", "--result-count", "3", "--backend", "yfinance"], backend="yfinance", category="search", note="yfinance 搜索美股", allow_failure=True)
    add("search local", ["--query", "平安", "--result-count", "3"], category="search", note="本地缓存搜索")
    add("search local", ["--query", "平安", "--result-count", "3", "--format", "json"], format="json", category="search", note="本地缓存搜索 JSON")

    # ---- stock group ----
    stock_hist = ["--symbols", "000001", "--start-date", "20250601", "--end-date", "20250603"]
    add("stock price history", stock_hist, category="stock", note="股票历史 K 线 (默认)")
    add("stock price history", stock_hist + ["--backend", "efinance"], backend="efinance", category="stock", note="efinance")
    add("stock price history", stock_hist + ["--backend", "akshare"], backend="akshare", category="stock", note="akshare")
    add("stock price history", stock_hist + ["--backend", "yfinance", "--symbols", "AAPL"], backend="yfinance", category="stock", note="yfinance", allow_failure=True)
    add("stock price history", stock_hist + ["--backend", "auto"], backend="auto", category="stock", note="auto 兜底")
    add("stock price history", stock_hist + ["--format", "json"], format="json", category="stock", note="JSON 格式")

    add("stock price latest", ["--symbols", "000001"], category="stock", note="最新行情")
    add("stock price latest", ["--symbols", "000001", "--backend", "efinance"], backend="efinance", category="stock")
    add("stock price latest", ["--symbols", "000001", "--backend", "yfinance", "--symbols", "AAPL"], backend="yfinance", category="stock", allow_failure=True)
    add("stock price latest", ["--symbols", "000001", "--backend", "auto"], backend="auto", category="stock")

    add("stock price live", ["--market", "A_stock"], category="stock", note="A股实时行情")
    add("stock price live", ["--market", "A_stock", "--backend", "efinance"], backend="efinance", category="stock")
    add("stock price live", ["--market", "A_stock", "--backend", "akshare"], backend="akshare", category="stock")
    add("stock price live", ["--market", "A_stock", "--limit", "5"], category="stock", note="限制 5 行")

    add("stock price snapshot", ["--symbols", "000001"], category="stock", note="行情快照")
    add("stock price snapshot", ["--symbols", "000001", "--backend", "yfinance", "--symbols", "AAPL"], backend="yfinance", category="stock", allow_failure=True)

    add("stock profile", ["--symbols", "000001"], category="stock", note="股票资料")
    add("stock profile", ["--symbols", "000001", "--backend", "efinance"], backend="efinance", category="stock")
    add("stock profile", ["--symbols", "000001", "--backend", "akshare"], backend="akshare", category="stock")
    add("stock profile", ["--symbols", "000001", "--backend", "yfinance", "--symbols", "AAPL"], backend="yfinance", category="stock", allow_failure=True)

    add("stock constituents", ["--symbols", "000300"], category="stock", note="指数成分股")
    add("stock sector", ["--symbols", "000001"], category="stock", note="所属板块")
    add("stock trades", ["--symbols", "000001"], category="stock", note="成交明细")
    add("stock report-dates", [], category="stock", note="报告期", allow_failure=True)  # 可能数据量大
    add("stock ipo latest", [], category="stock", note="IPO 审核")
    add("stock leaderboard daily", ["--start-date", "20250530", "--end-date", "20250530"], category="stock", note="龙虎榜")
    add("stock performance quarterly", [], category="stock", note="季度表现")
    add("stock holders top10", ["--symbols", "000001"], category="stock", note="前十大股东")
    add("stock holders latest-count", ["--symbols", "000001"], category="stock", note="股东户数")
    add("stock flow history", ["--symbols", "000001"], category="stock", note="历史资金流")
    add("stock flow today", ["--symbols", "000001"], category="stock", note="日内资金流")

    # ---- fund group ----
    add("fund nav history", ["--symbol", "161725"], category="fund", note="基金净值")
    add("fund nav history", ["--symbol", "161725", "--backend", "efinance"], backend="efinance", category="fund")
    add("fund nav history", ["--symbol", "161725", "--backend", "akshare"], backend="akshare", category="fund")
    add("fund nav history", ["--symbol", "161725", "--format", "json"], format="json", category="fund")

    add("fund profile", ["--symbol", "161725"], category="fund", note="基金资料")
    add("fund catalog", ["--limit", "3"], category="fund", note="基金名录 (限 3 条)")
    add("fund managers", ["--symbol", "161725"], category="fund", note="管理人")
    add("fund estimate live", ["--symbol", "161725"], category="fund", note="实时估算")
    add("fund performance period", ["--symbol", "161725"], category="fund", note="阶段表现")
    add("fund disclosure dates", ["--symbol", "161725"], category="fund", note="披露日期")
    add("fund allocation industry", ["--symbol", "161725"], category="fund", note="行业分布")
    add("fund allocation position", ["--symbol", "161725"], category="fund", note="持仓占比")
    add("fund allocation types", ["--symbol", "161725"], category="fund", note="类型占比")
    add("fund nav history-batch", ["--symbols", "161725", "--symbols", "110022"], category="fund", note="批量净值")

    # ---- bond group ----
    add("bond catalog", ["--limit", "3"], category="bond", note="债券名录")
    add("bond price history", ["--symbols", "019641", "--start-date", "20250501", "--end-date", "20250530"], category="bond", note="债券 K 线")
    add("bond price live", ["--limit", "5"], category="bond", note="债券实时")
    add("bond profile", ["--symbol", "019641"], category="bond", note="债券资料")
    add("bond trades", ["--symbol", "019641"], category="bond", note="债券成交")
    add("bond flow history", ["--symbol", "019641"], category="bond", note="债券资金流", allow_failure=True)
    add("bond flow today", ["--symbol", "019641"], category="bond", note="债券日内资金流", allow_failure=True)

    # ---- futures group ----
    add("futures catalog", ["--limit", "3"], category="futures", note="期货名录")
    add("futures price history", ["--symbols", "IH888"], category="futures", note="期货 K 线")
    add("futures price live", ["--limit", "5"], category="futures", note="期货实时")
    add("futures trades", ["--symbol", "IH888"], category="futures", note="期货成交")

    # ---- quote group ----
    add("quote price history", ["--quote-id", "1.000001", "--start-date", "20250501", "--end-date", "20250530"], category="quote", note="通用历史行情")
    add("quote price history", ["--quote-id", "1.000001", "--backend", "efinance"], backend="efinance", category="quote")
    add("quote price history", ["--quote-id", "AAPL", "--backend", "yfinance"], backend="yfinance", category="quote", allow_failure=True)

    add("quote price latest", ["--quote-ids", "1.000001"], category="quote", note="通用最新行情")
    add("quote price latest", ["--quote-ids", "1.000001", "--backend", "efinance"], backend="efinance", category="quote")
    add("quote price latest", ["--quote-ids", "AAPL", "--backend", "yfinance"], backend="yfinance", category="quote", allow_failure=True)

    add("quote profile", ["--quote-id", "1.000001"], category="quote", note="通用资料")
    add("quote trades", ["--quote-id", "1.000001"], category="quote", note="通用成交")
    add("quote flow history", ["--quote-id", "1.000001"], category="quote", note="通用资金流")
    add("quote flow today", ["--quote-id", "1.000001"], category="quote", note="通用日内资金流")

    # ---- market group ----
    add("market price live", ["--market", "A_stock", "--limit", "5"], category="market", note="市场实时行情")

    # ---- resolve group ----
    add("resolve quote-id", ["--symbol", "000001"], category="resolve", note="解析 quote_id")
    add("resolve quote-id", ["--symbol", "000001", "--format", "json"], format="json", category="resolve")

    # ---- runtime options 综合测试 ----
    add("stock price history", stock_hist + ["--format", "csv"], format="csv", category="stock", note="CSV 格式")
    add("stock price history", stock_hist + ["--view", "raw"], view="raw", category="stock", note="raw 视图")
    add("stock price history", stock_hist + ["--full"], extra_flags=["--full"], category="stock", note="完整输出")
    add("stock price history", stock_hist + ["--transpose"], extra_flags=["--transpose"], category="stock", note="转置输出")
    add("stock price history", stock_hist + ["--indicator-level", "full"], extra_flags=["--indicator-level", "full"], category="stock", note="全量指标")
    add("stock price history", stock_hist + ["--no-index"], extra_flags=["--no-index"], category="stock", note="无索引")

    return tests


# ---------------------------------------------------------------------------
# 执行引擎
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    """单条测试的执行结果。"""
    id: str
    command: str
    backend: str
    format: str
    category: str
    note: str
    exit_code: int
    elapsed_ms: int
    stdout: str
    stderr: str
    success: bool
    error: str = ""


def run_test(tc: TestCase) -> TestResult:
    """执行一条测试用例并返回结果。"""
    cmd_parts = [str(VENV_PYTHON)] + CLI_ENTRY + tc.command.split()
    cmd_parts.extend(tc.args)
    if tc.backend not in ("default", "auto"):
        cmd_parts.extend(["--backend", tc.backend])
    elif tc.backend == "auto":
        cmd_parts.extend(["--backend", "auto"])
    if tc.format != "table":
        cmd_parts.extend(["--format", tc.format])
    if tc.view != "observation":
        cmd_parts.extend(["--view", tc.view])
    if tc.extra_flags:
        cmd_parts.extend(tc.extra_flags)

    timeout = WATCH_TIMEOUT if "watch" in tc.command else TIMEOUT_SECONDS
    start = time.perf_counter()

    try:
        proc = subprocess.run(
            cmd_parts,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        elapsed = int((time.perf_counter() - start) * 1000)
        stdout = proc.stdout
        stderr = proc.stderr
        exit_code = proc.returncode
        success = exit_code == 0
        error = ""
    except subprocess.TimeoutExpired:
        elapsed = int((time.perf_counter() - start) * 1000)
        stdout = ""
        stderr = f"TIMEOUT after {timeout}s"
        exit_code = -1
        success = False
        error = f"超时 ({timeout}s)"
    except Exception:
        elapsed = int((time.perf_counter() - start) * 1000)
        stdout = ""
        stderr = traceback.format_exc()
        exit_code = -2
        success = False
        error = f"执行异常: {traceback.format_exc()[:200]}"

    # 截断超长输出
    max_output = 20000
    if len(stdout) > max_output:
        stdout = stdout[:max_output] + f"\n\n... [截断，原始长度 {len(stdout)} 字符]"
    if len(stderr) > max_output:
        stderr = stderr[:max_output] + f"\n\n... [截断，原始长度 {len(stderr)} 字符]"

    return TestResult(
        id=tc.id,
        command=tc.command,
        backend=tc.backend,
        format=tc.format,
        category=tc.category,
        note=tc.note,
        exit_code=exit_code,
        elapsed_ms=elapsed,
        stdout=stdout,
        stderr=stderr,
        success=success,
        error=error,
    )


def main() -> None:
    suite = build_test_suite()
    print(f"测试用例总数: {len(suite)}")

    results: list[dict[str, Any]] = []
    stats = {"total": 0, "passed": 0, "failed": 0, "timeout": 0, "error": 0}
    category_stats: dict[str, dict] = {}

    start_time = datetime.now(TZ)

    for i, tc in enumerate(suite):
        print(f"\n[{i+1}/{len(suite)}] {tc.command} ({tc.backend}/{tc.format}) {tc.note}")
        result = run_test(tc)

        # 统计
        stats["total"] += 1
        if result.exit_code == 0:
            stats["passed"] += 1
            status = "OK"
        elif result.exit_code == -1:
            stats["timeout"] += 1
            status = "TIMEOUT"
        else:
            stats["failed"] += 1
            if tc.allow_failure:
                status = "FAIL (允许)"
            else:
                status = "FAIL"

        # 分类统计
        cat = tc.category or "other"
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "passed": 0, "failed": 0}
        category_stats[cat]["total"] += 1
        if result.success:
            category_stats[cat]["passed"] += 1
        else:
            category_stats[cat]["failed"] += 1

        print(f"  → {status} ({result.elapsed_ms}ms)")

        results.append(asdict(result))

    end_time = datetime.now(TZ)

    # 汇总
    summary = {
        "test_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": (end_time - start_time).total_seconds(),
        "total": stats["total"],
        "passed": stats["passed"],
        "failed": stats["failed"],
        "timeout": stats["timeout"],
        "pass_rate": round(stats["passed"] / max(stats["total"], 1) * 100, 1),
        "category_stats": category_stats,
    }

    output = {
        "summary": summary,
        "results": results,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入: {OUTPUT_JSON}")
    print(f"通过: {summary['passed']}/{summary['total']} ({summary['pass_rate']}%)")
    print(f"失败: {summary['failed']}, 超时: {summary['timeout']}")


if __name__ == "__main__":
    main()
