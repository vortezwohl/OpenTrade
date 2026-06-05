"""第三次全量真实 API 回归执行器。

该脚本独立于现有测试脚本，直接根据当前源码枚举命令面，使用项目
`.venv` 中的解释器真实调用 CLI 与第三方后端 API，并把每条命令的
stdout / stderr 原样落到 JSON 与 HTML 报告中。
"""

from __future__ import annotations
from tests.regression_reporting import (
    classify_regression_failure,
    detect_auto_fallback,
    extract_backend_meta_from_stdout,
)
from opentrade.commands import create_root_command, create_search_command
from opentrade.command_catalog import SHARED_COMMANDS
from opentrade.backends.factory import list_provider_extension_commands

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


def iter_leaf_paths(command: click.Command,
                    prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
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
            current = current.commands[part] if isinstance(
                current, click.Group) else current
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
        matrix[" ".join(definition.cli_path)] = [
            item.value for item in definition.supported_backends]
    for definition in list_provider_extension_commands():
        provider = (
            definition.provider_name.value
            if definition.provider_name
            else "unknown"
        )
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
        if isinstance(
                parameter,
                click.Option) and parameter.name not in RUNTIME_NAMES:
            names.add(str(parameter.name))
    return names


def present_business_options(
        command: click.Command,
        tokens: list[str]) -> set[str]:
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
    """从 JSON 用例文件构建第三轮真实回归矩阵。"""

    rows = json.loads(CASE_DATA_PATH.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = []
    for row in rows:
        cases.append(
            make_case(
                path=str(row["path"]),
                backend=row.get("backend"),
                tokens=[str(token) for token in row["tokens"]],
                note=str(row["note"]),
                tags=[str(item) for item in row.get("tags", [])],
                timeout=int(row.get("timeout", TIMEOUT)),
                artifacts=[str(item) for item in row.get("artifacts", [])],
            )
        )
    return cases


def validate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """跑前校验命令、backend、参数和运行模式覆盖。"""

    lookup = command_lookup()
    matrix = source_matrix()
    actual_paths = {case["path"] for case in cases}
    missing_paths = sorted(expected_paths() - actual_paths)
    extra_paths = sorted(actual_paths - expected_paths())
    if missing_paths or extra_paths:
        raise RuntimeError(
            f"命令覆盖不完整: missing={missing_paths} extra={extra_paths}")

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
        option_hits[case["path"]].update(
            present_business_options(lookup[case["path"]], case["tokens"]))
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
    """从 stdout 中提取 backend 元数据与 limit 证据。"""

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
    """结合执行上下文推断失败分类与失败原因摘要。"""

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
    """判断 auto 请求是否真实切换到了首候选之外的 backend。"""

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
            files = sorted(str(file.relative_to(path))
                           for file in path.rglob("*") if file.is_file())
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
        stdout = exc.stdout if isinstance(
            exc.stdout,
            str) else (
            exc.stdout or b"").decode(
            "utf-8",
            errors="replace")
        stderr = exc.stderr if isinstance(
            exc.stderr,
            str) else (
            exc.stderr or b"").decode(
            "utf-8",
            errors="replace")
        if stderr:
            stderr += "\n"
        stderr += f"TIMEOUT after {case['timeout']}s"
        status = "TIMEOUT"
    duration = round(time.perf_counter() - begin, 3)
    meta = parse_backend_meta(stdout)
    artifacts = collect_artifacts(case["artifacts"])
    failure_class, failure_reason = infer_failure(
        case, stdout, stderr, returncode, status, meta, artifacts)
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


def summarize(results: list[dict[str, Any]],
              matrix: dict[str, Any]) -> dict[str, Any]:
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
        backend_stats[item["requested_backend"]
                      or "default"][item["status"]] += 1
        if item.get("failure_class"):
            failure_class_counter[str(item["failure_class"])] += 1
        if item["requested_backend"] == "auto":
            auto_final[str(item["backend_meta"].get(
                "final_backend") or "<none>")] += 1
            if item["auto_fallback_used"]:
                fallback_count += 1
            if item["status"] != "PASS" and not item["backend_meta"].get(
                    "final_backend"):
                auto_failed += 1

    def fold(counter_map: dict[str, Counter[str]]
             ) -> dict[str, dict[str, Any]]:
        data = {}
        for name, counter in sorted(counter_map.items()):
            subtotal = sum(counter.values())
            data[name] = {
                "total": subtotal,
                "pass": counter.get("PASS", 0),
                "fail": counter.get("FAIL", 0),
                "timeout": counter.get("TIMEOUT", 0),
                "pass_rate": round(
                    (counter.get("PASS", 0) / subtotal) * 100,
                    2,
                ) if subtotal else 0.0,
            }
        return data

    return {
        "total": total,
        "pass": counts.get("PASS", 0),
        "fail": counts.get("FAIL", 0),
        "timeout": counts.get("TIMEOUT", 0),
        "pass_rate": round(
            (counts.get("PASS", 0) / total) * 100,
            2,
        ) if total else 0.0,
        "avg_duration_seconds": round(
            statistics.mean(durations),
            3,
        ) if durations else 0.0,
        "median_duration_seconds": round(
            statistics.median(durations),
            3,
        ) if durations else 0.0,
        "category_stats": fold(category_stats),
        "backend_stats": fold(backend_stats),
        "failure_class_counter": dict(failure_class_counter),
        "auto_stats": {
            "total": sum(
                1 for item in results if item["requested_backend"] == "auto"
            ),
            "fallback_used": fallback_count,
            "all_failed_without_final_backend": auto_failed,
            "final_backend_counts": dict(auto_final),
        },
        "matrix": matrix,
    }


def render_counter_rows(items: dict[str, dict[str, Any]]) -> str:
    """渲染分类或 backend 统计表的表格行。"""

    rows: list[str] = []
    for name, item in items.items():
        rows.append(
            "<tr>"
            f"<td>{escape(name)}</td>"
            f"<td>{item['total']}</td>"
            f"<td>{item['pass']}</td>"
            f"<td>{item['fail']}</td>"
            f"<td>{item['timeout']}</td>"
            f"<td>{item['pass_rate']}%</td>"
            "</tr>"
        )
    return "\n".join(rows)


def render_auto_rows(counter: dict[str, int]) -> str:
    """渲染 auto 路由最终 backend 分布行。"""

    if not counter:
        return '<tr><td colspan="2">暂无数据</td></tr>'

    rows: list[str] = []
    for name, count in sorted(
        counter.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        rows.append(
            "<tr>"
            f"<td>{escape(str(name))}</td>"
            f"<td>{count}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def render_case_blocks(results: list[dict[str, Any]]) -> str:
    """渲染逐条用例结果详情卡片。"""

    blocks: list[str] = []
    for index, item in enumerate(results, start=1):
        style = {
            "PASS": "ok",
            "FAIL": "danger",
            "TIMEOUT": "warn",
        }.get(item["status"], "warn")
        mode_text = ", ".join(item.get("mode_tags") or []) or "<none>"
        backend_meta = json.dumps(
            item.get("backend_meta") or {},
            ensure_ascii=False,
            indent=2,
        )
        artifact_reports = json.dumps(
            item.get("artifact_reports") or [],
            ensure_ascii=False,
            indent=2,
        )
        lines = [
            f'<article class="case-card" id="case-{index}">',
            f'  <div class="case-head {style}">',
            f'    <span class="case-id">#{index:03d}</span>',
            f'    <span class="case-path">{escape(item["path"])}</span>',
            f'    <span class="case-status">{escape(item["status"])}</span>',
            (
                '    <span class="case-time">'
                f"{item['duration_seconds']}s</span>"
            ),
            (
                '    <span class="case-backend">requested='
                f"{escape(str(item.get('requested_backend')))}</span>"
            ),
            "  </div>",
            '  <div class="case-body">',
            (
                "    <p><strong>命令:</strong> <code>"
                f"{escape(item['command_text'])}</code></p>"
            ),
            f'    <p><strong>备注:</strong> {escape(item["note"])}</p>',
            f'    <p><strong>运行模式:</strong> {escape(mode_text)}</p>',
            (
                "    <p><strong>返回码:</strong> "
                f"{escape(str(item['returncode']))} | "
                "<strong>失败归类:</strong> "
                f"{escape(str(item.get('failure_class')))} | "
                "<strong>auto fallback:</strong> "
                f"{item['auto_fallback_used']}</p>"
            ),
            "    <details open>",
            "      <summary>backend 元数据</summary>",
            f"      <pre>{escape(backend_meta)}</pre>",
            "    </details>",
            "    <details>",
            "      <summary>stdout</summary>",
            f"      <pre>{escape(item['stdout'] or '<empty>')}</pre>",
            "    </details>",
            "    <details>",
            "      <summary>stderr</summary>",
            f"      <pre>{escape(item['stderr'] or '<empty>')}</pre>",
            "    </details>",
            "    <details>",
            "      <summary>产物记录</summary>",
            f"      <pre>{escape(artifact_reports)}</pre>",
            "    </details>",
            "  </div>",
            "</article>",
        ]
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


def render_html(payload: dict[str, Any]) -> str:
    """渲染第三轮全量真实回归 HTML 报告。"""

    summary = payload["summary"]
    results = payload["results"]
    mode_text = ", ".join(summary["matrix"]["mode_tags"])
    category_rows = render_counter_rows(summary["category_stats"])
    backend_rows = render_counter_rows(summary["backend_stats"])
    auto_rows = render_auto_rows(summary["auto_stats"]["final_backend_counts"])
    html_lines = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '  <meta charset="utf-8">',
        (
            '  <meta name="viewport" content="width=device-width, '
            'initial-scale=1">'
        ),
        "  <title>efinance-cli 第三轮真实 API 全量回归</title>",
        "  <style>",
        "    :root {",
        "      --bg: #eef4f7;",
        "      --paper: rgba(255, 255, 255, 0.94);",
        "      --line: rgba(45, 89, 114, 0.18);",
        "      --ink: #15212b;",
        "      --muted: #536576;",
        "      --accent: #215c77;",
        "      --accent-soft: rgba(33, 92, 119, 0.12);",
        "      --ok: #1c6f53;",
        "      --ok-bg: #e6f4ee;",
        "      --warn: #8b6117;",
        "      --warn-bg: #fff1df;",
        "      --danger: #8a2f33;",
        "      --danger-bg: #fbe7e8;",
        "      --code: #182833;",
        "      --code-ink: #edf8ff;",
        "      --shadow: 0 28px 72px rgba(16, 41, 58, 0.10);",
        "    }",
        "    * { box-sizing: border-box; }",
        "    body {",
        "      margin: 0;",
        "      color: var(--ink);",
        (
            "      background: linear-gradient(180deg, "
            "rgba(255, 255, 255, 0.70), rgba(255, 255, 255, 0.70)),"
        ),
        (
            "        radial-gradient(circle at top right, "
            "rgba(33, 92, 119, 0.18), transparent 24%),"
        ),
        "        linear-gradient(180deg, #e8f0f4 0%, var(--bg) 100%);",
        (
            "      font-family: \"Georgia\", \"Times New Roman\","
            " \"Noto Serif SC\", serif;"
        ),
        "      line-height: 1.82;",
        "    }",
        "    code, pre {",
        (
            "      font-family: \"Cascadia Code\", \"Consolas\", monospace;"
        ),
        "    }",
        "    pre {",
        "      margin: 0;",
        "      padding: 1rem 1.1rem;",
        "      overflow-x: auto;",
        "      white-space: pre-wrap;",
        "      word-break: break-word;",
        "      font-size: 0.83rem;",
        "      line-height: 1.55;",
        "      border-radius: 10px;",
        "      background: var(--code);",
        "      color: var(--code-ink);",
        "    }",
        "    .nav {",
        "      position: sticky;",
        "      top: 0;",
        "      z-index: 20;",
        "      backdrop-filter: blur(10px);",
        "      background: rgba(255, 255, 255, 0.78);",
        "      border-bottom: 1px solid var(--line);",
        "    }",
        "    .nav-inner {",
        "      max-width: 1280px;",
        "      margin: 0 auto;",
        "      padding: 0.8rem 1.2rem;",
        "      display: flex;",
        "      gap: 1rem;",
        "      flex-wrap: wrap;",
        "      font-size: 0.92rem;",
        "    }",
        "    .nav a { color: var(--accent); text-decoration: none; }",
        (
            "    .page { max-width: 1280px; margin: 0 auto;"
            " padding: 28px 18px 72px; }"
        ),
        "    .hero {",
        "      padding: 2.3rem 2rem;",
        "      border: 1px solid var(--line);",
        "      border-radius: 24px;",
        (
            "      background: linear-gradient(135deg, "
            "rgba(255, 255, 255, 0.98), rgba(247, 251, 253, 0.92));"
        ),
        "      box-shadow: var(--shadow);",
        "    }",
        "    .eyebrow {",
        "      display: inline-block;",
        "      padding: 0.25rem 0.7rem;",
        "      border-radius: 999px;",
        "      background: var(--accent-soft);",
        "      color: var(--accent);",
        "      font-size: 0.82rem;",
        "      letter-spacing: 0.06em;",
        "      text-transform: uppercase;",
        "    }",
        "    .hero h1 {",
        "      margin: 0.9rem 0 0.45rem;",
        "      font-size: clamp(2rem, 4vw, 3.2rem);",
        "      line-height: 1.12;",
        "      color: var(--accent);",
        "    }",
        "    .hero p { margin: 0.4rem 0; color: var(--muted); }",
        "    .card-grid {",
        "      display: grid;",
        "      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));",
        "      gap: 1rem;",
        "      margin-top: 1.6rem;",
        "    }",
        "    .stat-card, .panel, .case-card {",
        "      border: 1px solid var(--line);",
        "      background: var(--paper);",
        "      box-shadow: var(--shadow);",
        "    }",
        "    .stat-card { padding: 1rem 1.1rem; border-radius: 16px; }",
        "    .stat-num { font-size: 2rem; font-weight: 700; }",
        "    .stat-label { color: var(--muted); font-size: 0.9rem; }",
        "    .section { margin-top: 2.2rem; }",
        "    .section h2 {",
        "      margin: 0 0 1rem;",
        "      padding-bottom: 0.4rem;",
        "      color: var(--accent);",
        "      border-bottom: 2px solid var(--accent-soft);",
        "    }",
        "    .panel { border-radius: 18px; padding: 1.2rem 1.3rem; }",
        "    .muted { color: var(--muted); }",
        "    table { width: 100%; border-collapse: collapse; }",
        "    th, td {",
        "      padding: 0.66rem 0.82rem;",
        "      text-align: left;",
        "      border-bottom: 1px solid var(--line);",
        "      vertical-align: top;",
        "    }",
        "    th { background: rgba(33, 92, 119, 0.06); }",
        (
            "    .case-card { border-radius: 18px; overflow: hidden;"
            " margin-top: 1rem; }"
        ),
        "    .case-head {",
        "      display: flex;",
        "      gap: 0.9rem;",
        "      flex-wrap: wrap;",
        "      align-items: center;",
        "      padding: 0.78rem 1rem;",
        "      font-size: 0.92rem;",
        "    }",
        (
            "    .case-head.ok { background: var(--ok-bg);"
            " border-left: 5px solid var(--ok); }"
        ),
        (
            "    .case-head.warn { background: var(--warn-bg);"
            " border-left: 5px solid var(--warn); }"
        ),
        (
            "    .case-head.danger { background: var(--danger-bg);"
            " border-left: 5px solid var(--danger); }"
        ),
        (
            "    .case-id { color: var(--muted); min-width: 3rem;"
            " font-weight: 700; }"
        ),
        (
            "    .case-path { font-family: \"Cascadia Code\","
            " \"Consolas\", monospace; font-weight: 700; flex: 1; }"
        ),
        "    .case-body { padding: 1rem 1.05rem 1.15rem; }",
        "    .case-body p { margin: 0.38rem 0; }",
        "    details { margin-top: 0.7rem; }",
        "    details summary { cursor: pointer; color: var(--accent); }",
        "  </style>",
        "</head>",
        "<body>",
        '  <div class="nav">',
        '    <div class="nav-inner">',
        '      <a href="#summary">概览</a>',
        '      <a href="#coverage">覆盖矩阵</a>',
        '      <a href="#category">分类统计</a>',
        '      <a href="#backend">按 backend 统计</a>',
        '      <a href="#failure">auto fallback</a>',
        '      <a href="#details">详细结果</a>',
        "    </div>",
        "  </div>",
        '  <div class="page">',
        '    <section class="hero">',
        '      <span class="eyebrow">Real API Regression</span>',
        '      <h1>efinance-cli 第三轮真实 API 全量回归</h1>',
        (
            "      <p>本报告使用 <code>"
            f"{escape(str(VENV_PYTHON))}"
            "</code> 直接调用真实 CLI 与真实第三方 API，不使用 mock，"
            "不依赖系统全局解释器。</p>"
        ),
        (
            "      <p>开始时间: "
            f"{escape(payload['started_at'])} | 结束时间: "
            f"{escape(str(payload.get('finished_at') or '未完成'))} | "
            f"已执行: {len(results)} / {summary['total']}</p>"
        ),
        '      <div class="card-grid">',
        (
            '        <div class="stat-card"><div class="stat-num">'
            f"{summary['total']}"
            '</div><div class="stat-label">总用例</div></div>',
        ),
        (
            '        <div class="stat-card"><div class="stat-num" '
            'style="color: var(--ok)">'
            f"{summary['pass']}"
            '</div><div class="stat-label">通过</div></div>',
        ),
        (
            '        <div class="stat-card"><div class="stat-num" '
            'style="color: var(--danger)">'
            f"{summary['fail']}"
            '</div><div class="stat-label">失败</div></div>',
        ),
        (
            '        <div class="stat-card"><div class="stat-num" '
            'style="color: var(--warn)">'
            f"{summary['timeout']}"
            '</div><div class="stat-label">超时</div></div>',
        ),
        (
            '        <div class="stat-card"><div class="stat-num">'
            f"{summary['pass_rate']}%"
            '</div><div class="stat-label">通过率</div></div>',
        ),
        (
            '        <div class="stat-card"><div class="stat-num">'
            f"{summary['avg_duration_seconds']}s"
            '</div><div class="stat-label">平均耗时</div></div>',
        ),
        "      </div>",
        "    </section>",
        '    <section class="section" id="summary">',
        "      <h2>执行摘要</h2>",
        '      <div class="panel">',
        (
            "        <p><strong>Objective:</strong> 覆盖所有 backend 支持路径与"
            "CLI 真实调用 API 的关键运行模式与参数组合。</p>"
        ),
        (
            "        <p><strong>Verification:</strong> 逐条保留 stdout、"
            "stderr 与 backend 证据，并汇总失败归因。</p>"
        ),
        (
            '        <p class="muted">本报告对应真实外部依赖调用，重点观察接口波动、',
            '样本契约漂移与产品缺陷，不用 mock 隐藏真实问题。</p>',
        ),
        "      </div>",
        "    </section>",
        '    <section class="section" id="coverage">',
        "      <h2>覆盖矩阵</h2>",
        '      <div class="panel">',
        (
            "        <p><strong>命令入口数:</strong> "
            f"{summary['matrix']['expected_command_count']} ?</p>"
        ),
        (
            "        <p><strong>shared auto 覆盖:</strong> "
            f"{summary['matrix']['shared_auto_covered']} / "
            f"{summary['matrix']['shared_auto_target']} ?</p>"
        ),
        (
            "        <p><strong>显式 backend 覆盖:</strong> "
            f"{summary['matrix']['explicit_backend_covered']} / "
            f"{summary['matrix']['explicit_backend_target']} ?</p>"
        ),
        (
            "        <p><strong>业务参数覆盖:</strong> "
            f"{summary['matrix']['business_option_covered']} / "
            f"{summary['matrix']['business_option_target']} ?</p>"
        ),
        f'        <p><strong>运行模式:</strong> {escape(mode_text)}</p>',
        (
            "        <p><strong>默认路由样本:</strong> "
            f"{summary['matrix']['default_route_samples']}</p>"
        ),
        "      </div>",
        "    </section>",
        '    <section class="section" id="category">',
        "      <h2>分类统计</h2>",
        '      <div class="panel">',
        "        <table>",
        (
            "          <thead><tr><th>分类</th><th>总数</th><th>通过</th>"
            "<th>失败</th><th>超时</th><th>通过率</th></tr></thead>"
        ),
        "          <tbody>",
        f"{category_rows}",
        "          </tbody>",
        "        </table>",
        "      </div>",
        "    </section>",
        '    <section class="section" id="backend">',
        "      <h2>按 backend 统计</h2>",
        '      <div class="panel">',
        "        <table>",
        (
            "          <thead><tr><th>backend</th><th>总数</th><th>通过</th>"
            "<th>失败</th><th>超时</th><th>通过率</th></tr></thead>"
        ),
        "          <tbody>",
        f"{backend_rows}",
        "          </tbody>",
        "        </table>",
        "      </div>",
        "    </section>",
        '    <section class="section" id="failure">',
        "      <h2>auto fallback 统计</h2>",
        '      <div class="panel">',
        (
            "        <p><strong>auto 用例数:</strong> "
            f"{summary['auto_stats']['total']}</p>"
        ),
        (
            "        <p><strong>发生 fallback:</strong> "
            f"{summary['auto_stats']['fallback_used']}</p>"
        ),
        (
            "        <p><strong>无最终 backend 的失败数:</strong> "
            f"{summary['auto_stats']['all_failed_without_final_backend']}</p>"
        ),
        "        <table>",
        "          <thead><tr><th>最终 backend</th><th>次数</th></tr></thead>",
        "          <tbody>",
        f"{auto_rows}",
        "          </tbody>",
        "        </table>",
        "      </div>",
        "    </section>",
        '    <section class="section">',
        "      <h2>索引</h2>",
        '      <div class="panel">',
        f"        {build_case_index(results)}",
        "      </div>",
        "    </section>",
        '    <section class="section" id="details">',
        "      <h2>详细结果</h2>",
        '      <div class="panel">',
        (
            '        <p class="muted">以下详情保留完整 stdout 与 stderr，',
            '便于定位真实 API 失败原因。</p>',
        ),
        f"        {render_case_blocks(results)}",
        "      </div>",
        "    </section>",
        "  </div>",
        "</body>",
        "</html>",
    ]
    return "\n".join(html_lines) + "\n"


def write_text(path: Path, content: str) -> None:
    """以 UTF-8 无 BOM 写入文本。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def save_payload(
    cases: list[dict[str, Any]],
    results: list[dict[str, Any]],
    matrix: dict[str, Any],
    started_at: str,
    finished_at: str | None,
) -> None:
    """同步刷新 JSON 与 HTML 产物。"""

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
    write_text(
        RESULT_JSON,
        json.dumps(payload, ensure_ascii=False, indent=2),
    )
    write_text(
        RAW_JSON,
        json.dumps(
            {
                "started_at": started_at,
                "finished_at": finished_at,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
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
        print(
            f"[{index:03d}/{total:03d}] START {case['path']} "
            f"requested={case['backend']}",
            flush=True,
        )
        result = run_case(case)
        results.append(result)
        print(
            f"[{index:03d}/{total:03d}] {result['status']:<7} "
            f"{result['duration_seconds']:>8.3f}s {case['path']} "
            f"requested={case['backend']}",
            flush=True,
        )
        if result["failure_class"]:
            print(
                f"           failure={result['failure_class']}",
                flush=True,
            )
        save_payload(cases, results, matrix, started_at, None)
    finished_at = now_iso()
    save_payload(cases, results, matrix, started_at, finished_at)
    summary = summarize(results, matrix)
    print(
        f"完成: total={summary['total']} pass={summary['pass']} "
        f"fail={summary['fail']} timeout={summary['timeout']} "
        f"pass_rate={summary['pass_rate']}% html={REPORT_HTML}",
        flush=True,
    )


if __name__ == "__main__":
    main()
