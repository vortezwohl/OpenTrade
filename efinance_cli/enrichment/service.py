"""技术指标增强服务。

该模块负责把原始结果或共享契约结果补齐为可供 observation 与渲染消费的增强数据。
当前阶段同时承担两类职责：

1. 兼容旧的函数驱动命令路径；
2. 为共享 capability 提供标准化的历史补充接口，逐步替换对 `efinance.*.get_quote_history`
   的直接依赖。
"""

from __future__ import annotations

from typing import Any

import pandas as pd

import efinance
from efinance_cli.enrichment.indicators import enrich_history_frame
from efinance_cli.enrichment.levels import LEVELS, normalize_indicator_level
from efinance_cli.models import InvocationRequest
from efinance_cli.retry_utils import call_with_network_retry


HISTORY_COMMANDS: set[tuple[str, str]] = {
    ("stock", "get_quote_history"),
    ("bond", "get_quote_history"),
    ("futures", "get_quote_history"),
    ("common", "get_quote_history"),
    ("fund", "get_quote_history"),
}

SINGLE_ROW_COMMANDS: set[tuple[str, str]] = {
    ("stock", "get_quote_snapshot"),
    ("stock", "get_base_info"),
    ("bond", "get_base_info"),
    ("common", "get_base_info"),
}

LATEST_COMMANDS: set[tuple[str, str]] = {
    ("stock", "get_latest_quote"),
    ("common", "get_latest_quote"),
}

REALTIME_LIST_COMMANDS: set[tuple[str, str]] = {
    ("stock", "get_realtime_quotes"),
    ("bond", "get_realtime_quotes"),
    ("futures", "get_realtime_quotes"),
    ("common", "get_realtime_quotes_by_fs"),
    ("fund", "get_realtime_increase_rate"),
}

SHARED_HISTORY_COMMANDS: set[tuple[str, str]] = {
    ("shared", "equity.price.history"),
}


def enrich_market_data(request: InvocationRequest, value: Any) -> Any:
    """根据命令和结果类型附加技术指标。"""
    module_name = request.spec.module_name
    function_name = request.spec.function_name
    level = normalize_indicator_level(request.output.indicator_level)
    command_key = (module_name, function_name)

    if module_name == "utils":
        return value
    if command_key in HISTORY_COMMANDS or command_key in SHARED_HISTORY_COMMANDS:
        return enrich_history_result(value, level)
    if command_key in SINGLE_ROW_COMMANDS:
        return enrich_single_result(request, value, level)
    if command_key in LATEST_COMMANDS:
        return enrich_latest_result(request, value, level)
    if command_key in REALTIME_LIST_COMMANDS:
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
    """增强单标的静态或快照结果。"""
    if not isinstance(value, pd.Series):
        return value
    code = extract_code_from_series(value)
    if not code:
        return value
    history = fetch_history_for_code(request.spec.module_name, code, level)
    if history is None or history.empty:
        return value
    enriched = enrich_history_frame(history, level)
    latest = enriched.iloc[-1]
    result = value.copy()
    for key, indicator_value in latest.items():
        if key not in result.index:
            result[key] = indicator_value
    return result


def enrich_latest_result(request: InvocationRequest, value: Any, level: str) -> Any:
    """增强最新行情结果。"""
    if not isinstance(value, pd.DataFrame):
        return value
    enriched_rows: list[pd.Series] = []
    for _, row in value.iterrows():
        enriched_rows.append(enrich_row_with_history(request.spec.module_name, row, level))
    return pd.DataFrame(enriched_rows)


def enrich_realtime_list_result(request: InvocationRequest, value: Any, level: str) -> Any:
    """增强实时列表结果。"""
    if not isinstance(value, pd.DataFrame):
        return value
    config = LEVELS[level]
    max_rows = request.output.limit or config.realtime_limit
    rows = []
    for idx, (_, row) in enumerate(value.iterrows()):
        if idx < max_rows:
            rows.append(enrich_row_with_history(request.spec.module_name, row, level))
        else:
            rows.append(row)
    return pd.DataFrame(rows)


def enrich_row_with_history(module_name: str, row: pd.Series, level: str) -> pd.Series:
    """对单行实时结果做历史回补增强。"""
    code = extract_code_from_series(row)
    if not code:
        return row
    history = fetch_history_for_code(module_name, code, level)
    if history is None or history.empty:
        return row
    enriched = enrich_history_frame(history, level)
    latest = enriched.iloc[-1]
    result = row.copy()
    for key, indicator_value in latest.items():
        if key not in result.index:
            result[key] = indicator_value
    return result


def fetch_history_for_code(module_name: str, code: str, level: str) -> pd.DataFrame | None:
    """按模块回补历史 K 线。"""
    config = LEVELS[level]
    try:
        if module_name == "stock":
            return call_with_network_retry(
                efinance.stock.get_quote_history,
                code,
                beg="19000101",
                end="20500101",
            ).tail(config.history_window)
        if module_name == "bond":
            return call_with_network_retry(
                efinance.bond.get_quote_history,
                code,
                beg="19000101",
                end="20500101",
            ).tail(config.history_window)
        if module_name == "futures":
            if "." not in code:
                return None
            return call_with_network_retry(
                efinance.futures.get_quote_history,
                code,
                beg="19000101",
                end="20500101",
            ).tail(config.history_window)
        if module_name == "common":
            return call_with_network_retry(
                efinance.common.get_quote_history,
                code,
                beg="19000101",
                end="20500101",
            ).tail(config.history_window)
        if module_name == "fund":
            return call_with_network_retry(
                efinance.fund.get_quote_history,
                code,
            ).tail(config.history_window)
    except Exception:
        return None
    return None


def fetch_standard_history_for_request(
    request: InvocationRequest,
    code: str,
    level: str,
) -> pd.DataFrame | None:
    """通过标准补充接口回补共享 capability 的历史结果。

    设计约束：
    - 共享 capability 优先走 `CommandFacade`，而不是直接绑到某个 provider 函数；
    - 返回值统一为标准字段 DataFrame，供 enrichment / observation 继续消费；
    - 如果请求本身已经是共享历史命令，则优先复用该请求的后端与参数语义。
    """

    command_key = (
        request.command_definition.command_key
        if request.command_definition is not None
        else None
    )
    if command_key != "equity.price.history" or request.backend_selection is None:
        return fetch_history_for_code(request.spec.module_name, code, level)

    from efinance_cli.facade import CommandFacade

    config = LEVELS[level]
    facade = CommandFacade()
    request_data = {
        "symbol": code,
        "market": request.kwargs.get("market"),
        "start_date": request.kwargs.get("start_date", "19000101"),
        "end_date": request.kwargs.get("end_date", "20500101"),
        "period": request.kwargs.get("period", "daily"),
        "adjust": request.kwargs.get("adjust", "qfq"),
    }
    try:
        standard_result = facade.invoke(
            request.command_definition,
            request.backend_selection,
            request_data,
        )
    except Exception:
        return None

    data = getattr(standard_result, "data", None)
    if not isinstance(data, list):
        return None
    frame = pd.DataFrame(data)
    if frame.empty:
        return frame
    if "symbol" in frame.columns:
        frame = frame[frame["symbol"].astype(str) == str(code)]
    return frame.tail(config.history_window).reset_index(drop=True)


def extract_code_from_series(series: pd.Series) -> str | None:
    """从结果行或详情中提取证券代码。"""
    candidates = [
        "股票代码",
        "债券代码",
        "期货代码",
        "基金代码",
        "代码",
        "行情ID",
    ]
    for candidate in candidates:
        if candidate in series.index and pd.notna(series[candidate]):
            return str(series[candidate])
    return None
