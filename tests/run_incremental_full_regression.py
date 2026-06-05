"""增量全量真实回归执行器。

该脚本使用项目虚拟环境调用真实 CLI 与真实第三方 API，覆盖当前仓库声明的
全部叶子命令、共享命令的全部支持 backend，以及代表性运行时模式与命令专属参数。
它会在每条用例完成后立刻刷新 JSON 与 HTML 报告，确保长时间执行过程中可以持续查看阶段性结果。
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import click

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_provider_factory = importlib.import_module("opentrade.backends.factory")
_command_catalog = importlib.import_module("opentrade.command_catalog")
_command_module = importlib.import_module("opentrade.commands")
_regression_reporting = importlib.import_module("tests.regression_reporting")
_cli_support = importlib.import_module("tests.cli_regression_support")

list_provider_extension_commands = (
    _provider_factory.list_provider_extension_commands
)
SHARED_COMMANDS = _command_catalog.SHARED_COMMANDS
get_shared_command_definition = _command_catalog.get_shared_command_definition
create_root_command = _command_module.create_root_command
create_search_command = _command_module.create_search_command
classify_regression_failure = (
    _regression_reporting.classify_regression_failure
)
detect_auto_fallback = _regression_reporting.detect_auto_fallback
extract_backend_meta_from_payload = (
    _regression_reporting.extract_backend_meta_from_payload
)
RUNTIME_EXECUTION_OPTION_NAMES = (
    _cli_support.RUNTIME_EXECUTION_OPTION_NAMES
)
RUNTIME_OUTPUT_OPTION_NAMES = _cli_support.RUNTIME_OUTPUT_OPTION_NAMES
RUNTIME_WATCH_OPTION_NAMES = _cli_support.RUNTIME_WATCH_OPTION_NAMES
collect_leaf_commands = _cli_support.collect_leaf_commands

TZ = ZoneInfo("Asia/Shanghai")
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
CLI_PREFIX = [str(VENV_PYTHON), "-X", "utf8", "-m", "opentrade"]
DOCS_DIR = PROJECT_ROOT / "docs"
ARTIFACT_DIR = DOCS_DIR / "20260601-second-regression-artifacts"
REPORT_JSON_PATH = DOCS_DIR / "20260601-second-regression-results.json"
REPORT_HTML_PATH = DOCS_DIR / "20260601-第二次测试结论.html"
REPORT_VERSION = "2026-06-03.incremental-v8"
CASE_DATA_PATH = (
    PROJECT_ROOT / "tests" / "data" / "incremental_full_regression_cases.json"
)
DEFAULT_TIMEOUT_SECONDS = 180
WATCH_TIMEOUT_SECONDS = 45
PROXY_ENV_KEYS = {
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
}
STDERR_IGNORE_PATTERNS = (
    re.compile(r"^\s*0%\|"),
    re.compile(r"^\s*100%\|"),
    re.compile(r"it/s"),
    re.compile(r"FutureWarning:"),
    re.compile(r"UserWarning:"),
    re.compile(r"DeprecationWarning:"),
    re.compile(r"InsecureRequestWarning:"),
)
REQUIRED_RUNTIME_TAGS = {
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


@dataclass(slots=True)
class CaseSpec:
    """描述一条真实 CLI 回归用例。"""

    case_id: str
    title: str
    command_path: str
    args_text: str
    requested_backend: str | None
    category: str
    note: str
    mode_tags: list[str] = field(default_factory=list)
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    artifact_paths: list[str] = field(default_factory=list)
    tokens: list[str] = field(default_factory=list)

    def command_text(self) -> str:
        return subprocess.list2cmdline(CLI_PREFIX + self.tokens)


@dataclass(slots=True)
class CaseResult:
    """保存单条用例的完整执行结果。"""

    case_id: str
    title: str
    command_path: str
    category: str
    requested_backend: str | None
    note: str
    mode_tags: list[str]
    command_text: str
    started_at: str
    finished_at: str
    duration_seconds: float
    timeout_seconds: int
    returncode: int | None
    status: str
    failure_class: str | None
    failure_reason: str | None
    stdout: str
    stderr: str
    backend_meta: dict[str, Any]
    auto_fallback_used: bool
    artifact_reports: list[dict[str, Any]]


def iso_now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def build_case_id(command_path: str, backend: str | None) -> str:
    return f"{command_path.replace(' ', '-')}__{backend or 'none'}"


def make_case(
    command_path: str,
    backend: str | None,
    args_text: str,
    note: str,
    mode_tags: list[str] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    artifact_paths: list[str] | None = None,
    tokens: list[str] | None = None,
) -> CaseSpec:
    actual_tokens = list(tokens or [])
    actual_args_text = args_text
    if not actual_tokens and actual_args_text:
        actual_tokens = shlex.split(actual_args_text, posix=True)
    if not actual_args_text and actual_tokens:
        actual_args_text = subprocess.list2cmdline(actual_tokens)
    return CaseSpec(
        case_id=build_case_id(command_path, backend),
        title=f"{command_path} [{backend}]" if backend else command_path,
        command_path=command_path,
        args_text=actual_args_text,
        requested_backend=backend,
        category=command_path.split()[0],
        note=note,
        mode_tags=mode_tags or [],
        timeout_seconds=timeout_seconds,
        artifact_paths=artifact_paths or [],
        tokens=actual_tokens,
    )


def build_cases() -> list[CaseSpec]:
    """从 JSON 用例文件构建增量全量回归矩阵。"""

    raw_cases = json.loads(CASE_DATA_PATH.read_text(encoding="utf-8"))
    cases: list[CaseSpec] = []
    for item in raw_cases:
        cases.append(
            make_case(
                command_path=str(item["command_path"]),
                backend=item.get("requested_backend"),
                args_text=str(item.get("args_text") or ""),
                note=str(item["note"]),
                mode_tags=list(item.get("mode_tags") or []),
                timeout_seconds=int(
                    item.get("timeout_seconds")
                    or DEFAULT_TIMEOUT_SECONDS
                ),
                artifact_paths=list(item.get("artifact_paths") or []),
                tokens=[
                    str(token)
                    for token in item.get("tokens") or []
                ],
            )
        )
    return cases


def collect_command_objects() -> dict[str, click.Command]:
    """收集当前 CLI 暴露的全部叶子命令对象。"""

    command_map: dict[str, click.Command] = {"search": create_search_command()}
    for leaf in collect_leaf_commands(create_root_command()):
        command_map[" ".join(leaf.path)] = leaf.command
    return command_map


def list_primary_business_option_names(command: click.Command) -> set[str]:
    runtime_names = (
        RUNTIME_EXECUTION_OPTION_NAMES
        | RUNTIME_OUTPUT_OPTION_NAMES
        | RUNTIME_WATCH_OPTION_NAMES
    )
    names: set[str] = set()
    for parameter in command.params:
        if (
            isinstance(parameter, click.Option)
            and parameter.name not in runtime_names
        ):
            names.add(str(parameter.name))
    return names


def normalize_present_options(
    command: click.Command,
    args_text: str,
) -> set[str]:
    lookup: dict[str, str] = {}
    runtime_names = (
        RUNTIME_EXECUTION_OPTION_NAMES
        | RUNTIME_OUTPUT_OPTION_NAMES
        | RUNTIME_WATCH_OPTION_NAMES
    )
    for parameter in command.params:
        if not isinstance(parameter, click.Option):
            continue
        if parameter.name in runtime_names:
            continue
        for opt in parameter.opts:
            lookup[opt] = str(parameter.name)
        for opt in parameter.secondary_opts:
            lookup[opt] = str(parameter.name)

    present: set[str] = set()
    for token in shlex.split(args_text, posix=True):
        if token in lookup:
            present.add(lookup[token])
    return present


def validate_case_matrix(cases: list[CaseSpec]) -> None:
    command_map = collect_command_objects()
    actual_paths = {case.command_path for case in cases}
    missing_commands = sorted(set(command_map) - actual_paths)
    if missing_commands:
        raise RuntimeError(f"回归矩阵缺少命令覆盖: {missing_commands}")

    definition_map = {
        "search": get_shared_command_definition("instrument.search")}
    for definition in SHARED_COMMANDS:
        path_text = " ".join(definition.cli_path)
        if path_text == "instrument search":
            path_text = "search"
        definition_map[path_text] = definition
    for definition in list_provider_extension_commands():
        definition_map[" ".join(definition.cli_path)] = definition

    backend_coverage: dict[str, set[str | None]] = defaultdict(set)
    option_coverage: dict[str, set[str]] = defaultdict(set)
    runtime_tags: set[str] = set()
    for case in cases:
        backend_coverage[case.command_path].add(case.requested_backend)
        runtime_tags.update(case.mode_tags)
        command = command_map.get(case.command_path)
        if command is not None:
            option_coverage[case.command_path].update(
                normalize_present_options(command, case.args_text)
            )

    for command_path, definition in definition_map.items():
        if command_path == "watch":
            continue
        expected = {item.value for item in definition.supported_backends}
        if len(expected) >= 2 or command_path == "search":
            expected.add("auto")
        actual = {item for item in backend_coverage.get(
            command_path, set()) if item is not None}
        missing = sorted(expected - actual)
        if missing:
            raise RuntimeError(f"命令 {command_path} 缺少 backend 覆盖: {missing}")

    for command_path, command in command_map.items():
        expected_options = list_primary_business_option_names(command)
        actual_options = option_coverage.get(command_path, set())
        missing = sorted(expected_options - actual_options)
        if missing:
            raise RuntimeError(f"命令 {command_path} 缺少业务参数覆盖: {missing}")

    missing_runtime_tags = sorted(REQUIRED_RUNTIME_TAGS - runtime_tags)
    if missing_runtime_tags:
        raise RuntimeError(f"回归矩阵缺少运行时模式覆盖: {missing_runtime_tags}")


def fresh_outputs() -> None:
    if REPORT_JSON_PATH.exists():
        REPORT_JSON_PATH.unlink()
    if REPORT_HTML_PATH.exists():
        REPORT_HTML_PATH.unlink()
    if ARTIFACT_DIR.exists():
        shutil.rmtree(ARTIFACT_DIR)


def build_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in PROXY_ENV_KEYS:
        env.pop(key, None)
    env["PYTHONUTF8"] = "1"
    return env


def is_meaningful_stderr(stderr: str) -> bool:
    for raw_line in stderr.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if any(pattern.search(line) for pattern in STDERR_IGNORE_PATTERNS):
            continue
        return True
    return False


def try_parse_json(stdout: str) -> Any | None:
    text = stdout.strip()
    if not text:
        return None
    if not (text.startswith("{") or text.startswith("[")):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def extract_backend_meta(parsed: Any) -> dict[str, Any]:
    """从 raw/json 结果中提取 backend 元数据与 limit 证据。"""

    return extract_backend_meta_from_payload(parsed)


def classify_failure(
    command_path: str,
    requested_backend: str | None,
    stdout: str,
    stderr: str,
    returncode: int | None,
    status: str,
    backend_meta: dict[str, Any],
    artifact_reports: list[dict[str, Any]],
) -> tuple[str | None, str | None]:
    """按统一规则推断当前回归结果的失败分类与摘要。"""

    return classify_regression_failure(
        command_path=command_path,
        requested_backend=requested_backend,
        stdout=stdout,
        stderr=stderr,
        returncode=returncode,
        status=status,
        backend_meta=backend_meta,
        artifact_reports=artifact_reports,
    )


def build_artifact_reports(paths: list[str]) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            reports.append({"path": str(path), "exists": False,
                           "kind": "missing", "size": None, "members": []})
            continue
        if path.is_file():
            reports.append(
                {
                    "path": str(path),
                    "exists": True,
                    "kind": "file",
                    "size": path.stat().st_size,
                    "members": [],
                }
            )
            continue
        members = sorted(str(item.relative_to(path))
                         for item in path.rglob("*") if item.is_file())
        total_size = sum(
            item.stat().st_size for item in path.rglob("*") if item.is_file())
        reports.append(
            {
                "path": str(path),
                "exists": True,
                "kind": "directory",
                "size": total_size,
                "members": members,
            }
        )
    return reports


def run_case(case: CaseSpec) -> CaseResult:
    command = CLI_PREFIX + case.tokens
    started_at = iso_now()
    begin = time.perf_counter()
    stdout = ""
    stderr = ""
    returncode: int | None = None
    status = "pass"
    backend_meta: dict[str, Any] = {}
    auto_fallback_used = False
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=case.timeout_seconds,
            env=build_subprocess_env(),
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        returncode = completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else (
            exc.stdout or b"").decode("utf-8", errors="replace")
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else (
            exc.stderr or b"").decode("utf-8", errors="replace")
        status = "timeout"

    finished_at = iso_now()
    duration_seconds = round(time.perf_counter() - begin, 3)
    artifact_reports = build_artifact_reports(case.artifact_paths)
    if status != "timeout":
        parsed = try_parse_json(stdout)
        backend_meta = extract_backend_meta(parsed)
        auto_fallback_used = detect_auto_fallback(
            case.requested_backend, backend_meta)
        missing_artifact = any(not item["exists"] for item in artifact_reports)
        expects_json = (
            "--format" in case.args_text
            and "json" in case.args_text
        )
        if returncode != 0:
            status = "fail"
        elif (
            missing_artifact
            or (expects_json and parsed is None)
            or is_meaningful_stderr(stderr)
        ):
            status = "degraded"
        else:
            status = "pass"

    failure_class, failure_reason = classify_failure(
        case.command_path,
        case.requested_backend,
        stdout,
        stderr,
        returncode,
        status,
        backend_meta,
        artifact_reports,
    )
    return CaseResult(
        case_id=case.case_id,
        title=case.title,
        command_path=case.command_path,
        category=case.category,
        requested_backend=case.requested_backend,
        note=case.note,
        mode_tags=case.mode_tags,
        command_text=subprocess.list2cmdline(command),
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=duration_seconds,
        timeout_seconds=case.timeout_seconds,
        returncode=returncode,
        status=status,
        failure_class=failure_class,
        failure_reason=failure_reason,
        stdout=stdout,
        stderr=stderr,
        backend_meta=backend_meta,
        auto_fallback_used=auto_fallback_used,
        artifact_reports=artifact_reports,
    )


def load_existing_results() -> dict[str, Any]:
    if not REPORT_JSON_PATH.exists():
        return {}
    try:
        return json.loads(REPORT_JSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def serialize_result(result: CaseResult) -> dict[str, Any]:
    return asdict(result)


def build_summary(
    results: list[dict[str, Any]],
    total_cases: int,
) -> dict[str, Any]:
    counter = Counter(item["status"] for item in results)
    backend_counter = Counter()
    failure_class_counter = Counter()
    category_counter: dict[str, Counter[str]] = defaultdict(Counter)
    runtime_tag_counter = Counter()
    auto_total = auto_success = auto_fallback_used = auto_fallback_success = 0
    total_duration = 0.0
    for item in results:
        total_duration += float(item["duration_seconds"])
        backend_counter[item.get("requested_backend") or "none"] += 1
        if item.get("failure_class"):
            failure_class_counter[str(item["failure_class"])] += 1
        category_counter[item["category"]][item["status"]] += 1
        for tag in item.get("mode_tags", []):
            runtime_tag_counter[tag] += 1
        if item.get("requested_backend") == "auto":
            auto_total += 1
            if item["status"] in {"pass", "degraded"}:
                auto_success += 1
            if item.get("auto_fallback_used"):
                auto_fallback_used += 1
                if item["status"] in {"pass", "degraded"}:
                    auto_fallback_success += 1

    strict_pass_rate = (
        counter["pass"] / total_cases * 100.0) if total_cases else 0.0
    effective_success_rate = (
        (counter["pass"] + counter["degraded"]) / total_cases * 100.0
        if total_cases
        else 0.0
    )
    progress_rate = (len(results) / total_cases *
                     100.0) if total_cases else 0.0
    return {
        "total_cases": total_cases,
        "completed_cases": len(results),
        "remaining_cases": max(total_cases - len(results), 0),
        "progress_rate": round(progress_rate, 1),
        "strict_pass": counter["pass"],
        "degraded": counter["degraded"],
        "fail": counter["fail"],
        "timeout": counter["timeout"],
        "strict_pass_rate": round(strict_pass_rate, 1),
        "effective_success_rate": round(effective_success_rate, 1),
        "completed_duration_seconds": round(total_duration, 3),
        "backend_counter": dict(backend_counter),
        "failure_class_counter": dict(failure_class_counter),
        "failure_counter": dict(failure_class_counter),
        "runtime_tag_counter": dict(runtime_tag_counter),
        "category_counter": {
            key: dict(value)
            for key, value in sorted(category_counter.items())
        },
        "auto_stats": {
            "total": auto_total,
            "successful": auto_success,
            "fallback_used": auto_fallback_used,
            "fallback_successful": auto_fallback_success,
        },
    }


def build_json_payload(
    cases: list[CaseSpec],
    completed: dict[str, dict[str, Any]],
    run_started_at: str,
) -> dict[str, Any]:
    ordered_results = [completed[case.case_id]
                       for case in cases if case.case_id in completed]
    summary = build_summary(ordered_results, len(cases))
    return {
        "report_version": REPORT_VERSION,
        "project_root": str(PROJECT_ROOT),
        "python_executable": str(VENV_PYTHON),
        "run_started_at": run_started_at,
        "last_updated_at": iso_now(),
        "methodology": {
            "definition": [
                "每个命令入口至少一条真实调用。",
                "每个命令声明支持的 backend 至少一条显式调用。",
                "多 backend 命令额外覆盖 backend auto。",
                "每个命令专属可选参数至少在一条真实调用中出现一次。",
                (
                    "运行时模式覆盖 format、view raw、watch、output、"
                    "encoding、indicator-level、trace-window、full、"
                    "transpose、no-index。"
                ),
            ],
            "environment": {
                "cwd": str(PROJECT_ROOT),
                "python": str(VENV_PYTHON),
                "proxy_keys_cleared": sorted(PROXY_ENV_KEYS),
                "real_api": True,
                "mock_used": False,
            },
        },
        "summary": summary,
        "cases": [asdict(case) for case in cases],
        "results": ordered_results,
    }


def render_counter_table(
    counter_map: dict[str, int],
    left: str,
    right: str,
) -> str:
    """渲染简单键值计数表。"""

    rows = [
        f"<tr><th>{escape(left)}</th><th>{escape(right)}</th></tr>"
    ]
    for key, value in sorted(
        counter_map.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        rows.append(
            f"<tr><td>{escape(str(key))}</td><td>{value}</td></tr>"
        )
    return "\n".join(rows)


def render_category_table(summary: dict[str, Any]) -> str:
    """渲染按命令分类聚合的统计表格。"""

    rows = [
        (
            "<tr><th>分类</th><th>通过</th><th>降级</th><th>失败</th>"
            "<th>超时</th><th>有效成功率</th></tr>"
        )
    ]
    for category, counter in summary["category_counter"].items():
        success = counter.get("pass", 0) + counter.get("degraded", 0)
        total = sum(counter.values())
        rate = (success / total * 100.0) if total else 0.0
        rows.append(
            "<tr>"
            f"<td>{escape(category)}</td>"
            f"<td>{counter.get('pass', 0)}</td>"
            f"<td>{counter.get('degraded', 0)}</td>"
            f"<td>{counter.get('fail', 0)}</td>"
            f"<td>{counter.get('timeout', 0)}</td>"
            f"<td>{rate:.1f}%</td>"
            "</tr>"
        )
    return "\n".join(rows)


def render_artifacts(reports: list[dict[str, Any]]) -> str:
    """渲染用例执行过程中产生的副作用产物信息。"""

    if not reports:
        return ""
    chunks = ["<div class='artifact-list'><strong>副作用产物</strong>"]
    for item in reports:
        status = "已生成" if item["exists"] else "缺失"
        chunks.append(
            (
                "<div class='artifact-item'>"
                f"<div><code>{escape(item['path'])}</code>"
                f" · {status} · {escape(item['kind'])}</div>"
                f"<div>大小: {item['size']}</div>"
                "</div>"
            )
        )
        if item["members"]:
            chunks.append(
                "<details><summary>目录文件清单</summary>"
                f"<pre>{escape(chr(10).join(item['members']))}</pre>"
                "</details>"
            )
    chunks.append("</div>")
    return "\n".join(chunks)


def render_case_card(index: int, result: dict[str, Any]) -> str:
    """渲染单条回归结果卡片。"""

    status = result["status"]
    class_name = {
        "pass": "ok",
        "degraded": "warn",
        "fail": "danger",
        "timeout": "danger",
    }[status]
    status_text = {
        "pass": "PASS",
        "degraded": "DEGRADED",
        "fail": "FAIL",
        "timeout": "TIMEOUT",
    }[status]
    backend_meta = result.get("backend_meta") or {}
    backend_text = result.get("requested_backend") or "none"
    if backend_meta.get("final_backend"):
        backend_text = f"{backend_text} -> {backend_meta['final_backend']}"

    stdout_text = result["stdout"] if result["stdout"] else "<empty>"
    stderr_text = result["stderr"] if result["stderr"] else "<empty>"
    lines = [
        f"<article class='test-case' id='case-{index}'>",
        f"  <div class='test-header {class_name}'>",
        f"    <span class='test-id'>#{index}</span>",
        f"    <span class='test-title'>{escape(result['title'])}</span>",
        f"    <span class='test-status'>{status_text}</span>",
        (
            "    <span class='test-time'>"
            f"{result['duration_seconds']:.3f}s</span>"
        ),
        "  </div>",
        "  <div class='test-meta'>",
        (
            "    <div><strong>命令路径:</strong> <code>"
            f"{escape(result['command_path'])}</code></div>"
        ),
        (
            "    <div><strong>backend:</strong> <code>"
            f"{escape(backend_text)}</code></div>"
        ),
        (
            "    <div><strong>失败归类:</strong> <code>"
            f"{escape(result.get('failure_class') or '-')}</code></div>"
        ),
        (
            "    <div><strong>开始/结束:</strong> "
            f"{escape(result['started_at'])} / "
            f"{escape(result['finished_at'])}</div>"
        ),
        "  </div>",
        f"  <div class='test-note'>{escape(result['note'])}</div>",
    ]
    if result.get("auto_fallback_used"):
        lines.append(
            "  <div class='test-note'>检测到 auto 请求发生 fallback。</div>"
        )
    lines.extend(
        [
            "  <details class='cli-command'>",
            "    <summary>执行命令</summary>",
            f"    <pre>{escape(result['command_text'])}</pre>",
            "  </details>",
        ]
    )

    artifacts_html = render_artifacts(result.get("artifact_reports") or [])
    if artifacts_html:
        lines.append(f"  {artifacts_html}")

    lines.extend(
        [
            "  <details class='stdout-block' open>",
            "    <summary>stdout（原始 CLI 输出）</summary>",
            f"    <pre>{escape(stdout_text)}</pre>",
            "  </details>",
            "  <details class='stderr-block'>",
            "    <summary>stderr（原始 CLI 输出）</summary>",
            f"    <pre>{escape(stderr_text)}</pre>",
            "  </details>",
            "</article>",
        ]
    )
    return "\n".join(lines)


def build_html_report(payload: dict[str, Any]) -> str:
    """构建增量全量回归 HTML 报告。"""

    summary = payload["summary"]
    methodology = payload["methodology"]
    progress_label = (
        "进行中"
        if summary["completed_cases"] < summary["total_cases"]
        else "已完成"
    )
    auto_stats = summary["auto_stats"]
    methodology_items = "".join(
        f"<li>{escape(item)}</li>"
        for item in methodology["definition"]
    )
    proxy_keys = ", ".join(methodology["environment"]["proxy_keys_cleared"])
    real_api_text = "是" if methodology["environment"]["real_api"] else "否"
    mock_used_text = "是" if methodology["environment"]["mock_used"] else "否"
    result_cards = "\n".join(
        render_case_card(index, result)
        for index, result in enumerate(payload["results"], start=1)
    )
    empty_state = (
        "<div class='panel'>当前尚无已完成用例，报告会在执行过程中持续"
        "刷新。</div>"
    )
    html_lines = [
        "<!DOCTYPE html>",
        "<html lang='zh-CN'>",
        "<head>",
        "  <meta charset='utf-8'>",
        (
            "  <meta name='viewport' content='width=device-width, "
            "initial-scale=1'>"
        ),
        "  <title>efinance-cli 第二次全量真实回归测试</title>",
        "  <style>",
        "    :root {",
        "      --bg: #eef4f7;",
        "      --paper: rgba(255, 255, 255, 0.94);",
        "      --ink: #182431;",
        "      --muted: #4c5d69;",
        "      --line: rgba(58, 84, 104, 0.18);",
        "      --accent: #315f7d;",
        "      --ok: #1f6b54;",
        "      --ok-bg: #e7f4ed;",
        "      --warn: #8c6117;",
        "      --warn-bg: #fdf2df;",
        "      --danger: #8b3138;",
        "      --danger-bg: #fae6e7;",
        "      --code-bg: #152433;",
        "      --code-text: #edf5fb;",
        "    }",
        "    * { box-sizing: border-box; }",
        "    body {",
        "      margin: 0;",
        "      color: var(--ink);",
        (
            "      background: radial-gradient(circle at top right, "
            "rgba(64, 110, 140, 0.18), transparent 22%),"
        ),
        "        linear-gradient(180deg, #eaf1f5 0%, var(--bg) 100%);",
        (
            "      font-family: 'Georgia', 'Times New Roman', "
            "'Noto Serif SC', serif;"
        ),
        "      line-height: 1.85;",
        "    }",
        "    code, pre {",
        "      font-family: 'Cascadia Code', 'Consolas', monospace;",
        "    }",
        "    .nav {",
        "      position: sticky;",
        "      top: 0;",
        "      z-index: 10;",
        "      display: flex;",
        "      gap: 1rem;",
        "      flex-wrap: wrap;",
        "      padding: 0.75rem 1rem;",
        "      background: rgba(255, 255, 255, 0.88);",
        "      backdrop-filter: blur(10px);",
        "      border-bottom: 1px solid var(--line);",
        "    }",
        "    .nav a { color: var(--accent); text-decoration: none; }",
        (
            "    .page { max-width: 1240px; margin: 0 auto; "
            "padding: 28px 18px 72px; }"
        ),
        "    .hero, .panel {",
        "      padding: 1rem 1.15rem;",
        "      border: 1px solid var(--line);",
        "      border-radius: 14px;",
        "      background: var(--paper);",
        "      box-shadow: 0 10px 28px rgba(32, 48, 61, 0.05);",
        "    }",
        "    .hero h1 {",
        "      margin: 0 0 0.5rem;",
        "      color: var(--accent);",
        "      font-size: 2.2rem;",
        "    }",
        "    .hero p { margin: 0.55rem 0; color: var(--muted); }",
        "    .cards {",
        "      display: grid;",
        "      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));",
        "      gap: 0.9rem;",
        "      margin: 1.5rem 0;",
        "    }",
        "    .card {",
        "      padding: 1rem 1.15rem;",
        "      border: 1px solid var(--line);",
        "      border-radius: 14px;",
        "      background: var(--paper);",
        "      box-shadow: 0 10px 28px rgba(32, 48, 61, 0.05);",
        "    }",
        "    .card .num {",
        "      font-size: 2rem;",
        "      font-weight: 700;",
        "      margin-bottom: 0.2rem;",
        "    }",
        "    .num-ok { color: var(--ok); }",
        "    .num-warn { color: var(--warn); }",
        "    .num-danger { color: var(--danger); }",
        "    .hero-grid {",
        "      display: grid;",
        "      grid-template-columns: 2fr 1fr;",
        "      gap: 1.2rem;",
        "      margin-top: 1.2rem;",
        (
            "    table { width: 100%; border-collapse: collapse; "
            "margin-top: 0.8rem; }"
        ),
        "    .section { margin-top: 2rem; }",
        "    .section h2 { color: var(--accent); margin-bottom: 0.7rem; }",
        (
            "    .test-id { font-weight: 700; color: var(--muted); "
            "min-width: 2rem; }"
        ),
        "    th, td {",
        "      padding: 0.65rem 0.8rem;",
        "      text-align: left;",
        "      border-bottom: 1px solid var(--line);",
        "      vertical-align: top;",
        "    }",
        "    th { background: #f1f6f9; }",
        "    ul { margin: 0.5rem 0 0.2rem 1.1rem; padding: 0; }",
        "    pre {",
        "      margin: 0.5rem 0 0;",
        "      padding: 1rem 1.1rem;",
        "      white-space: pre-wrap;",
        "      word-break: break-word;",
        "      overflow-x: auto;",
        "      border-radius: 10px;",
        "      background: var(--code-bg);",
        "      color: var(--code-text);",
        "      font-size: 0.84rem;",
        "      line-height: 1.55;",
        "    }",
        "    details summary { cursor: pointer; color: var(--accent); }",
        "    .test-case {",
        "      margin-top: 1rem;",
        "      border: 1px solid var(--line);",
        "      border-radius: 14px;",
        "      background: var(--paper);",
        "      overflow: hidden;",
        "      box-shadow: 0 12px 32px rgba(27, 40, 49, 0.05);",
        "    }",
        "    .test-header {",
        "      display: flex;",
        "      flex-wrap: wrap;",
        "      gap: 0.75rem;",
        "      align-items: center;",
        "      padding: 0.9rem 1rem;",
        "      font-size: 0.92rem;",
        "    }",
        "    .test-header.ok {",
        "      background: var(--ok-bg);",
        "      border-left: 5px solid var(--ok);",
        "    }",
        "    .test-header.warn {",
        "      background: var(--warn-bg);",
        (
            "    .test-id { font-weight: 700; color: var(--muted); "
            "min-width: 2rem; }"
        ),
        "    }",
        "    .test-header.danger {",
        "      background: var(--danger-bg);",
        "      border-left: 5px solid var(--danger);",
        "    }",
        "    .test-title { flex: 1; font-weight: 700; }",
        "    .test-status { font-weight: 700; }",
        "    .test-time { color: var(--muted); }",
        (
            "    .test-meta, .test-note, .artifact-list, .cli-command, "
            ".stdout-block, .stderr-block { padding: 0.7rem 1rem 0.2rem; }"
        ),
        "    .test-meta {",
        "      display: grid;",
        "      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));",
        "      gap: 0.4rem 1rem;",
        "      font-size: 0.9rem;",
        "    }",
        "    .artifact-item { margin-top: 0.45rem; color: var(--muted); }",
        "    .footer-note { color: var(--muted); font-size: 0.9rem; }",
        "    @media (max-width: 880px) {",
        "      .hero-grid { grid-template-columns: 1fr; }",
        "    }",
        "  </style>",
        "</head>",
        "<body>",
        "  <nav class='nav'>",
        "    <a href='#summary'>概览</a>",
        "    <a href='#methodology'>方法学</a>",
        "    <a href='#stats'>统计</a>",
        "    <a href='#results'>逐条结果</a>",
        "  </nav>",
        "  <main class='page'>",
        "    <section class='hero' id='summary'>",
        "      <h1>efinance-cli 第二次全量真实 API 回归测试</h1>",
        (
            "      <p>状态: <strong>"
            f"{escape(progress_label)}</strong> · 版本: "
            f"<code>{escape(payload['report_version'])}</code> · 最后刷新: "
            f"{escape(payload['last_updated_at'])}</p>"
        ),
        (
            "      <p>本报告使用 <code>"
            f"{escape(payload['python_executable'])}</code> 调用真实 CLI 与"
            "真实第三方 API，不使用 mock，不使用系统全局解释器。</p>"
        ),
        "      <div class='cards'>",
        (
            "        <div class='card'><div class='num'>"
            f"{summary['completed_cases']}/{summary['total_cases']}"
            "</div><div>已完成 / 总用例</div></div>"
        ),
        (
            "        <div class='card'><div class='num'>"
            f"{summary['progress_rate']:.1f}%"
            "</div><div>进度</div></div>"
        ),
        (
            "        <div class='card'><div class='num num-ok'>"
            f"{summary['strict_pass']}"
            "</div><div>严格通过</div></div>"
        ),
        (
            "        <div class='card'><div class='num num-warn'>"
            f"{summary['degraded']}"
            "</div><div>降级通过</div></div>"
        ),
        (
            "        <div class='card'><div class='num num-danger'>"
            f"{summary['fail']}"
            "</div><div>失败</div></div>"
        ),
        (
            "        <div class='card'><div class='num num-danger'>"
            f"{summary['timeout']}"
            "</div><div>超时</div></div>"
        ),
        (
            "        <div class='card'><div class='num'>"
            f"{summary['strict_pass_rate']:.1f}%"
            "</div><div>严格通过率</div></div>"
        ),
        (
            "        <div class='card'><div class='num'>"
            f"{summary['effective_success_rate']:.1f}%"
            "</div><div>有效成功率</div></div>"
        ),
        "      </div>",
        "      <div class='hero-grid'>",
        "        <div class='panel'>",
        "          <strong>当前工程定义</strong>",
        "          <ul>",
        (
            "            <li>全量不是参数数学穷举，而是命令入口、支持 "
            "backend、关键运行模式与命令专属参数的完整真实覆盖。</li>"
        ),
        (
            "            <li>每条结果都保留完整 stdout 与 stderr，报告在"
            "执行过程中持续刷新。</li>"
        ),
        (
            "            <li>执行器会清空代理环境变量，避免代理污染真实"
            "可用性判断。</li>"
        ),
        "          </ul>",
        "        </div>",
        "        <div class='panel'>",
        "          <strong>auto 兜底实时统计</strong>",
        "          <ul>",
        f"            <li>auto 用例总数: {auto_stats['total']}</li>",
        f"            <li>auto 成功数: {auto_stats['successful']}</li>",
        (
            "            <li>检测到 fallback 的用例数: "
            f"{auto_stats['fallback_used']}</li>"
        ),
        (
            "            <li>fallback 后仍成功的用例数: "
            f"{auto_stats['fallback_successful']}</li>"
        ),
        "          </ul>",
        "        </div>",
        "      </div>",
        "    </section>",
        "    <section class='section' id='methodology'>",
        "      <h2>方法学</h2>",
        "      <div class='panel'>",
        f"        <ul>{methodology_items}</ul>",
        "        <table>",
        "          <tr><th>项目</th><th>值</th></tr>",
        (
            "          <tr><td>项目目录</td><td><code>"
            f"{escape(methodology['environment']['cwd'])}</code></td></tr>"
        ),
        (
            "          <tr><td>Python 解释器</td><td><code>"
            f"{escape(methodology['environment']['python'])}</code></td></tr>"
        ),
        (
            "          <tr><td>真实 API</td><td>"
            f"{real_api_text}</td></tr>"
        ),
        (
            "          <tr><td>Mock</td><td>"
            f"{mock_used_text}</td></tr>"
        ),
        (
            "          <tr><td>已清理代理变量</td><td><code>"
            f"{escape(proxy_keys)}</code></td></tr>"
        ),
        "        </table>",
        "      </div>",
        "    </section>",
        "    <section class='section' id='stats'>",
        "      <h2>统计</h2>",
        "      <div class='panel'>",
        "        <h3>分类统计</h3>",
        f"        <table>{render_category_table(summary)}</table>",
        "      </div>",
        "      <div class='panel' style='margin-top:1rem;'>",
        "        <h3>失败归类</h3>",
        (
            "        <table>"
            f"{render_counter_table(summary['failure_counter'], '失败归类', '次数')}"
            "</table>"
        ),
        "      </div>",
        "      <div class='panel' style='margin-top:1rem;'>",
        "        <h3>请求 backend 分布</h3>",
        (
            "        <table>"
            f"{render_counter_table(
                summary['backend_counter'],
                'requested_backend',
                '用例数',
            )}"
            "</table>"
        ),
        "      </div>",
        "      <div class='panel' style='margin-top:1rem;'>",
        "        <h3>运行模式命中统计</h3>",
        (
            "        <table>"
            f"{render_counter_table(
                summary['runtime_tag_counter'],
                '运行模式',
                '命中次数',
            )}"
            "</table>"
        ),
        "      </div>",
        "    </section>",
        "    <section class='section' id='results'>",
        "      <h2>逐条结果</h2>",
        (
            "      <p class='footer-note'>stdout 与 stderr 保留原始 CLI 输出。"
            "降级通过表示退出码可能为 0，但 stderr、产物或观测信息仍有"
            "风险信号。</p>"
        ),
        f"      {result_cards if result_cards else empty_state}",
        "    </section>",
        "  </main>",
        "</body>",
        "</html>",
    ]
    return "\n".join(html_lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="执行增量全量真实 API 回归测试。")
    parser.add_argument("--fresh", action="store_true",
                        help="删除本执行器生成的 JSON、HTML 与产物目录后重新开始。")
    parser.add_argument("--max-cases", type=int,
                        default=None, help="仅执行前 N 条尚未完成的用例。")
    return parser.parse_args()


def main() -> int:
    if not VENV_PYTHON.exists():
        raise SystemExit(f"项目虚拟环境解释器不存在: {VENV_PYTHON}")
    args = parse_args()
    if args.fresh:
        fresh_outputs()
    cases = build_cases()
    validate_case_matrix(cases)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    existing = load_existing_results()
    run_started_at = str(existing.get("run_started_at") or iso_now())
    completed = {
        item["case_id"]: item
        for item in existing.get("results", [])
        if isinstance(item, dict) and item.get("case_id")
    }
    flush_reports(cases, completed, run_started_at)

    remaining = [case for case in cases if case.case_id not in completed]
    if args.max_cases is not None:
        remaining = remaining[: args.max_cases]

    print(f"[regression] using python: {VENV_PYTHON}")
    print(f"[regression] total cases: {len(cases)}")
    print(f"[regression] already completed: {len(completed)}")
    print(f"[regression] executing now: {len(remaining)}")
    print(f"[regression] html report: {REPORT_HTML_PATH}")
    print(f"[regression] json report: {REPORT_JSON_PATH}")

    for index, case in enumerate(remaining, start=1):
        print(
            f"[regression] ({index}/{len(remaining)}) "
            f"{case.title} -> {case.command_text()}"
        )
        result = run_case(case)
        completed[case.case_id] = serialize_result(result)
        flush_reports(cases, completed, run_started_at)
        print(
            f"[regression] completed {case.case_id} "
            f"status={result.status} returncode={result.returncode} "
            f"duration={result.duration_seconds:.3f}s"
        )

    summary = build_json_payload(cases, completed, run_started_at)["summary"]
    print(
        f"[regression] summary completed={summary['completed_cases']}/"
        f"{summary['total_cases']} pass={summary['strict_pass']} "
        f"degraded={summary['degraded']} fail={summary['fail']} "
        f"timeout={summary['timeout']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
