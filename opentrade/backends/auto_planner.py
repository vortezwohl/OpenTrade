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


def plan_auto_backend_candidates(
    definition: CommandDefinition,
    request_data: Mapping[str, object],
) -> tuple[BackendName, ...]:
    """根据请求语义返回 auto backend 候选顺序。"""

    registry = list_backend_providers()
    supported = [
        backend_name
        for backend_name in DEFAULT_AUTO_CANDIDATE_ORDER
        if definition.supports_backend(backend_name) and backend_name in registry
    ]
    if len(supported) <= 1:
        return tuple(supported)

    market = _extract_market(request_data)
    target_text = _extract_target_text(definition.command_key, request_data)
    preferred = _preferred_backends(definition.command_key, market, target_text)
    ordered: list[BackendName] = []
    for backend_name in preferred:
        if backend_name in supported and backend_name not in ordered:
            ordered.append(backend_name)
    for backend_name in supported:
        if backend_name not in ordered:
            ordered.append(backend_name)
    return tuple(ordered)


def _extract_market(request_data: Mapping[str, object]) -> str | None:
    value = request_data.get("market")
    if value in (None, ""):
        return None
    return str(value)


def _extract_target_text(command_key: str, request_data: Mapping[str, object]) -> str:
    if command_key in {"stock.price.history", "stock.price.latest", "fund.profile"}:
        values = request_data.get("symbols") or []
        return str(values[0]) if values else ""
    if command_key == "stock.profile":
        return str(request_data.get("symbol") or "")
    if command_key in {"quote.price.history"}:
        values = request_data.get("symbols") or []
        return str(values[0]) if values else ""
    if command_key in {"quote.price.latest"}:
        values = request_data.get("quote_ids") or []
        return str(values[0]) if values else ""
    if command_key == "quote.profile":
        return str(request_data.get("quote_id") or "")
    if command_key == "fund.nav.history":
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
        return (BackendName.YFINANCE, BackendName.EFINANCE, BackendName.AKSHARE)
    if market == "A_stock" or _looks_like_a_share_symbol(target) or _looks_like_cn_quote_id(target):
        if command_key in {"stock.price.live"}:
            return (BackendName.EFINANCE, BackendName.AKSHARE)
        return (BackendName.EFINANCE, BackendName.AKSHARE, BackendName.YFINANCE)
    return (BackendName.EFINANCE, BackendName.YFINANCE, BackendName.AKSHARE)


def _looks_like_us_symbol(text: str) -> bool:
    if not text:
        return False
    if "." in text and text.split(".", 1)[0].isdigit():
        return False
    return text.isalpha() and len(text) <= 8


def _looks_like_a_share_symbol(text: str) -> bool:
    return len(text) == 6 and text.isdigit()


def _looks_like_cn_quote_id(text: str) -> bool:
    return "." in text and text.split(".", 1)[0].isdigit()
