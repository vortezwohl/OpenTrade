"""
真实回归报告的共享辅助能力。

该模块为多个真实回归脚本提供统一的失败分层、路由证据归一化与
auto fallback 判定逻辑，避免不同脚本继续各自维护一套互相漂移的
报告口径。
"""

from __future__ import annotations

import json
import re
from typing import Any

UPSTREAM_PATTERNS = (
    "timeout after",
    "connecttimeout",
    "readtimeout",
    "connectionerror",
    "sslerror",
    "maxretryerror",
    "bad gateway",
    "gateway timeout",
    "remote end closed connection",
    "connection reset",
    "name resolution",
    "temporary failure in name resolution",
    "proxyerror",
    "rate limit",
    "too many requests",
    "yfratelimiterror",
)
SAMPLE_PATTERNS = (
    "missing option",
    "missing required option",
    "no such option",
    "invalid value for",
    "got unexpected extra argument",
    "invalid choice",
    "invalid date",
    "date format",
    "should be in yyyymmdd",
    "must be in yyyymmdd",
    "not a valid integer",
)
ADAPTER_HINT_PATTERNS = (
    "adapter",
    "adaptation",
    "provider-specific",
    "provider specific",
    "shared contract",
    "shared schema",
    "shared request",
    "normalized request",
    "cannot map",
    "failed to map",
    "mapping failed",
    "provider does not support",
    "not supported by provider",
    "unsupported market",
    "market semantics",
    "quote-id semantics",
    "quote id semantics",
    "provider adaptation",
    "shared market",
    "shared quote-id",
    "shared quote id",
)
ADAPTER_FIELD_HINTS = ("market", "quote-id", "quote id", "quote_ids", "fs", "symbol", "symbols")
ERROR_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))")


def _to_text(value: Any) -> str | None:
    """把证据字段转成可序列化字符串。"""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_text_list(value: Any) -> list[str]:
    """把候选链等字段归一化为字符串列表。"""

    if not isinstance(value, (list, tuple)):
        return []
    items: list[str] = []
    for item in value:
        text = _to_text(item)
        if text is not None:
            items.append(text)
    return items


def normalize_backend_meta(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """把 raw/observation 中的 backend 元数据收敛为统一结构。"""

    raw = metadata if isinstance(metadata, dict) else {}
    planned_candidates = _to_text_list(raw.get("planned_candidates") or raw.get("candidate_chain"))
    attempted_candidates = _to_text_list(raw.get("attempted_candidates"))
    final_backend = _to_text(raw.get("final_backend"))
    fallback_used = bool(raw.get("fallback_used", False))
    if not fallback_used and len(planned_candidates) > 1 and final_backend is not None:
        fallback_used = final_backend != planned_candidates[0]
    return {
        "requested_backend": _to_text(raw.get("requested_backend")),
        "resolved_backend": _to_text(raw.get("resolved_backend")),
        "planned_candidates": planned_candidates,
        "attempted_candidates": attempted_candidates,
        "candidate_chain": planned_candidates,
        "final_backend": final_backend,
        "fallback_used": fallback_used,
        "limit_strategy": _to_text(raw.get("limit_strategy")),
        "limit_value": raw.get("limit_value"),
        "limit_effect": _to_text(raw.get("limit_effect")),
        "display_limit_applied": bool(raw.get("display_limit_applied", False)),
        "execution_limit_applied": bool(raw.get("execution_limit_applied", False)),
    }


def extract_backend_meta_from_payload(payload: Any) -> dict[str, Any]:
    """从 raw/json 载荷中提取并归一化 backend 元数据。"""

    if not isinstance(payload, dict):
        return normalize_backend_meta({})
    for key in ("metadata", "meta"):
        value = payload.get(key)
        if isinstance(value, dict):
            return normalize_backend_meta(value)
    return normalize_backend_meta({})


def extract_backend_meta_from_stdout(stdout: str) -> dict[str, Any]:
    """从 stdout 的 JSON 文本中提取 backend 元数据。"""

    text = stdout.strip()
    if not text:
        return normalize_backend_meta({})
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return normalize_backend_meta({})
    return extract_backend_meta_from_payload(payload)


def detect_auto_fallback(requested_backend: str | None, backend_meta: dict[str, Any] | None) -> bool:
    """判断 auto 请求是否真实落到了首候选之外的 backend。"""

    if requested_backend != "auto":
        return False
    meta = normalize_backend_meta(backend_meta)
    if meta["fallback_used"]:
        return True
    planned_candidates = meta["planned_candidates"]
    final_backend = meta["final_backend"]
    return bool(planned_candidates) and len(planned_candidates) > 1 and final_backend is not None and final_backend != planned_candidates[0]


def summarize_failure_reason(stdout: str, stderr: str) -> str | None:
    """抽取最可读的失败原因摘要。"""

    text = "\n".join(part for part in [stderr.strip(), stdout.strip()] if part)
    if not text:
        return None
    found = ERROR_RE.findall(text)
    if found:
        return found[-1]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1][:200] if lines else None


def classify_regression_failure(
    *,
    command_path: str,
    requested_backend: str | None,
    stdout: str,
    stderr: str,
    returncode: int | None,
    status: str,
    backend_meta: dict[str, Any] | None,
    artifact_reports: list[dict[str, Any]] | None = None,
) -> tuple[str | None, str | None]:
    """按分层规则给真实回归结果归因。

    Args:
        command_path: 当前回归命令路径。
        requested_backend: 用例声明的 backend。
        stdout: 原始标准输出。
        stderr: 原始错误输出。
        returncode: 进程退出码。
        status: 当前脚本内部状态，例如 PASS/FAIL/TIMEOUT 或 pass/fail/degraded。
        backend_meta: 已归一化的 backend 元数据。
        artifact_reports: 副作用产物信息，用于识别成功退出但结果缺失的产品缺陷。

    Returns:
        二元组，分别为失败分类与原因摘要。
    """

    lowered_status = status.lower()
    if lowered_status == "pass":
        return None, None

    reason = summarize_failure_reason(stdout, stderr)
    combined = "\n".join(part for part in [stderr.strip(), stdout.strip()] if part)
    lowered = combined.lower()

    if lowered_status == "timeout" or any(pattern in lowered for pattern in UPSTREAM_PATTERNS):
        return "upstream_instability", reason

    if returncode == 2 or any(pattern in lowered for pattern in SAMPLE_PATTERNS):
        return "sample_mismatch", reason

    adapter_hint = any(pattern in lowered for pattern in ADAPTER_HINT_PATTERNS)
    adapter_field_conflict = any(field in lowered for field in ADAPTER_FIELD_HINTS) and any(
        token in lowered for token in ("unsupported", "not support", "cannot map", "failed to map", "provider")
    )
    if adapter_hint or adapter_field_conflict:
        return "adapter_gap", reason

    missing_artifact = any(not item.get("exists", False) for item in (artifact_reports or []))
    meta = normalize_backend_meta(backend_meta)
    unresolved_auto = requested_backend == "auto" and meta["final_backend"] is None and lowered_status != "pass"
    if missing_artifact or unresolved_auto or lowered_status in {"fail", "degraded", "timeout"}:
        return "product_defect", reason

    return "product_defect", reason
