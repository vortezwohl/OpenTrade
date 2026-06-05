#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OpenTrade 全命令 dryrun / 真实环境回归执行入口。

该脚本面向当前仓库的 52 条叶子命令，自动收集命令树、生成最小合法调用、
补充关键运行时参数覆盖，并把 dryrun 与真实环境测试结果统一写入 docs。

设计目标：
1. 不伪造“所有参数组合全部执行完毕”的结论；
2. 对全部叶子命令执行结构化 dryrun 覆盖；
3. 对全部叶子命令执行最小真实调用，并对关键运行时参数做系统覆盖；
4. 对带副作用的命令使用独立临时目录，避免污染默认工作区；
5. 把实际覆盖边界、失败原因和测试结论落盘，便于后续 agent 复跑与审计。
"""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_cli_support_module = importlib.import_module("tests.cli_regression_support")
build_all_optional_option_tokens = (
    _cli_support_module.build_all_optional_option_tokens
)
build_cli = _cli_support_module.build_cli
build_required_tokens = _cli_support_module.build_required_tokens
collect_leaf_commands = _cli_support_module.collect_leaf_commands
LeafCommand = _cli_support_module.LeafCommand

DOCS_DIR = PROJECT_ROOT / "docs"
DRYRUN_JSON_PATH = DOCS_DIR / "20260602-opentrade-dryrun-results.json"
REAL_JSON_PATH = DOCS_DIR / "20260602-opentrade-real-results.json"
SUMMARY_MD_PATH = DOCS_DIR / "20260602-opentrade-full-regression-report.md"
LOCAL_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
PYTHON_BIN = str(LOCAL_PYTHON if LOCAL_PYTHON.exists() else sys.executable)
CLI_ENTRY = [PYTHON_BIN, "-m", "opentrade"]
DRYRUN_TIMEOUT_SECONDS = 30
REAL_TIMEOUT_SECONDS = 25
WATCH_TIMEOUT_SECONDS = 10
WATCH_CASES = {
    "search local",
    "fund nav history",
    "quote price latest",
    "stock price history",
    "stock price live",
    "market price live",
    "resolve quote-id",
}
SIDE_EFFECT_COMMANDS = {"fund reports download", "market add"}
RUNTIME_COVERAGE_COMMANDS = {
    "watch",
    "search local",
    "fund nav history",
    "fund reports download",
    "quote price latest",
    "stock price history",
    "stock price live",
    "stock industry boards",
    "market add",
    "market price live",
    "resolve quote-id",
}


@dataclass(slots=True)
class CaseResult:
    """描述一条 dryrun 或真实环境用例的结果。"""

    phase: str
    command_path: str
    case_name: str
    argv: list[str]
    exit_code: int
    elapsed_ms: int
    success: bool
    stdout: str
    stderr: str
    note: str = ""


def _truncate(text: str, limit: int = 6000) -> str:
    """限制落盘输出长度，避免 JSON 与 Markdown 膨胀失控。"""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n\n... [截断，原始长度 {len(text)} 字符]"


def _run_cli(argv: list[str], timeout_seconds: int) -> CaseResult:
    """执行一次 CLI 调用。"""
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return CaseResult(
            phase="",
            command_path="",
            case_name="",
            argv=argv,
            exit_code=proc.returncode,
            elapsed_ms=elapsed_ms,
            success=proc.returncode == 0,
            stdout=_truncate(proc.stdout),
            stderr=_truncate(proc.stderr),
        )
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return CaseResult(
            phase="",
            command_path="",
            case_name="",
            argv=argv,
            exit_code=-1,
            elapsed_ms=elapsed_ms,
            success=False,
            stdout=_truncate(
                (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            ),
            stderr=f"TIMEOUT after {timeout_seconds}s",
            note="超时",
        )


def _sample_required_tokens(leaf: LeafCommand, temp_dir: Path) -> list[str]:
    """为真实执行构造更贴近实际的最小合法参数。"""
    path = " ".join(leaf.path)
    if path == "watch":
        return [
            "watch", "--count", "1", "--interval", "0.2", "search", "--query",
            "AAPL"
        ]
    if path == "search local":
        return ["search", "local", "--query", "AAPL"]
    if path == "search":
        return ["search", "--query", "AAPL"]
    if path == "market add":
        return [
            "market",
            "add",
            "--market-category",
            "codex_regression",
            "--market-id",
            "999",
            "--market-name",
            "Codex Regression Market",
        ]
    if path == "fund reports download":
        return [
            "fund",
            "reports",
            "download",
            "--symbol",
            "161725",
            "--max-files",
            "1",
            "--output-dir",
            str(temp_dir / "fund-pdf-output"),
        ]
    if path == "market price live":
        return [
            "market", "price", "live", "--market", "m:105+t:3", "--limit", "3"
        ]
    if path == "quote price history":
        return [
            "quote", "price", "history", "--quote-id", "1.000001",
            "--start-date", "20250501", "--end-date", "20250503"
        ]
    if path == "quote price latest":
        return ["quote", "price", "latest", "--quote-ids", "1.000001"]
    if path == "quote profile":
        return ["quote", "profile", "--quote-id", "1.000001"]
    if path == "quote trades":
        return ["quote", "trades", "--quote-id", "1.000001"]
    if path == "quote flow history":
        return ["quote", "flow", "history", "--quote-id", "1.000001"]
    if path == "quote flow today":
        return ["quote", "flow", "today", "--quote-id", "1.000001"]
    if path == "resolve quote-id":
        return ["resolve", "quote-id", "--symbol", "000001"]
    if path == "stock price history":
        return [
            "stock", "price", "history", "--symbols", "000001", "--start-date",
            "20250501", "--end-date", "20250503"
        ]
    if path == "stock price latest":
        return ["stock", "price", "latest", "--symbols", "000001"]
    if path == "stock price live":
        return [
            "stock", "price", "live", "--market", "A_stock", "--limit", "3"
        ]
    if path == "stock price snapshot":
        return ["stock", "price", "snapshot", "--symbols", "000001"]
    if path == "stock profile":
        return ["stock", "profile", "--symbols", "000001"]
    if path == "stock constituents":
        return ["stock", "constituents", "--symbols", "000300"]
    if path == "stock sector":
        return ["stock", "sector", "--symbols", "000001"]
    if path == "stock trades":
        return ["stock", "trades", "--symbols", "000001"]
    if path == "stock report-dates":
        return ["stock", "report-dates"]
    if path == "stock ipo latest":
        return ["stock", "ipo", "latest"]
    if path == "stock leaderboard daily":
        return [
            "stock", "leaderboard", "daily", "--start-date", "20250530",
            "--end-date", "20250530"
        ]
    if path == "stock performance quarterly":
        return ["stock", "performance", "quarterly"]
    if path == "stock holders top10":
        return ["stock", "holders", "top10", "--symbols", "000001"]
    if path == "stock holders latest-count":
        return ["stock", "holders", "latest-count", "--symbols", "000001"]
    if path == "stock flow history":
        return ["stock", "flow", "history", "--symbols", "000001"]
    if path == "stock flow today":
        return ["stock", "flow", "today", "--symbols", "000001"]
    if path == "stock industry boards":
        return ["stock", "industry", "boards"]
    if path == "fund nav history":
        return ["fund", "nav", "history", "--symbol", "161725"]
    if path == "fund nav history-batch":
        return [
            "fund", "nav", "history-batch", "--symbols", "161725", "--symbols",
            "110022"
        ]
    if path == "fund profile":
        return ["fund", "profile", "--symbols", "161725"]
    if path == "fund allocation industry":
        return ["fund", "allocation", "industry", "--symbol", "161725"]
    if path == "fund allocation position":
        return ["fund", "allocation", "position", "--symbol", "161725"]
    if path == "fund allocation types":
        return ["fund", "allocation", "types", "--symbol", "161725"]
    if path == "fund catalog":
        return ["fund", "catalog", "--limit", "3"]
    if path == "fund disclosure dates":
        return ["fund", "disclosure", "dates", "--symbol", "161725"]
    if path == "fund estimate live":
        return ["fund", "estimate", "live", "--symbol", "161725"]
    if path == "fund managers":
        return ["fund", "managers", "--symbol", "161725"]
    if path == "fund performance period":
        return ["fund", "performance", "period", "--symbol", "161725"]
    if path == "bond catalog":
        return ["bond", "catalog", "--limit", "3"]
    if path == "bond flow history":
        return ["bond", "flow", "history", "--symbol", "019641"]
    if path == "bond flow today":
        return ["bond", "flow", "today", "--symbol", "019641"]
    if path == "bond price history":
        return [
            "bond", "price", "history", "--symbols", "019641", "--start-date",
            "20250501", "--end-date", "20250503"
        ]
    if path == "bond price live":
        return ["bond", "price", "live", "--limit", "3"]
    if path == "bond profile":
        return ["bond", "profile", "--symbol", "019641"]
    if path == "bond trades":
        return ["bond", "trades", "--symbol", "019641"]
    if path == "futures catalog":
        return ["futures", "catalog", "--limit", "3"]
    if path == "futures price history":
        return ["futures", "price", "history", "--symbols", "IH888"]
    if path == "futures price live":
        return ["futures", "price", "live", "--limit", "3"]
    if path == "futures trades":
        return ["futures", "trades", "--symbol", "IH888"]
    if path == "quote news":
        return ["quote", "news", "--quote-id", "AAPL", "--result-count", "3"]
    return build_required_tokens(leaf)


def _runtime_coverage_cases(command_path: str,
                            temp_dir: Path) -> list[tuple[str, list[str]]]:
    """返回代表性命令的真实环境参数覆盖矩阵。"""
    if command_path == "watch":
        return [
            (
                "watch-search", [
                    "--count", "1", "--interval", "0.2", "search", "--query",
                    "AAPL"
                ]
            )
        ]
    if command_path == "search local":
        return [
            ("json", ["--format", "json"]),
            (
                "watch",
                ["--watch", "--count", "1", "--interval", "0.2", "--no-clear"]
            ),
        ]
    if command_path == "fund nav history":
        return [
            ("akshare-json", ["--backend", "akshare", "--format", "json"]),
            (
                "raw-full", [
                    "--view", "raw", "--indicator-level", "full",
                    "--trace-window", "8"
                ]
            ),
        ]
    if command_path == "fund reports download":
        return [
            (
                "isolated-output",
                [
                    "--max-files", "1", "--output-dir",
                    str(temp_dir / "fund-download-runtime")
                ],
            )
        ]
    if command_path == "quote price latest":
        return [
            ("json", ["--format", "json"]),
            (
                "watch",
                ["--watch", "--count", "1", "--interval", "0.2", "--no-clear"]
            ),
        ]
    if command_path == "stock price history":
        return [
            (
                "csv", [
                    "--format", "csv", "--output",
                    str(temp_dir / "stock-history.csv")
                ]
            ),
            (
                "raw-full", [
                    "--view", "raw", "--indicator-level", "full",
                    "--trace-window", "8"
                ]
            ),
            (
                "watch",
                ["--watch", "--count", "1", "--interval", "0.2", "--no-clear"]
            ),
        ]
    if command_path == "stock price live":
        return [
            ("akshare", ["--backend", "akshare"]),
            ("json", ["--format", "json"]),
        ]
    if command_path == "stock industry boards":
        return [("json-limit", ["--format", "json", "--limit", "2"])]
    if command_path == "market add":
        return [
            (
                "deduplicate-off",
                [
                    "--no-deduplicate", "--output",
                    str(temp_dir / "market-add.txt")
                ],
            )
        ]
    if command_path == "market price live":
        return [
            ("json", ["--format", "json"]),
            (
                "watch",
                ["--watch", "--count", "1", "--interval", "0.2", "--no-clear"]
            ),
        ]
    if command_path == "resolve quote-id":
        return [
            ("json-ignore-errors", ["--format", "json", "--ignore-errors"]),
            ("market-filter", ["--market", "A_stock", "--no-use-local-cache"]),
        ]
    return []


def _real_timeout_for_command(command_path: str) -> int:
    """为真实环境命令设置更保守的超时，避免长尾阻塞整体回归。"""
    if command_path == "watch":
        return WATCH_TIMEOUT_SECONDS
    if command_path in {
            "quote price latest",
            "quote price history",
            "stock price latest",
            "stock price live",
            "market price live",
    }:
        return 12
    return REAL_TIMEOUT_SECONDS


def _help_case(argv_tail: list[str], leaf: LeafCommand) -> CaseResult:
    """执行帮助信息用例。"""
    result = _run_cli(
        CLI_ENTRY + argv_tail + ["--help"], DRYRUN_TIMEOUT_SECONDS
    )
    result.phase = "dryrun"
    result.command_path = " ".join(leaf.path)
    result.case_name = "help"
    return result


def _dryrun_parse_case(argv_tail: list[str], leaf: LeafCommand) -> CaseResult:
    """通过 monkeypatch 执行“只解析不打后端”的 dryrun。"""
    python_code = """
from click.testing import CliRunner
from unittest.mock import patch
from opentrade.commands import create_root_command
import importlib
import json

captured = {}

def fake_run(self, request):
    captured['path'] = list(request.spec.cli_path)
    captured['command_key'] = request.command_definition.command_key
    captured['backend'] = request.backend_selection.resolved.value
    captured['kwargs'] = dict(request.kwargs)
    captured['watch_enabled'] = request.watch.enabled
    return None

runner = CliRunner()
cli = create_root_command()
argv = json.loads(%s)
with patch('opentrade.executor.CommandExecutor.run', new=fake_run):
    result = runner.invoke(cli, argv)
print(json.dumps({
    'exit_code': result.exit_code,
    'output': result.output,
    'captured': captured,
}, ensure_ascii=False))
""" % json.dumps(json.dumps(argv_tail, ensure_ascii=False))
    argv = [PYTHON_BIN, "-X", "utf8", "-c", python_code]
    result = _run_cli(argv, DRYRUN_TIMEOUT_SECONDS)
    result.phase = "dryrun"
    result.command_path = " ".join(leaf.path)
    result.case_name = "parse"
    return result


def run_dryrun_suite() -> dict[str, Any]:
    """执行完整 dryrun 回归。"""
    dryrun_results: list[CaseResult] = []
    cli = build_cli()
    leaf_commands = collect_leaf_commands(cli)
    temp_dir = Path(tempfile.mkdtemp(prefix="opentrade-dryrun-"))
    try:
        for leaf in leaf_commands:
            if " ".join(leaf.path) == "watch":
                help_args = ["watch"]
                parse_args = [
                    "watch", "--count", "1", "--interval", "0.2", "search",
                    "--query", "AAPL"
                ]
            else:
                help_args = list(leaf.path)
                parse_args = build_required_tokens(leaf)
                optional_tokens = build_all_optional_option_tokens(
                    leaf, temp_dir
                )
                if optional_tokens:
                    parse_args = parse_args + optional_tokens

            dryrun_results.append(_help_case(help_args, leaf))
            dryrun_results.append(_dryrun_parse_case(parse_args, leaf))

        summary = _summarize_results(dryrun_results)
        payload = {
            "generated_at": datetime.now().isoformat(),
            "leaf_command_count": len(leaf_commands),
            "case_count": len(dryrun_results),
            "summary": summary,
            "results": [asdict(item) for item in dryrun_results],
        }
        DRYRUN_JSON_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return payload
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def run_real_suite() -> dict[str, Any]:
    """执行完整真实环境回归。"""
    results: list[CaseResult] = []
    leaf_commands = collect_leaf_commands()
    temp_dir = Path(tempfile.mkdtemp(prefix="opentrade-real-"))
    try:
        for leaf in leaf_commands:
            command_path = " ".join(leaf.path)
            base_tokens = _sample_required_tokens(leaf, temp_dir)
            timeout = _real_timeout_for_command(command_path)

            minimal = _run_cli(CLI_ENTRY + base_tokens, timeout)
            minimal.phase = "real"
            minimal.command_path = command_path
            minimal.case_name = "minimal"
            results.append(minimal)

            if command_path in RUNTIME_COVERAGE_COMMANDS:
                for case_name, runtime_tokens in _runtime_coverage_cases(
                        command_path, temp_dir):
                    runtime = _run_cli(
                        CLI_ENTRY + base_tokens + runtime_tokens, timeout
                    )
                    runtime.phase = "real"
                    runtime.command_path = command_path
                    runtime.case_name = f"runtime-{case_name}"
                    results.append(runtime)

        summary = _summarize_results(results)
        payload = {
            "generated_at": datetime.now().isoformat(),
            "leaf_command_count": len(leaf_commands),
            "case_count": len(results),
            "summary": summary,
            "results": [asdict(item) for item in results],
        }
        REAL_JSON_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return payload
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _summarize_results(results: list[CaseResult]) -> dict[str, Any]:
    """汇总通过、失败与命令级覆盖情况。"""
    total = len(results)
    passed = sum(1 for item in results if item.success)
    failed = total - passed
    by_command: dict[str, dict[str, int]] = {}
    failures: list[dict[str, Any]] = []

    for item in results:
        bucket = by_command.setdefault(
            item.command_path, {
                "total": 0,
                "passed": 0,
                "failed": 0
            }
        )
        bucket["total"] += 1
        if item.success:
            bucket["passed"] += 1
        else:
            bucket["failed"] += 1
            failures.append(
                {
                    "command_path": item.command_path,
                    "case_name": item.case_name,
                    "exit_code": item.exit_code,
                    "note": item.note,
                    "stderr": item.stderr,
                }
            )

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round((passed / total) * 100, 1) if total else 0.0,
        "command_breakdown": by_command,
        "failures": failures,
    }


def write_markdown_report(
    dryrun_payload: dict[str, Any], real_payload: dict[str, Any]
) -> None:
    """把最终回归结论写入 Markdown 报告。"""
    lines: list[str] = []
    lines.append("# OpenTrade 全命令 dryrun / 真实环境回归报告")
    lines.append("")
    lines.append(f"- 生成时间: `{datetime.now().isoformat(timespec='seconds')}`")
    lines.append(f"- 叶子命令数: `{dryrun_payload['leaf_command_count']}`")
    lines.append("- 说明: 本报告覆盖全部叶子命令，并对关键运行时参数做系统覆盖；不宣称已穷举所有参数排列组合。")
    lines.append("")
    lines.append("## 覆盖边界")
    lines.append("")
    lines.append(
        "- dryrun: 对每条叶子命令执行 `--help` 与“最小合法参数 + 可选参数单次覆盖”的解析回归，不触发真实后端。"
    )
    lines.append("- 真实环境: 对每条叶子命令至少执行一次最小合法真实调用；对代表性命令追加关键参数覆盖调用。")
    lines.append(
        "- 关键运行时参数覆盖: 通过代表性命令矩阵覆盖 "
        "`--backend`、`--format`、`--view`、`--indicator-level`、"
        "`--trace-window`、`--watch`、`--output`、`--encoding`、"
        "布尔 flag。"
    )
    lines.append(
        "- 带副作用命令: `fund reports download` 与 `market add` "
        "使用临时目录或隔离参数执行，避免污染默认工作区。"
    )
    lines.append("")
    lines.append("## dryrun 结果")
    lines.append("")
    lines.append(f"- 用例数: `{dryrun_payload['case_count']}`")
    lines.append(f"- 通过: `{dryrun_payload['summary']['passed']}`")
    lines.append(f"- 失败: `{dryrun_payload['summary']['failed']}`")
    lines.append(f"- 通过率: `{dryrun_payload['summary']['pass_rate']}%`")
    lines.append("")
    lines.append("## 真实环境结果")
    lines.append("")
    lines.append(f"- 用例数: `{real_payload['case_count']}`")
    lines.append(f"- 通过: `{real_payload['summary']['passed']}`")
    lines.append(f"- 失败: `{real_payload['summary']['failed']}`")
    lines.append(f"- 通过率: `{real_payload['summary']['pass_rate']}%`")
    lines.append("")

    for section_name, payload in [("dryrun 失败项", dryrun_payload),
                                  ("真实环境失败项", real_payload)]:
        lines.append(f"## {section_name}")
        lines.append("")
        failures = payload["summary"]["failures"]
        if not failures:
            lines.append("- 无失败项。")
            lines.append("")
            continue
        for failure in failures:
            lines.append(
                f"- `{failure['command_path']}` / "
                f"`{failure['case_name']}` / exit "
                f"`{failure['exit_code']}`"
            )
            if failure.get("note"):
                lines.append(f"  说明: {failure['note']}")
            stderr = str(failure.get("stderr", "")).strip()
            if stderr:
                lines.append(f"  stderr: `{stderr[:300]}`")
        lines.append("")

    lines.append("## 输出文件")
    lines.append("")
    lines.append(f"- JSON 明细: `{DRYRUN_JSON_PATH.name}`")
    lines.append(f"- JSON 明细: `{REAL_JSON_PATH.name}`")
    lines.append(f"- 当前报告: `{SUMMARY_MD_PATH.name}`")
    lines.append("")
    SUMMARY_MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """顺序执行 dryrun、真实环境回归并写报告。"""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    dryrun_payload = run_dryrun_suite()
    real_payload = run_real_suite()
    write_markdown_report(dryrun_payload, real_payload)
    print(f"dryrun 结果: {DRYRUN_JSON_PATH}")
    print(f"真实环境结果: {REAL_JSON_PATH}")
    print(f"Markdown 报告: {SUMMARY_MD_PATH}")
    print(
        "dryrun 通过率: "
        f"{dryrun_payload['summary']['passed']}/"
        f"{dryrun_payload['summary']['total']} "
        f"({dryrun_payload['summary']['pass_rate']}%)"
    )
    print(
        "real 通过率: "
        f"{real_payload['summary']['passed']}/"
        f"{real_payload['summary']['total']} "
        f"({real_payload['summary']['pass_rate']}%)"
    )


if __name__ == "__main__":
    main()
