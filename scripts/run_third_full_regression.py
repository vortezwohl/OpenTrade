"""第三次全量真实 API 回归执行器。

该脚本独立于现有测试脚本，直接根据当前源码枚举命令面，使用项目
`.venv` 中的解释器真实调用 CLI 与第三方后端 API，并把每条命令的
stdout / stderr 原样落到 JSON 与 HTML 报告中。
"""

from __future__ import annotations

import json
import os
import re
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import click

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from opentrade.backends.factory import list_provider_extension_commands
from opentrade.command_catalog import SHARED_COMMANDS
from opentrade.commands import create_root_command, create_search_command
from scripts.regression_reporting import (
    classify_regression_failure,
    detect_auto_fallback,
    extract_backend_meta_from_stdout,
)

TZ = ZoneInfo("Asia/Shanghai")
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
CLI_PREFIX = [str(VENV_PYTHON), "-X", "utf8", "-m", "opentrade"]
DOCS_DIR = PROJECT_ROOT / "docs"
ARTIFACT_DIR = DOCS_DIR / "20260601-third-regression-artifacts"
RESULT_JSON = DOCS_DIR / "20260601-third-regression-results.json"
RAW_JSON = DOCS_DIR / "20260601-第三次测试结论.raw.json"
REPORT_HTML = DOCS_DIR / "20260601-第三次测试结论.html"
TIMEOUT = 150
WATCH_TIMEOUT = 60
REQUIRED_TAGS = {
    "format-json",
    "format-csv",
    "format-tsv",
    "view-raw",
    "watch",
    "output",
    "encoding",
    "indicator-level",
    "trace-window",
    "full",
    "transpose",
    "no-index",
}
RUNTIME_NAMES = {
    "backend_name",
    "format_name",
    "full",
    "transpose",
    "no_index",
    "limit",
    "output_path",
    "encoding",
    "indicator_level",
    "view_mode",
    "trace_window",
    "watch",
    "interval",
    "count",
    "clear_screen",
}
ERROR_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))")


def now_iso() -> str:
    """返回上海时区时间。"""

    return datetime.now(TZ).isoformat(timespec="seconds")


def make_case(
    path: str,
    backend: str | None,
    tokens: list[str],
    note: str,
    tags: list[str] | None = None,
    timeout: int = TIMEOUT,
    artifacts: list[str] | None = None,
) -> dict[str, Any]:
    """构造一条回归用例。"""

    return {
        "id": f"{path.replace(' ', '-')}__{backend or 'default'}",
        "path": path,
        "backend": backend,
        "tokens": tokens,
        "note": note,
        "tags": tags or [],
        "timeout": timeout,
        "artifacts": artifacts or [],
        "category": path.split()[0],
    }


def iter_leaf_paths(command: click.Command, prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    """递归收集 Click 叶子命令路径。"""

    if isinstance(command, click.Group):
        paths: list[tuple[str, ...]] = []
        for child in command.commands.values():
            next_prefix = prefix + ((child.name,) if child.name else ())
            paths.extend(iter_leaf_paths(child, next_prefix))
        return paths
    return [prefix]


def command_lookup() -> dict[str, click.Command]:
    """构建路径到 Click 命令对象的映射。"""

    root = create_root_command()
    lookup: dict[str, click.Command] = {
        "search": create_search_command(),
        "watch": root.commands["watch"],
    }
    for path in iter_leaf_paths(root):
        if not path or " ".join(path) == "watch":
            continue
        current: click.Command = root
        for part in path:
            current = current.commands[part] if isinstance(current, click.Group) else current
        path_text = " ".join(path)
        lookup[path_text] = current
        if path_text == "search local":
            lookup["search local"] = current
    return lookup


def source_matrix() -> dict[str, list[str]]:
    """按源码返回每个命令支持的 backend 列表。"""

    matrix = {"search": ["efinance", "akshare", "yfinance"], "watch": []}
    for definition in SHARED_COMMANDS:
        if definition.command_key == "instrument.search":
            continue
        matrix[" ".join(definition.cli_path)] = [item.value for item in definition.supported_backends]
    for definition in list_provider_extension_commands():
        provider = definition.provider_name.value if definition.provider_name else "unknown"
        matrix[" ".join(definition.cli_path)] = [provider]
    return matrix

def expected_paths() -> set[str]:
    """返回源码层面的全部命令路径。"""

    paths = {"search", "watch"}
    for definition in SHARED_COMMANDS:
        if definition.command_key == "instrument.search":
            continue
        paths.add(" ".join(definition.cli_path))
    for definition in list_provider_extension_commands():
        paths.add(" ".join(definition.cli_path))
    return paths


def business_options(command: click.Command) -> set[str]:
    """提取业务参数名，不含统一运行时参数。"""

    names: set[str] = set()
    for parameter in command.params:
        if isinstance(parameter, click.Option) and parameter.name not in RUNTIME_NAMES:
            names.add(str(parameter.name))
    return names


def present_business_options(command: click.Command, tokens: list[str]) -> set[str]:
    """根据 token 判断本条用例实际覆盖了哪些业务参数。"""

    mapping: dict[str, str] = {}
    for parameter in command.params:
        if not isinstance(parameter, click.Option):
            continue
        if parameter.name in RUNTIME_NAMES:
            continue
        for option_text in parameter.opts:
            mapping[option_text] = str(parameter.name)
        for option_text in parameter.secondary_opts:
            mapping[option_text] = str(parameter.name)
    present = set()
    for token in tokens:
        if token in mapping:
            present.add(mapping[token])
    return present


def build_cases() -> list[dict[str, Any]]:
    """构建全量真实回归矩阵。"""

    stock_csv = (ARTIFACT_DIR / "stock-price-latest-efinance.csv").as_posix()
    fund_dir = (ARTIFACT_DIR / "fund-reports-download").as_posix()
    return [
        make_case("search", None, ["search", "--query", "平安银行", "--result-count", "5"], "默认搜索路由样本。"),
        make_case("search", "auto", ["search", "--query", "平安银行", "--result-count", "5", "--use-local-cache", "--backend", "auto", "--format", "json", "--view", "raw", "--trace-window", "8"], "搜索 auto 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("search", "efinance", ["search", "--query", "平安银行", "--result-count", "5", "--backend", "efinance"], "搜索 efinance 样本。"),
        make_case("search", "akshare", ["search", "--query", "平安银行", "--result-count", "5", "--backend", "akshare"], "搜索 akshare 样本。"),
        make_case("search", "yfinance", ["search", "--query", "AAPL", "--market", "US_stock", "--result-count", "5", "--no-use-local-cache", "--backend", "yfinance", "--format", "json", "--view", "raw", "--trace-window", "8"], "搜索 yfinance 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("search local", "efinance", ["search", "local", "--query", "平安", "--market", "A_stock", "--backend", "efinance"], "本地缓存搜索样本。"),
        make_case("watch", None, ["watch", "--count", "1", "--interval", "0.2", "--no-clear", "stock", "price", "latest", "--symbols", "000001", "--backend", "efinance", "--format", "json", "--view", "raw", "--trace-window", "8"], "顶层 watch 包装器样本。", ["watch", "format-json", "view-raw", "trace-window"], WATCH_TIMEOUT),
        make_case("stock price history", "auto", ["stock", "price", "history", "--symbols", "000001", "--start-date", "20250501", "--end-date", "20250503", "--market", "A_stock", "--backend", "auto", "--format", "json", "--view", "raw", "--trace-window", "8"], "stock history auto。", ["format-json", "view-raw", "trace-window"]),
        make_case("stock price history", "efinance", ["stock", "price", "history", "--symbols", "000001", "--start-date", "20250501", "--end-date", "20250503", "--timeframe", "101", "--adjustment", "1", "--market", "A_stock", "--ignore-errors", "--use-id-cache", "--backend", "efinance", "--indicator-level", "full", "--full"], "stock history efinance 全参数样本。", ["indicator-level", "full"]),
        make_case("stock price history", "akshare", ["stock", "price", "history", "--symbols", "000001", "--start-date", "20250501", "--end-date", "20250503", "--backend", "akshare", "--no-index"], "stock history akshare 样本。", ["no-index"]),
        make_case("stock price history", "yfinance", ["stock", "price", "history", "--symbols", "AAPL", "--start-date", "20250501", "--end-date", "20250503", "--backend", "yfinance", "--format", "json", "--view", "raw", "--trace-window", "8"], "stock history yfinance 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("stock price latest", "auto", ["stock", "price", "latest", "--symbols", "000001", "--backend", "auto", "--format", "json", "--view", "raw", "--trace-window", "8"], "stock latest auto 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("stock price latest", "efinance", ["stock", "price", "latest", "--symbols", "000001", "--backend", "efinance", "--format", "csv", "--output", stock_csv, "--encoding", "utf-8"], "stock latest efinance 输出文件样本。", ["format-csv", "output", "encoding"], artifacts=[stock_csv]),
        make_case("stock price latest", "yfinance", ["stock", "price", "latest", "--symbols", "AAPL", "--backend", "yfinance", "--format", "tsv"], "stock latest yfinance tsv 样本。", ["format-tsv"]),
        make_case("stock price live", "auto", ["stock", "price", "live", "--market", "A_stock", "--backend", "auto", "--format", "json", "--view", "raw", "--trace-window", "8"], "stock live auto 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("stock price live", "efinance", ["stock", "price", "live", "--market", "A_stock", "--backend", "efinance", "--limit", "5"], "stock live efinance 样本。"),
        make_case("stock price live", "akshare", ["stock", "price", "live", "--market", "A_stock", "--backend", "akshare", "--no-index", "--limit", "5"], "stock live akshare 样本。", ["no-index"]),
        make_case("stock price snapshot", "auto", ["stock", "price", "snapshot", "--symbol", "000001", "--backend", "auto", "--format", "json", "--view", "raw", "--trace-window", "8"], "stock snapshot auto 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("stock price snapshot", "efinance", ["stock", "price", "snapshot", "--symbol", "000001", "--backend", "efinance", "--transpose"], "stock snapshot transpose 样本。", ["transpose"]),
        make_case("stock price snapshot", "yfinance", ["stock", "price", "snapshot", "--symbol", "AAPL", "--backend", "yfinance", "--format", "json", "--view", "raw", "--trace-window", "8"], "stock snapshot yfinance 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("stock profile", "auto", ["stock", "profile", "--symbols", "000001", "--backend", "auto", "--format", "json", "--view", "raw", "--trace-window", "8"], "stock profile auto 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("stock profile", "efinance", ["stock", "profile", "--symbols", "000001", "--backend", "efinance", "--full"], "stock profile full 样本。", ["full"]),
        make_case("stock profile", "akshare", ["stock", "profile", "--symbols", "000001", "--backend", "akshare"], "stock profile akshare 样本。"),
        make_case("stock profile", "yfinance", ["stock", "profile", "--symbols", "AAPL", "--backend", "yfinance", "--format", "json", "--view", "raw", "--trace-window", "8"], "stock profile yfinance 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("fund nav history", "auto", ["fund", "nav", "history", "--symbol", "VOO", "--backend", "auto", "--format", "json", "--view", "raw", "--trace-window", "8"], "fund nav auto 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("fund nav history", "efinance", ["fund", "nav", "history", "--symbol", "161725", "--max-pages", "1", "--backend", "efinance"], "fund nav efinance 样本。"),
        make_case("fund nav history", "akshare", ["fund", "nav", "history", "--symbol", "161725", "--backend", "akshare"], "fund nav akshare 样本。"),
        make_case("fund nav history", "yfinance", ["fund", "nav", "history", "--symbol", "VOO", "--backend", "yfinance", "--format", "json", "--view", "raw", "--trace-window", "8"], "fund nav yfinance 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("fund profile", "auto", ["fund", "profile", "--symbols", "161725", "--backend", "auto", "--format", "json", "--view", "raw", "--trace-window", "8"], "fund profile auto 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("fund profile", "efinance", ["fund", "profile", "--symbols", "161725", "--backend", "efinance"], "fund profile efinance 样本。"),
        make_case("fund profile", "yfinance", ["fund", "profile", "--symbols", "VOO", "--backend", "yfinance", "--format", "json", "--view", "raw", "--trace-window", "8"], "fund profile yfinance 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("quote price history", "auto", ["quote", "price", "history", "--symbols", "000001", "--start-date", "20250501", "--end-date", "20250503", "--market", "A_stock", "--backend", "auto", "--format", "json", "--view", "raw", "--trace-window", "8"], "quote history auto 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("quote price history", "efinance", ["quote", "price", "history", "--symbols", "000001", "--start-date", "20250501", "--end-date", "20250503", "--timeframe", "101", "--adjustment", "1", "--market", "A_stock", "--ignore-errors", "--use-id-cache", "--backend", "efinance", "--indicator-level", "full"], "quote history efinance 全参数样本。", ["indicator-level"]),
        make_case("quote price history", "yfinance", ["quote", "price", "history", "--symbols", "AAPL", "--start-date", "20250501", "--end-date", "20250503", "--backend", "yfinance", "--format", "json", "--view", "raw", "--trace-window", "8"], "quote history yfinance 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("quote price latest", "auto", ["quote", "price", "latest", "--quote-ids", "0.000001", "--backend", "auto", "--format", "json", "--view", "raw", "--trace-window", "8"], "quote latest auto 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("quote price latest", "efinance", ["quote", "price", "latest", "--quote-ids", "0.000001", "--backend", "efinance"], "quote latest efinance 样本。"),
        make_case("quote price latest", "yfinance", ["quote", "price", "latest", "--quote-ids", "AAPL", "--backend", "yfinance", "--format", "json", "--view", "raw", "--trace-window", "8"], "quote latest yfinance 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("quote profile", "auto", ["quote", "profile", "--quote-id", "0.000001", "--backend", "auto", "--format", "json", "--view", "raw", "--trace-window", "8"], "quote profile auto 样本。", ["format-json", "view-raw", "trace-window"]),
        make_case("quote profile", "efinance", ["quote", "profile", "--quote-id", "0.000001", "--backend", "efinance"], "quote profile efinance 样本。"),
        make_case("quote profile", "yfinance", ["quote", "profile", "--quote-id", "AAPL", "--backend", "yfinance", "--format", "json", "--view", "raw", "--trace-window", "8"], "quote profile yfinance 样本。", ["format-json", "view-raw", "trace-window"]),        make_case("stock constituents", "efinance", ["stock", "constituents", "--symbol", "000300", "--backend", "efinance"], "指数成分股样本。"),
        make_case("stock flow history", "efinance", ["stock", "flow", "history", "--symbol", "000001", "--backend", "efinance"], "个股资金流历史样本。"),
        make_case("stock flow today", "efinance", ["stock", "flow", "today", "--symbol", "000001", "--backend", "efinance"], "个股资金流当日样本。"),
        make_case("stock holders latest-count", "efinance", ["stock", "holders", "latest-count", "--date", "20250331", "--backend", "efinance", "--limit", "5"], "股东户数样本。"),
        make_case("stock holders top10", "efinance", ["stock", "holders", "top10", "--symbol", "000001", "--top", "5", "--backend", "efinance"], "十大股东样本。"),
        make_case("stock ipo latest", "efinance", ["stock", "ipo", "latest", "--backend", "efinance", "--limit", "5"], "IPO 样本。"),
        make_case("stock leaderboard daily", "efinance", ["stock", "leaderboard", "daily", "--start-date", "20250530", "--end-date", "20250530", "--backend", "efinance"], "龙虎榜样本。"),
        make_case("stock performance quarterly", "efinance", ["stock", "performance", "quarterly", "--date", "20250331", "--backend", "efinance", "--limit", "5"], "季度业绩样本。"),
        make_case("stock report-dates", "efinance", ["stock", "report-dates", "--backend", "efinance", "--limit", "5"], "财报日期样本。"),
        make_case("stock sector", "efinance", ["stock", "sector", "--symbol", "000001", "--backend", "efinance"], "板块归属样本。"),
        make_case("stock trades", "efinance", ["stock", "trades", "--symbol", "000001", "--max-records", "20", "--backend", "efinance"], "股票逐笔成交样本。"),
        make_case("fund nav history-batch", "efinance", ["fund", "nav", "history-batch", "--symbols", "161725", "--symbols", "005827", "--max-pages", "1", "--backend", "efinance", "--format", "json"], "基金净值批量样本。", ["format-json"]),
        make_case("fund catalog", "efinance", ["fund", "catalog", "--fund-type", "全部", "--backend", "efinance", "--limit", "5"], "基金目录样本。"),
        make_case("fund managers", "efinance", ["fund", "managers", "--fund-type", "全部", "--backend", "efinance", "--limit", "5"], "基金经理样本。"),
        make_case("fund estimate live", "efinance", ["fund", "estimate", "live", "--symbols", "161725", "--backend", "efinance"], "基金估值样本。"),
        make_case("fund performance period", "efinance", ["fund", "performance", "period", "--symbol", "161725", "--backend", "efinance"], "基金阶段业绩样本。"),
        make_case("fund disclosure dates", "efinance", ["fund", "disclosure", "dates", "--symbol", "161725", "--backend", "efinance"], "基金披露日期样本。"),
        make_case("fund allocation industry", "efinance", ["fund", "allocation", "industry", "--symbol", "161725", "--dates", "20241231", "--backend", "efinance"], "基金行业配置样本。"),
        make_case("fund allocation position", "efinance", ["fund", "allocation", "position", "--symbol", "161725", "--dates", "20241231", "--backend", "efinance"], "基金持仓配置样本。"),
        make_case("fund allocation types", "efinance", ["fund", "allocation", "types", "--symbol", "161725", "--dates", "20241231", "--backend", "efinance"], "基金资产类型配置样本。"),
        make_case("fund reports download", "efinance", ["fund", "reports", "download", "--symbol", "161725", "--max-files", "1", "--output-dir", fund_dir, "--backend", "efinance"], "基金报告下载样本。", artifacts=[fund_dir]),
        make_case("bond catalog", "efinance", ["bond", "catalog", "--backend", "efinance", "--limit", "5"], "债券目录样本。"),
        make_case("bond flow history", "efinance", ["bond", "flow", "history", "--symbol", "113527", "--backend", "efinance"], "债券资金流历史样本。"),
        make_case("bond flow today", "efinance", ["bond", "flow", "today", "--symbol", "113527", "--backend", "efinance"], "债券资金流当日样本。"),
        make_case("bond price history", "efinance", ["bond", "price", "history", "--symbols", "113527", "--start-date", "20250501", "--end-date", "20250503", "--timeframe", "101", "--adjustment", "1", "--backend", "efinance"], "债券历史行情样本。"),
        make_case("bond price live", "efinance", ["bond", "price", "live", "--backend", "efinance", "--limit", "5"], "债券实时行情样本。"),
        make_case("bond profile", "efinance", ["bond", "profile", "--symbols", "113527", "--backend", "efinance", "--format", "json", "--view", "raw"], "债券资料样本。", ["format-json", "view-raw"]),
        make_case("bond trades", "efinance", ["bond", "trades", "--symbol", "113527", "--max-records", "20", "--backend", "efinance"], "债券逐笔成交样本。"),
        make_case("futures catalog", "efinance", ["futures", "catalog", "--backend", "efinance", "--limit", "5"], "期货目录样本。"),
        make_case("futures price history", "efinance", ["futures", "price", "history", "--quote-ids", "114.jd2606", "--start-date", "20250501", "--end-date", "20250503", "--timeframe", "101", "--adjustment", "1", "--backend", "efinance"], "期货历史行情样本。"),
        make_case("futures price live", "efinance", ["futures", "price", "live", "--backend", "efinance", "--limit", "5"], "期货实时行情样本。"),
        make_case("futures trades", "efinance", ["futures", "trades", "--quote-id", "114.jd2606", "--max-records", "20", "--backend", "efinance"], "期货逐笔成交样本。"),
        make_case("quote flow history", "efinance", ["quote", "flow", "history", "--symbol", "000001", "--backend", "efinance"], "通用行情资金流历史样本。"),
        make_case("quote flow today", "efinance", ["quote", "flow", "today", "--symbol", "000001", "--backend", "efinance"], "通用行情资金流当日样本。"),
        make_case("quote trades", "efinance", ["quote", "trades", "--quote-id", "0.000001", "--max-records", "20", "--backend", "efinance"], "通用行情逐笔成交样本。"),
        make_case("market add", "efinance", ["market", "add", "--market-category", "codex_regression", "--market-id", "999", "--market-name", "Codex-Regression-Market", "--deduplicate", "--backend", "efinance"], "市场注册副作用样本。"),
        make_case("market price live", "efinance", ["market", "price", "live", "--market", "m:105+t:3", "--backend", "efinance", "--limit", "5"], "市场实时行情样本。"),
        make_case("resolve quote-id", None, ["resolve", "quote-id", "--symbol", "000001", "--market", "A_stock"], "resolve 默认路由样本。"),
        make_case("resolve quote-id", "efinance", ["resolve", "quote-id", "--symbol", "000001", "--market", "A_stock", "--use-local-cache", "--ignore-errors", "--backend", "efinance", "--format", "json", "--view", "raw"], "resolve 全参数样本。", ["format-json", "view-raw"]),
        make_case("stock industry boards", "akshare", ["stock", "industry", "boards", "--backend", "akshare", "--limit", "5"], "akshare 行业板块样本。"),
        make_case("quote news", "yfinance", ["quote", "news", "--quote-id", "AAPL", "--result-count", "5", "--backend", "yfinance", "--format", "json", "--view", "raw"], "yfinance 新闻样本。", ["format-json", "view-raw"]),
    ]

def validate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """跑前校验命令、backend、参数和运行模式覆盖。"""

    lookup = command_lookup()
    matrix = source_matrix()
    actual_paths = {case["path"] for case in cases}
    missing_paths = sorted(expected_paths() - actual_paths)
    extra_paths = sorted(actual_paths - expected_paths())
    if missing_paths or extra_paths:
        raise RuntimeError(f"命令覆盖不完整: missing={missing_paths} extra={extra_paths}")

    explicit_hits: dict[str, set[str]] = defaultdict(set)
    auto_hits: set[str] = set()
    option_hits: dict[str, set[str]] = defaultdict(set)
    tags: set[str] = set()
    default_count = 0
    for case in cases:
        backend = case["backend"]
        if backend == "auto":
            auto_hits.add(case["path"])
        elif backend:
            explicit_hits[case["path"]].add(backend)
        else:
            default_count += 1
        option_hits[case["path"]].update(present_business_options(lookup[case["path"]], case["tokens"]))
        tags.update(case["tags"])

    backend_missing: list[str] = []
    shared_count = 0
    explicit_target = 0
    for path, backends in matrix.items():
        if path == "watch":
            continue
        if len(backends) > 1:
            shared_count += 1
            explicit_target += len(backends)
            if path not in auto_hits:
                backend_missing.append(f"{path}: 缺少 auto")
            lost = sorted(set(backends) - explicit_hits.get(path, set()))
            if lost:
                backend_missing.append(f"{path}: 缺少显式 backend {lost}")
        else:
            single = backends[0]
            if single not in explicit_hits.get(path, set()):
                backend_missing.append(f"{path}: 缺少 backend {single}")
    if backend_missing:
        raise RuntimeError("backend 覆盖不完整: " + " | ".join(backend_missing))

    option_total = 0
    option_covered = 0
    option_missing: list[str] = []
    for path, command in lookup.items():
        if path == "watch":
            continue
        expected = business_options(command)
        hit = option_hits.get(path, set())
        option_total += len(expected)
        option_covered += len(expected & hit)
        lost = sorted(expected - hit)
        if lost:
            option_missing.append(f"{path}: {lost}")
    if option_missing:
        raise RuntimeError("业务参数覆盖不完整: " + " | ".join(option_missing))

    missing_tags = sorted(REQUIRED_TAGS - tags)
    if missing_tags:
        raise RuntimeError(f"运行模式覆盖不完整: {missing_tags}")

    return {
        "expected_command_count": len(expected_paths()),
        "shared_auto_target": shared_count,
        "shared_auto_covered": len(auto_hits),
        "explicit_backend_target": explicit_target,
        "explicit_backend_covered": explicit_target,
        "business_option_target": option_total,
        "business_option_covered": option_covered,
        "mode_tags": sorted(tags),
        "default_route_samples": default_count,
    }


def parse_backend_meta(stdout: str) -> dict[str, Any]:
    """? stdout ????????? limit ???"""

    return extract_backend_meta_from_stdout(stdout)


def infer_failure(
    case: dict[str, Any],
    stdout: str,
    stderr: str,
    returncode: int | None,
    status: str,
    meta: dict[str, Any],
    artifacts: list[dict[str, Any]],
) -> tuple[str | None, str | None]:
    """????????????????????"""

    return classify_regression_failure(
        command_path=case["path"],
        requested_backend=case["backend"],
        stdout=stdout,
        stderr=stderr,
        returncode=returncode,
        status=status,
        backend_meta=meta,
        artifact_reports=artifacts,
    )


def detect_fallback(case: dict[str, Any], meta: dict[str, Any]) -> bool:
    """?? auto ????????????? backend?"""

    return detect_auto_fallback(case["backend"], meta)




def collect_artifacts(paths: list[str]) -> list[dict[str, Any]]:
    """收集文件或目录产物信息。"""

    reports = []
    for path_text in paths:
        path = Path(path_text)
        item = {
            "path": str(path),
            "exists": path.exists(),
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
        }
        if path.is_file():
            item["size_bytes"] = path.stat().st_size
        elif path.is_dir():
            files = sorted(str(file.relative_to(path)) for file in path.rglob("*") if file.is_file())
            item["file_count"] = len(files)
            item["files"] = files
        reports.append(item)
    return reports


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    """执行单条真实 CLI 命令。"""

    started_at = now_iso()
    begin = time.perf_counter()
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    command = CLI_PREFIX + case["tokens"]
    stdout = ""
    stderr = ""
    status = "FAIL"
    returncode: int | None = None
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=case["timeout"],
            env=env,
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        returncode = completed.returncode
        status = "PASS" if completed.returncode == 0 else "FAIL"
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", errors="replace")
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", errors="replace")
        if stderr:
            stderr += "\n"
        stderr += f"TIMEOUT after {case['timeout']}s"
        status = "TIMEOUT"
    duration = round(time.perf_counter() - begin, 3)
    meta = parse_backend_meta(stdout)
    artifacts = collect_artifacts(case["artifacts"])
    failure_class, failure_reason = infer_failure(case, stdout, stderr, returncode, status, meta, artifacts)
    return {
        "id": case["id"],
        "path": case["path"],
        "category": case["category"],
        "requested_backend": case["backend"],
        "note": case["note"],
        "mode_tags": list(case["tags"]),
        "command_text": subprocess.list2cmdline(command),
        "started_at": started_at,
        "finished_at": now_iso(),
        "duration_seconds": duration,
        "timeout_seconds": case["timeout"],
        "returncode": returncode,
        "status": status,
        "failure_class": failure_class,
        "failure_reason": failure_reason,
        "stdout": stdout,
        "stderr": stderr,
        "backend_meta": meta,
        "auto_fallback_used": detect_fallback(case, meta),
        "artifact_reports": artifacts,
    }

def summarize(results: list[dict[str, Any]], matrix: dict[str, Any]) -> dict[str, Any]:
    """汇总统计结果。"""

    total = len(results)
    counts = Counter(item["status"] for item in results)
    durations = [item["duration_seconds"] for item in results]
    category_stats: dict[str, Counter[str]] = defaultdict(Counter)
    backend_stats: dict[str, Counter[str]] = defaultdict(Counter)
    auto_final: Counter[str] = Counter()
    failure_class_counter: Counter[str] = Counter()
    fallback_count = 0
    auto_failed = 0
    for item in results:
        category_stats[item["category"]][item["status"]] += 1
        backend_stats[item["requested_backend"] or "default"][item["status"]] += 1
        if item.get("failure_class"):
            failure_class_counter[str(item["failure_class"])] += 1
        if item["requested_backend"] == "auto":
            auto_final[str(item["backend_meta"].get("final_backend") or "<none>")] += 1
            if item["auto_fallback_used"]:
                fallback_count += 1
            if item["status"] != "PASS" and not item["backend_meta"].get("final_backend"):
                auto_failed += 1

    def fold(counter_map: dict[str, Counter[str]]) -> dict[str, dict[str, Any]]:
        data = {}
        for name, counter in sorted(counter_map.items()):
            subtotal = sum(counter.values())
            data[name] = {
                "total": subtotal,
                "pass": counter.get("PASS", 0),
                "fail": counter.get("FAIL", 0),
                "timeout": counter.get("TIMEOUT", 0),
                "pass_rate": round((counter.get("PASS", 0) / subtotal) * 100, 2) if subtotal else 0.0,
            }
        return data

    return {
        "total": total,
        "pass": counts.get("PASS", 0),
        "fail": counts.get("FAIL", 0),
        "timeout": counts.get("TIMEOUT", 0),
        "pass_rate": round((counts.get("PASS", 0) / total) * 100, 2) if total else 0.0,
        "avg_duration_seconds": round(statistics.mean(durations), 3) if durations else 0.0,
        "median_duration_seconds": round(statistics.median(durations), 3) if durations else 0.0,
        "category_stats": fold(category_stats),
        "backend_stats": fold(backend_stats),
        "failure_class_counter": dict(failure_class_counter),
        "auto_stats": {
            "total": sum(1 for item in results if item["requested_backend"] == "auto"),
            "fallback_used": fallback_count,
            "all_failed_without_final_backend": auto_failed,
            "final_backend_counts": dict(auto_final),
        },
        "matrix": matrix,
    }


def render_html(payload: dict[str, Any]) -> str:
    """渲染 HTML 报告。"""

    summary = payload["summary"]
    results = payload["results"]
    def table_rows(items: dict[str, dict[str, Any]]) -> str:
        return "\n".join(
            f"<tr><td>{escape(name)}</td><td>{item['total']}</td><td>{item['pass']}</td><td>{item['fail']}</td><td>{item['timeout']}</td><td>{item['pass_rate']}%</td></tr>"
            for name, item in items.items()
        )
    auto_rows = "\n".join(
        f"<tr><td>{escape(name)}</td><td>{count}</td></tr>"
        for name, count in summary["auto_stats"]["final_backend_counts"].items()
    ) or "<tr><td colspan=\"2\">暂无记录</td></tr>"
    case_blocks = []
    for index, item in enumerate(results, start=1):
        style = {"PASS": "ok", "FAIL": "danger", "TIMEOUT": "warn"}.get(item["status"], "warn")
        evidence = {
            "requested_backend": item.get("requested_backend"),
            "resolved_backend": item["backend_meta"].get("resolved_backend"),
            "planned_candidates": item["backend_meta"].get("planned_candidates") or [],
            "attempted_candidates": item["backend_meta"].get("attempted_candidates") or [],
            "final_backend": item["backend_meta"].get("final_backend"),
            "fallback_used": item["backend_meta"].get("fallback_used", item.get("auto_fallback_used", False)),
            "limit_strategy": item["backend_meta"].get("limit_strategy"),
            "limit_effect": item["backend_meta"].get("limit_effect"),
            "display_limit_applied": item["backend_meta"].get("display_limit_applied"),
            "execution_limit_applied": item["backend_meta"].get("execution_limit_applied"),
        }
        case_blocks.append(
            f"""
<section class="test-case" id="case-{index}">
  <div class="test-header {style}">
    <span class="test-id">#{index}</span>
    <span class="test-command">{escape(item['path'])}</span>
    <span class="test-status">{escape(item['status'])}</span>
    <span class="test-time">{item['duration_seconds']}s</span>
    <span class="test-backend">requested={escape(str(item['requested_backend']))}</span>
  </div>
  <div class="test-body">
    <p><strong>命令:</strong> <code>{escape(item['command_text'])}</code></p>
    <p><strong>说明:</strong> {escape(item['note'])}</p>
    <p><strong>模式标签:</strong> {escape(', '.join(item['mode_tags']) or '<none>')}</p>
    <p><strong>退出码:</strong> {escape(str(item['returncode']))} | <strong>失败类型:</strong> {escape(str(item['failure_class']))} | <strong>auto 真实兜底:</strong> {item['auto_fallback_used']}</p>
    <details open><summary>backend 元数据</summary><pre>{escape(json.dumps(item['backend_meta'], ensure_ascii=False, indent=2) or '{}')}</pre></details>
    <details><summary>stdout</summary><pre>{escape(item['stdout'] or '<empty>')}</pre></details>
    <details><summary>stderr</summary><pre>{escape(item['stderr'] or '<empty>')}</pre></details>
    <details><summary>产物落盘</summary><pre>{escape(json.dumps(item['artifact_reports'], ensure_ascii=False, indent=2) or '[]')}</pre></details>
  </div>
</section>
"""
        )
    mode_text = ", ".join(summary["matrix"]["mode_tags"])
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>efinance-cli 第三次全量真实 API 回归测试结论</title>
<style>
:root {{ --bg:#eef4f7; --paper:rgba(255,255,255,.92); --line:rgba(45,89,114,.18); --ink:#15212b; --muted:#536576; --accent:#215c77; --accent-soft:rgba(33,92,119,.12); --ok:#1c6f53; --ok-bg:#e6f4ee; --warn:#8b6117; --warn-bg:#fff1df; --danger:#8a2f33; --danger-bg:#fbe7e8; --code:#182833; --code-ink:#edf8ff; --shadow:0 28px 72px rgba(16,41,58,.10); }}
* {{ box-sizing:border-box; }}
body {{ margin:0; color:var(--ink); background:linear-gradient(180deg,rgba(255,255,255,.68),rgba(255,255,255,.68)),radial-gradient(circle at top right, rgba(33,92,119,.18), transparent 24%),linear-gradient(180deg,#e8f0f4 0%,var(--bg) 100%); font-family:"Georgia","Times New Roman","Noto Serif SC",serif; line-height:1.82; }}
code,pre {{ font-family:"Cascadia Code","Consolas",monospace; }}
pre {{ margin:0; padding:1rem 1.1rem; overflow-x:auto; white-space:pre-wrap; word-break:break-word; font-size:.83rem; line-height:1.55; border-radius:10px; background:var(--code); color:var(--code-ink); }}
.nav {{ position:sticky; top:0; z-index:20; backdrop-filter:blur(10px); background:rgba(255,255,255,.78); border-bottom:1px solid var(--line); }}
.nav-inner {{ max-width:1280px; margin:0 auto; padding:.8rem 1.2rem; display:flex; gap:1rem; flex-wrap:wrap; font-size:.92rem; }}
.page {{ max-width:1280px; margin:0 auto; padding:28px 18px 72px; }}
.hero {{ position:relative; overflow:hidden; padding:2.3rem 2rem; border:1px solid var(--line); border-radius:24px; background:linear-gradient(135deg,rgba(255,255,255,.98),rgba(247,251,253,.92)),linear-gradient(90deg,rgba(33,92,119,.05),transparent); box-shadow:var(--shadow); }}
.hero::before {{ content:""; position:absolute; inset:0; background-image:linear-gradient(rgba(33,92,119,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(33,92,119,.08) 1px,transparent 1px); background-size:28px 28px; mask-image:linear-gradient(180deg,rgba(0,0,0,.38),transparent 85%); pointer-events:none; }}
.hero>* {{ position:relative; z-index:1; }}
.eyebrow {{ display:inline-block; padding:.25rem .7rem; border-radius:999px; background:var(--accent-soft); color:var(--accent); font-size:.82rem; letter-spacing:.06em; text-transform:uppercase; }}
.hero h1 {{ margin:.9rem 0 .45rem; font-size:clamp(2rem,4vw,3.2rem); line-height:1.12; color:var(--accent); }}
.hero p {{ margin:.4rem 0; color:var(--muted); }}
.card-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:1rem; margin-top:1.6rem; }}
.stat-card,.panel,.test-case {{ border:1px solid var(--line); background:var(--paper); box-shadow:var(--shadow); }}
.stat-card {{ padding:1rem 1.1rem; border-radius:16px; }} .stat-num {{ font-size:2rem; font-weight:700; }} .stat-label {{ color:var(--muted); font-size:.9rem; }}
.section {{ margin-top:2.2rem; }} .section h2 {{ margin:0 0 1rem; padding-bottom:.4rem; color:var(--accent); border-bottom:2px solid var(--accent-soft); }}
.panel {{ border-radius:18px; padding:1.2rem 1.3rem; }} .muted {{ color:var(--muted); }} table {{ width:100%; border-collapse:collapse; }} th,td {{ padding:.66rem .82rem; text-align:left; border-bottom:1px solid var(--line); vertical-align:top; }} th {{ background:rgba(33,92,119,.06); }}
.test-case {{ border-radius:18px; overflow:hidden; margin-top:1rem; }} .test-header {{ display:flex; gap:.9rem; flex-wrap:wrap; align-items:center; padding:.78rem 1rem; font-size:.92rem; }} .test-header.ok {{ background:var(--ok-bg); border-left:5px solid var(--ok); }} .test-header.warn {{ background:var(--warn-bg); border-left:5px solid var(--warn); }} .test-header.danger {{ background:var(--danger-bg); border-left:5px solid var(--danger); }} .test-id {{ color:var(--muted); min-width:3rem; font-weight:700; }} .test-command {{ font-family:"Cascadia Code","Consolas",monospace; font-weight:700; flex:1; }} .test-body {{ padding:1rem 1.05rem 1.15rem; }} .test-body p {{ margin:.38rem 0; }} details {{ margin-top:.7rem; }} details summary {{ cursor:pointer; color:var(--accent); }}
</style>
</head>
<body>
<div class="nav"><div class="nav-inner"><a href="#summary">概览</a><a href="#coverage">覆盖协议</a><a href="#category">按分类统计</a><a href="#backend">按 backend 统计</a><a href="#auto">auto 兜底统计</a><a href="#details">逐条真实输出</a></div></div>
<div class="page">
<section class="hero"><span class="eyebrow">Real API Regression</span><h1>efinance-cli 第三次全量真实 API 回归测试结论</h1><p>本报告使用 <code>{escape(str(VENV_PYTHON))}</code> 调用真实 CLI 与真实第三方 API，不做 mock，不复用既有测试脚本；每条命令的 stdout / stderr 均原样保留。</p><p>开始时间: {escape(payload['started_at'])} | 结束时间: {escape(str(payload.get('finished_at') or '进行中'))} | 进度: {len(results)} / {summary['total']}</p><div class="card-grid"><div class="stat-card"><div class="stat-num">{summary['total']}</div><div class="stat-label">总用例</div></div><div class="stat-card"><div class="stat-num" style="color:var(--ok)">{summary['pass']}</div><div class="stat-label">通过</div></div><div class="stat-card"><div class="stat-num" style="color:var(--danger)">{summary['fail']}</div><div class="stat-label">失败</div></div><div class="stat-card"><div class="stat-num" style="color:var(--warn)">{summary['timeout']}</div><div class="stat-label">超时</div></div><div class="stat-card"><div class="stat-num">{summary['pass_rate']}%</div><div class="stat-label">通过率</div></div><div class="stat-card"><div class="stat-num">{summary['avg_duration_seconds']}s</div><div class="stat-label">平均耗时</div></div></div></section>
<section class="section" id="summary"><h2>任务定约与执行结论</h2><div class="panel"><p><strong>Objective:</strong> 基于当前源码对全部命令、全部 backend、全部关键模式和全部业务参数面做真实 API 回归。</p><p><strong>Verification:</strong> 逐条真实执行，记录退出码、耗时、stdout、stderr、backend 元数据和副作用产物。</p><p class="muted">若存在限流、远端断连、空结果、进度条噪音或编码噪音，报告均按真实输出保留，不做隐藏。</p></div></section>
<section class="section" id="coverage"><h2>覆盖协议</h2><div class="panel"><p><strong>命令覆盖:</strong> {summary['matrix']['expected_command_count']} 条。</p><p><strong>shared auto 覆盖:</strong> {summary['matrix']['shared_auto_covered']} / {summary['matrix']['shared_auto_target']}。</p><p><strong>显式 backend 覆盖:</strong> {summary['matrix']['explicit_backend_covered']} / {summary['matrix']['explicit_backend_target']}。</p><p><strong>业务参数覆盖:</strong> {summary['matrix']['business_option_covered']} / {summary['matrix']['business_option_target']}。</p><p><strong>关键模式:</strong> {escape(mode_text)}</p><p><strong>默认路由样本:</strong> {summary['matrix']['default_route_samples']}</p></div></section>
<section class="section" id="category"><h2>按分类统计</h2><div class="panel"><table><thead><tr><th>分类</th><th>总数</th><th>通过</th><th>失败</th><th>超时</th><th>通过率</th></tr></thead><tbody>{table_rows(summary['category_stats'])}</tbody></table></div></section>
<section class="section" id="backend"><h2>按 backend 统计</h2><div class="panel"><table><thead><tr><th>backend</th><th>总数</th><th>通过</th><th>失败</th><th>超时</th><th>通过率</th></tr></thead><tbody>{table_rows(summary['backend_stats'])}</tbody></table></div></section>
<section class="section" id="auto"><h2>auto 兜底统计</h2><div class="panel"><p><strong>auto 用例总数:</strong> {summary['auto_stats']['total']}</p><p><strong>真实发生 fallback:</strong> {summary['auto_stats']['fallback_used']}</p><p><strong>无最终 backend 且失败:</strong> {summary['auto_stats']['all_failed_without_final_backend']}</p><table><thead><tr><th>最终 backend</th><th>次数</th></tr></thead><tbody>{auto_rows}</tbody></table></div></section>
<section class="section" id="details"><h2>逐条真实输出</h2><div class="panel"><p class="muted">以下记录逐条保留执行命令、耗时、退出码、backend 元数据以及原始 stdout / stderr。</p></div>{''.join(case_blocks)}</section>
</div></body></html>"""


def write_text(path: Path, content: str) -> None:
    """以 UTF-8 无 BOM 写入文本。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def save_payload(cases: list[dict[str, Any]], results: list[dict[str, Any]], matrix: dict[str, Any], started_at: str, finished_at: str | None) -> None:
    """同步刷新 JSON / HTML 产物。"""

    payload = {
        "started_at": started_at,
        "finished_at": finished_at,
        "generated_at": now_iso(),
        "python": str(VENV_PYTHON),
        "cwd": str(PROJECT_ROOT),
        "cases": cases,
        "results": results,
        "summary": summarize(results, matrix),
    }
    write_text(RESULT_JSON, json.dumps(payload, ensure_ascii=False, indent=2))
    write_text(RAW_JSON, json.dumps({"started_at": started_at, "finished_at": finished_at, "results": results}, ensure_ascii=False, indent=2))
    write_text(REPORT_HTML, render_html(payload))


def main() -> None:
    """脚本主入口。"""

    if not VENV_PYTHON.exists():
        raise FileNotFoundError(f"未找到项目解释器: {VENV_PYTHON}")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    started_at = now_iso()
    cases = build_cases()
    matrix = validate_cases(cases)
    results: list[dict[str, Any]] = []
    save_payload(cases, results, matrix, started_at, None)
    total = len(cases)
    for index, case in enumerate(cases, start=1):
        print(f"[{index:03d}/{total:03d}] START {case['path']} requested={case['backend']}", flush=True)
        result = run_case(case)
        results.append(result)
        print(f"[{index:03d}/{total:03d}] {result['status']:<7} {result['duration_seconds']:>8.3f}s {case['path']} requested={case['backend']}", flush=True)
        if result["failure_class"]:
            print(f"           failure={result['failure_class']}", flush=True)
        save_payload(cases, results, matrix, started_at, None)
    finished_at = now_iso()
    save_payload(cases, results, matrix, started_at, finished_at)
    summary = summarize(results, matrix)
    print(f"完成: total={summary['total']} pass={summary['pass']} fail={summary['fail']} timeout={summary['timeout']} pass_rate={summary['pass_rate']}% html={REPORT_HTML}", flush=True)


if __name__ == "__main__":
    main()
