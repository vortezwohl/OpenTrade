"""基于 normalized shared request 规划 auto backend 候选链。"""

from __future__ import annotations

from collections.abc import Mapping

from opentrade.backends.factory import list_backend_providers
from opentrade.models import BackendName, CommandDefinition

DEFAULT_AUTO_CANDIDATE_ORDER: tuple[BackendName, ...] = (
    BackendName.EFINANCE,
    BackendName.YFINANCE,
    BackendName.AKSHARE,
)

TRUTHFUL_SINGLE_TARGET_COMMANDS = {
    "stock.price.history",
    "stock.price.latest",
    "stock.price.snapshot",
    "stock.profile",
    "fund.nav.history",
    "fund.profile",
    "quote.price.history",
    "quote.price.latest",
    "quote.profile",
}


def plan_auto_backend_candidates(
    definition: CommandDefinition,
    request_data: Mapping[str, object],
) -> tuple[BackendName, ...]:
    """按请求真实性和偏好顺序生成 auto backend 候选链。"""
    registry = list_backend_providers()
    supported = [
        backend_name
        for backend_name in DEFAULT_AUTO_CANDIDATE_ORDER
        if definition.supports_backend(backend_name)
        and backend_name in registry
    ]
    if len(supported) <= 1:
        return tuple(supported)

    truthful_supported = [
        backend_name
        for backend_name in supported
        if _supports_request_truthfully(
            definition.command_key,
            backend_name,
            request_data,
        )
    ]
    if len(truthful_supported) <= 1:
        return tuple(truthful_supported)

    market = _extract_market(request_data)
    target_text = _extract_target_text(definition.command_key, request_data)
    preferred = _preferred_backends(
        definition.command_key,
        market,
        target_text,
    )
    ordered: list[BackendName] = []
    for backend_name in preferred:
        if backend_name in truthful_supported and backend_name not in ordered:
            ordered.append(backend_name)
    for backend_name in truthful_supported:
        if backend_name not in ordered:
            ordered.append(backend_name)
    return tuple(ordered)


def _extract_market(request_data: Mapping[str, object]) -> str | None:
    value = request_data.get("market")
    if value in (None, ""):
        return None
    return str(value)


def _extract_target_text(
    command_key: str,
    request_data: Mapping[str, object],
) -> str:
    if command_key in {
        "stock.price.history",
        "stock.price.latest",
        "quote.price.history",
        "quote.price.latest",
    }:
        values = request_data.get("symbols") or []
        return str(values[0]) if values else ""
    if command_key in {
        "stock.price.snapshot",
        "stock.profile",
        "quote.profile",
        "fund.nav.history",
        "fund.profile",
    }:
        return str(request_data.get("symbol") or "")
    if command_key == "instrument.search":
        return str(request_data.get("keyword") or "")
    return ""


def _preferred_backends(
    command_key: str,
    market: str | None,
    target_text: str,
) -> tuple[BackendName, ...]:
    target = target_text.strip().upper()
    if market == "US_stock" or _looks_like_us_symbol(target):
        return (
            BackendName.YFINANCE,
            BackendName.EFINANCE,
            BackendName.AKSHARE,
        )
    if (
        market == "A_stock"
        or _looks_like_a_share_symbol(target)
        or _looks_like_cn_quote_id(target)
    ):
        if command_key == "stock.price.live":
            return (BackendName.EFINANCE, BackendName.AKSHARE)
        return (
            BackendName.EFINANCE,
            BackendName.AKSHARE,
            BackendName.YFINANCE,
        )
    return (
        BackendName.EFINANCE,
        BackendName.YFINANCE,
        BackendName.AKSHARE,
    )


def _looks_like_us_symbol(text: str) -> bool:
    if not text:
        return False
    if text.endswith((".SS", ".SZ")):
        return False
    if "." in text and text.split(".", 1)[0].isdigit():
        return False
    return text.isalpha() and len(text) <= 8


def _looks_like_a_share_symbol(text: str) -> bool:
    return len(text) == 6 and text.isdigit()


def _looks_like_cn_quote_id(text: str) -> bool:
    if "." not in text:
        return False
    left, right = text.split(".", 1)
    return left.isdigit() and right.isdigit()


def _is_single_target_request(
    command_key: str,
    request_data: Mapping[str, object],
) -> bool:
    if command_key in {
        "stock.price.history",
        "stock.price.latest",
        "quote.price.history",
        "quote.price.latest",
    }:
        return len(request_data.get("symbols") or []) == 1
    if command_key in {
        "stock.price.snapshot",
        "stock.profile",
        "quote.profile",
        "fund.nav.history",
        "fund.profile",
    }:
        return bool(str(request_data.get("symbol") or "").strip())
    return True


def _supports_request_truthfully(
    command_key: str,
    backend_name: BackendName,
    request_data: Mapping[str, object],
) -> bool:
    """判断 backend 是否能真实消费当前 normalized request。"""
    market = _extract_market(request_data)
    target = _extract_target_text(command_key, request_data).strip().upper()

    if command_key == "stock.price.live":
        return backend_name != BackendName.YFINANCE

    if command_key == "fund.profile":
        return backend_name != BackendName.AKSHARE

    if command_key in TRUTHFUL_SINGLE_TARGET_COMMANDS:
        if not _is_single_target_request(command_key, request_data):
            if backend_name == BackendName.YFINANCE and command_key in {
                "stock.price.history",
                "stock.price.latest",
                "quote.price.history",
                "quote.price.latest",
            }:
                return False
            if backend_name == BackendName.AKSHARE:
                return False

    if command_key in {
        "quote.price.history",
        "quote.price.latest",
        "quote.profile",
    }:
        if _looks_like_cn_quote_id(target):
            return False
        if backend_name == BackendName.EFINANCE:
            return bool(target)
        if backend_name == BackendName.YFINANCE:
            if market not in (None, "", "A_stock", "US_stock"):
                return False
            return bool(target)

    if command_key in {
        "stock.price.history",
        "stock.price.latest",
        "stock.price.snapshot",
        "stock.profile",
    }:
        if backend_name == BackendName.AKSHARE:
            return market in (None, "A_stock") and _looks_like_a_share_symbol(
                target
            )
        if backend_name == BackendName.YFINANCE and market == "A_stock":
            return _looks_like_a_share_symbol(target)

    if (
        command_key == "fund.nav.history"
        and backend_name == BackendName.YFINANCE
    ):
        return _is_single_target_request(command_key, request_data)

    return True
