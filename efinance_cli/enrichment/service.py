"""技术指标增强服务。

该模块只服务于当前 shared / provider-extension 多后端执行链，职责收敛为：
1. 为共享历史结果补充技术指标；
2. 为共享单标的资料与实时列表通过标准补充接口回补历史；
3. 不再承载旧函数驱动命令模型的分类常量与直连 provider 回补路径。
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from efinance_cli.enrichment.indicators import enrich_history_frame
from efinance_cli.enrichment.levels import LEVELS, normalize_indicator_level
from efinance_cli.models import InvocationRequest


SHARED_HISTORY_COMMAND_KEYS: set[str] = {
    "stock.price.history",
    "bond.price.history",
    "futures.price.history",
    "quote.price.history",
    "fund.nav.history",
    "fund.nav.history-batch",
}

SHARED_SINGLE_ROW_COMMAND_KEYS: set[str] = {
    "stock.profile",
    "fund.profile",
    "bond.profile",
    "quote.profile",
}

SHARED_REALTIME_LIST_COMMAND_KEYS: set[str] = {
    "stock.price.live",
    "stock.price.latest",
    "stock.price.snapshot",
    "bond.price.live",
    "futures.price.live",
    "quote.price.latest",
    "market.price.live",
}

PROFILE_HISTORY_COMMAND_MAP: dict[str, str] = {
    "stock.profile": "stock.price.history",
    "fund.profile": "fund.nav.history",
    "bond.profile": "bond.price.history",
    "quote.profile": "quote.price.history",
}

REALTIME_HISTORY_COMMAND_MAP: dict[str, str] = {
    "stock.price.live": "stock.price.history",
    "stock.price.latest": "stock.price.history",
    "stock.price.snapshot": "stock.price.history",
    "bond.price.live": "bond.price.history",
    "futures.price.live": "futures.price.history",
    "quote.price.latest": "quote.price.history",
}


def enrich_market_data(request: InvocationRequest, value: Any) -> Any:
    """根据稳定命令键和结果类型附加技术指标。"""

    command_key = resolve_runtime_command_key(request)
    level = normalize_indicator_level(request.output.indicator_level)

    if command_key in SHARED_HISTORY_COMMAND_KEYS:
        return enrich_history_result(value, level)
    if command_key in SHARED_SINGLE_ROW_COMMAND_KEYS:
        return enrich_single_result(request, value, level)
    if command_key in SHARED_REALTIME_LIST_COMMAND_KEYS:
        return enrich_realtime_list_result(request, value, level)
    return value


def enrich_history_result(value: Any, level: str) -> Any:
    """增强历史 K 线结果。"""

    if isinstance(value, pd.DataFrame):
        return enrich_history_frame(value, level)
    if isinstance(value, dict):
        return {key: enrich_history_frame(frame, level) for key, frame in value.items()}
    return value


def enrich_single_result(request: InvocationRequest, value: Any, level: str) -> Any:
    """增强单标的静态资料结果。"""

    if not isinstance(value, pd.Series):
        return value
    code = extract_code_from_series(value)
    if not code:
        return value
    history = fetch_standard_history_for_request(request, code, level)
    if history is None or history.empty:
        return value
    enriched = enrich_history_frame(history, level)
    latest = enriched.iloc[-1]
    result = value.copy()
    for key, indicator_value in latest.items():
        if key not in result.index:
            result[key] = indicator_value
    return result


def enrich_realtime_list_result(request: InvocationRequest, value: Any, level: str) -> Any:
    """增强实时列表结果。"""

    if not isinstance(value, pd.DataFrame):
        return value
    config = LEVELS[level]
    max_rows = request.output.limit or config.realtime_limit
    rows = []
    for idx, (_, row) in enumerate(value.iterrows()):
        if idx < max_rows:
            rows.append(enrich_row_with_history(request, row, level))
        else:
            rows.append(row)
    return pd.DataFrame(rows)


def enrich_row_with_history(
    request: InvocationRequest,
    row: pd.Series,
    level: str,
) -> pd.Series:
    """对单行结果通过标准补充接口做历史回补增强。"""

    code = extract_code_from_series(row)
    if not code:
        return row
    history = fetch_standard_history_for_request(request, code, level)
    if history is None or history.empty:
        return row
    enriched = enrich_history_frame(history, level)
    latest = enriched.iloc[-1]
    result = row.copy()
    for key, indicator_value in latest.items():
        if key not in result.index:
            result[key] = indicator_value
    return result


def fetch_standard_history_for_request(
    request: InvocationRequest,
    code: str,
    level: str,
) -> pd.DataFrame | None:
    """通过标准补充接口回补共享 capability 的历史结果。"""

    command_key = resolve_runtime_command_key(request)
    history_command_key = resolve_history_lookup_command_key(command_key)
    if history_command_key is None:
        return None
    if request.backend_selection is None:
        return None

    from efinance_cli.command_catalog import get_shared_command_definition
    from efinance_cli.facade import CommandFacade

    config = LEVELS[level]
    facade = CommandFacade()
    history_definition = (
        request.command_definition
        if command_key == history_command_key and request.command_definition is not None
        else get_shared_command_definition(history_command_key)
    )
    request_data = build_history_lookup_request_data(request, history_command_key, code)
    backend_selection = request.backend_selection
    if getattr(backend_selection, "final_backend", None) is not None:
        backend_selection = type(backend_selection)(
            requested=backend_selection.requested,
            resolved=backend_selection.final_backend,
            source=backend_selection.source,
            candidate_chain=backend_selection.candidate_chain,
            final_backend=backend_selection.final_backend,
        )
    try:
        standard_result = facade.invoke(
            history_definition,
            backend_selection,
            request_data,
        )
    except Exception:
        return None

    data = getattr(standard_result, "data", None)
    frame = materialize_history_lookup_frame(data, code)
    if frame is None:
        return None
    if frame.empty:
        return frame
    if "symbol" in frame.columns:
        frame = frame[frame["symbol"].astype(str) == str(code)]
    return frame.tail(config.history_window).reset_index(drop=True)


def resolve_history_lookup_command_key(command_key: str | None) -> str | None:
    """把当前命令归并到对应的历史回补主链。"""

    if command_key in SHARED_HISTORY_COMMAND_KEYS:
        return command_key
    if command_key in PROFILE_HISTORY_COMMAND_MAP:
        return PROFILE_HISTORY_COMMAND_MAP[command_key]
    if command_key in REALTIME_HISTORY_COMMAND_MAP:
        return REALTIME_HISTORY_COMMAND_MAP[command_key]
    return None


def build_history_lookup_request_data(
    request: InvocationRequest,
    history_command_key: str,
    code: str,
) -> dict[str, object]:
    """为不同资产历史主链构造最小回补请求。"""

    common_history_fields = {
        "beg": request.kwargs.get("beg", "19000101"),
        "end": request.kwargs.get("end", "20500101"),
        "klt": request.kwargs.get("klt", 101),
        "fqt": request.kwargs.get("fqt", 1),
        "suppress_error": request.kwargs.get("suppress_error", False),
        "use_id_cache": request.kwargs.get("use_id_cache", True),
    }
    if history_command_key == "stock.price.history":
        return {
            "stock_codes": [code],
            "market_type": request.kwargs.get("market_type"),
            **common_history_fields,
        }
    if history_command_key == "bond.price.history":
        return {
            "bond_codes": [code],
            **common_history_fields,
        }
    if history_command_key == "futures.price.history":
        return {
            "quote_ids": [code],
            **common_history_fields,
        }
    if history_command_key == "quote.price.history":
        return {
            "codes": [code],
            **common_history_fields,
        }
    if history_command_key == "fund.nav.history":
        return {
            "fund_code": code,
            "pz": request.kwargs.get("pz", 40000),
        }
    raise KeyError(f"Unsupported history lookup command: {history_command_key}")


def materialize_history_lookup_frame(
    data: object,
    code: str,
) -> pd.DataFrame | None:
    """把标准历史结果恢复成用于指标补充的 DataFrame。"""

    if isinstance(data, list):
        return pd.DataFrame(data)
    if isinstance(data, dict):
        if code in data and isinstance(data[code], list):
            return pd.DataFrame(data[code])
        if len(data) == 1:
            only_value = next(iter(data.values()))
            if isinstance(only_value, list):
                return pd.DataFrame(only_value)
    return None


def resolve_runtime_command_key(request: InvocationRequest) -> str | None:
    """解析当前请求在新架构下的稳定命令键。"""

    if request.command_definition is not None:
        return request.command_definition.command_key
    if request.spec.module_name == "shared":
        return request.spec.function_name
    return None


def extract_code_from_series(series: pd.Series) -> str | None:
    """从结果行或详情中提取证券代码。"""

    candidates = [
        "股票代码",
        "债券代码",
        "期货代码",
        "基金代码",
        "代码",
        "行情ID",
        "symbol",
        "code",
        "quote_id",
    ]
    for candidate in candidates:
        if candidate in series.index and pd.notna(series[candidate]):
            return str(series[candidate])
    return None
