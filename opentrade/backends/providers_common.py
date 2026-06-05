"""多 backend provider 的共享辅助工具。

该模块只保留跨 backend 共享的请求读取、契约标准化、payload materialize 与 通用结果整理逻辑，不承载任何单一
provider 的专属适配语义。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd

from opentrade.contracts import (
    FUND_NAV_HISTORY_CONTRACT,
    HISTORY_BARS_CONTRACT,
    PROFILE_INFO_CONTRACT,
    PROVIDER_RECORDS_CONTRACT,
    REALTIME_QUOTES_CONTRACT,
    SEARCH_RESULTS_CONTRACT,
    StandardizationError,
    ensure_mapping_has_required_fields,
    normalize_contract_mapping,
)
from opentrade.models import BackendName, EXECUTION_LIMIT_REQUEST_KEY

PRICE_HISTORY_COMMAND_KEYS = {
    "stock.price.history",
    "bond.price.history",
    "futures.price.history",
    "quote.price.history",
}

PROFILE_COMMAND_KEYS = {
    "stock.profile",
    "fund.profile",
    "bond.profile",
    "quote.profile",
}

REALTIME_COMMAND_KEYS = {
    "stock.price.live",
    "stock.price.latest",
    "stock.price.snapshot",
    "bond.price.live",
    "futures.price.live",
    "quote.price.latest",
    "market.price.live",
}

SIDE_EFFECT_COMMAND_KEYS = {
    "fund.reports.download",
    "market.add",
}

SCALAR_LIST_COMMAND_KEYS = {
    "fund.disclosure.dates",
}


def _extract_execution_limit(request_data: Mapping[str, object]) -> int | None:
    """从 provider 请求中提取执行层 limit。"""
    value = request_data.get(EXECUTION_LIMIT_REQUEST_KEY)
    if value in (None, ""):
        return None
    limit = int(value)
    if limit <= 0:
        return None
    return limit


def _sanitize_provider_request(
    request_data: Mapping[str, object]
) -> dict[str, object]:
    """移除执行层内部控制字段，避免泄漏到第三方 callback kwargs。"""
    return {
        key: value
        for key, value in dict(request_data).items()
        if key != EXECUTION_LIMIT_REQUEST_KEY
    }


def _extract_market_value(value: object) -> object | None:
    if value in (None, "", (), []):
        return None
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _coerce_request_sequence(
    request_data: Mapping[str, object],
    *keys: str,
) -> list[str]:
    return _coerce_symbol_list(
        _get_request_value(request_data, *keys, default=[])
    )


def _single_or_multi(values: list[str]) -> str | list[str]:
    if len(values) == 1:
        return values[0]
    return values


def _get_single_request_value(
    request_data: Mapping[str, object],
    command_key: str,
    *keys: str,
) -> str:
    values = _coerce_request_sequence(request_data, *keys)
    if len(values) != 1:
        raise ValueError(f"{command_key} 只支持单个标的")
    return values[0]


def _standardize_profile_payload(
    result: object,
    request_data: dict[str, object],
    *,
    code_key: str | None = None,
) -> object:
    key_candidates: list[str] = []
    if code_key:
        key_candidates.append(code_key)
    key_candidates.extend(
        [
            "symbol",
            "symbols",
            "stock_codes",
            "fund_codes",
            "bond_codes",
            "quote_id",
            "quote_ids",
            "quote_id_list",
        ]
    )

    ordered_keys: list[str] = []
    for key in key_candidates:
        if key not in ordered_keys:
            ordered_keys.append(key)
    codes = _coerce_symbol_list(
        _get_request_value(request_data, *ordered_keys, default=[])
    )

    if isinstance(result, pd.Series):
        normalized = _normalize_profile_mapping(
            result.to_dict(), codes[0] if codes else None
        )
        return normalized

    if isinstance(result, pd.DataFrame) and {"item", "value"}.issubset(
            result.columns):
        row = {
            str(item): _normalize_scalar(value)
            for item, value in
            zip(result["item"], result["value"], strict=False)
        }
        return _normalize_profile_mapping(row, codes[0] if codes else None)

    if isinstance(result, pd.DataFrame):
        rows: list[dict[str, object]] = []
        for index, (_, row) in enumerate(result.iterrows()):
            fallback_code = codes[index] if index < len(codes) else None
            rows.append(
                _normalize_profile_mapping(row.to_dict(), fallback_code)
            )
        return rows

    if isinstance(result, dict):
        return _normalize_profile_mapping(result, codes[0] if codes else None)

    raise StandardizationError(
        f"Unsupported profile payload type: {type(result).__name__}"
    )


def _normalize_profile_mapping(
    row: dict[str, object], fallback_code: str | None
) -> dict[str, object]:
    normalized = normalize_contract_mapping(row, PROFILE_INFO_CONTRACT)
    if "code" not in normalized and fallback_code:
        normalized["code"] = fallback_code
    if "quote_id" not in normalized and "code" in normalized:
        normalized["quote_id"] = normalized["code"]
    if "name" not in normalized and fallback_code:
        normalized["name"] = fallback_code
    ensure_mapping_has_required_fields(normalized, PROFILE_INFO_CONTRACT)
    return normalized


def _get_request_value(
    request_data: Mapping[str, object],
    *keys: str,
    default: object = None
) -> object:
    for key in keys:
        if key in request_data and request_data[key] not in (None, "", (), []):
            return request_data[key]
    return default


def _coerce_symbol_list(value: object) -> list[str]:
    if value in (None, "", (), []):
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


def _coerce_frame_mapping(
    result: object
) -> pd.DataFrame | dict[str, pd.DataFrame]:
    if isinstance(result, pd.DataFrame):
        return result
    if isinstance(result, dict):
        mapping: dict[str, pd.DataFrame] = {}
        for key, value in result.items():
            if isinstance(value, pd.DataFrame):
                mapping[str(key)] = value
            else:
                raise StandardizationError(
                    "History payload mapping values must be DataFrame"
                )
        return mapping
    raise StandardizationError(
        f"Unsupported history payload type: {type(result).__name__}"
    )


def _materialize_provider_payload(value: object) -> object:
    if isinstance(value, pd.DataFrame):
        return _standardize_generic_payload(value)
    if isinstance(value, pd.Series):
        return _standardize_generic_payload(value)
    if isinstance(value, Mapping):
        return _standardize_generic_payload(dict(value))
    if isinstance(value, Sequence) and not isinstance(value,
                                                      (str, bytes, bytearray)):
        return _standardize_generic_payload(list(value))
    return _normalize_scalar(value)


def _coerce_history_frame(result: object) -> pd.DataFrame:
    if isinstance(result, pd.DataFrame):
        return result
    if isinstance(result, dict):
        if len(result) != 1:
            raise StandardizationError("History capability 仅支持单标的结果")
        only_value = next(iter(result.values()))
        if isinstance(only_value, pd.DataFrame):
            return only_value
    raise StandardizationError(
        f"Unsupported history payload type: {type(result).__name__}"
    )


def _standardize_history_frame(
    frame: pd.DataFrame,
    *,
    symbol: str,
    provider_name: str,
) -> list[dict[str, object]]:
    if frame is None or frame.empty:
        return []

    rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        item = {
            "date":
            _pick_first_present_value(row, ("date", "日期", "时间")),
            "symbol":
            _pick_first_present_value(
                row, ("symbol", "股票代码", "债券代码", "期货代码", "代码")
            ) or symbol,
            "open":
            _pick_first_present_value(row, ("开盘", "open")),
            "close":
            _pick_first_present_value(row, ("收盘", "最新价", "close")),
            "high":
            _pick_first_present_value(row, ("最高", "high")),
            "low":
            _pick_first_present_value(row, ("最低", "low")),
            "volume":
            _pick_first_present_value(row, ("成交量", "volume")),
            "turnover":
            _pick_first_present_value(row, ("成交额", "turnover")),
            "amplitude":
            _pick_first_present_value(row, ("振幅", "amplitude")),
            "change_pct":
            _pick_first_present_value(row, ("涨跌幅", "change_pct")),
            "change_amount":
            _pick_first_present_value(row, ("涨跌额", "change_amount")),
            "turnover_rate":
            _pick_first_present_value(row, ("换手率", "turnover_rate")),
        }
        item = {
            key: _normalize_scalar(value)
            for key, value in item.items() if value is not None
        }
        normalized = normalize_contract_mapping(item, HISTORY_BARS_CONTRACT)
        if "symbol" not in normalized:
            normalized["symbol"] = symbol
        ensure_mapping_has_required_fields(normalized, HISTORY_BARS_CONTRACT)
        normalized["provider_name"] = provider_name
        rows.append(normalized)
    return rows


def _standardize_fund_nav_history_frame(
    frame: pd.DataFrame,
    *,
    symbol: str,
) -> list[dict[str, object]]:
    if frame is None or frame.empty:
        return []

    rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        item = {
            "date":
            _pick_first_present_value(row, ("date", "日期", "净值日期", "时间")),
            "symbol":
            _pick_first_present_value(row, ("symbol", "基金代码", "代码")) or symbol,
            "unit_nav":
            _pick_first_present_value(row, ("unit_nav", "单位净值")),
            "accumulated_nav":
            _pick_first_present_value(row, ("accumulated_nav", "累计净值")),
            "change_pct":
            _pick_first_present_value(row, ("change_pct", "涨跌幅", "日增长率")),
        }
        item = {
            key: _normalize_scalar(value)
            for key, value in item.items() if value is not None
        }
        normalized = normalize_contract_mapping(
            item, FUND_NAV_HISTORY_CONTRACT
        )
        if "symbol" not in normalized:
            normalized["symbol"] = symbol
        ensure_mapping_has_required_fields(
            normalized, FUND_NAV_HISTORY_CONTRACT
        )
        rows.append(normalized)
    return rows


def _standardize_realtime_quotes_frame(
    frame: pd.DataFrame,
    *,
    market_name: str,
    provider_name: str,
) -> list[dict[str, object]]:
    if frame is None or frame.empty:
        return []

    rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        item = {
            "symbol":
            _pick_first_present_value(
                row,
                ("symbol", "代码", "股票代码", "债券代码", "期货代码", "证券代码"),
            ),
            "name":
            _pick_first_present_value(
                row,
                ("name", "名称", "股票名称", "债券名称", "期货名称", "证券简称"),
            ),
            "close":
            _pick_first_present_value(row, ("close", "最新价", "收盘")),
            "quote_id":
            _pick_first_present_value(
                row,
                (
                    "quote_id", "行情ID", "symbol", "代码", "股票代码", "债券代码", "期货代码",
                    "证券代码"
                ),
            ),
            "market":
            _pick_first_present_value(row, ("market", "市场", "市场类型"))
            or market_name,
            "open":
            _pick_first_present_value(row, ("open", "今开", "开盘")),
            "high":
            _pick_first_present_value(row, ("high", "最高")),
            "low":
            _pick_first_present_value(row, ("low", "最低")),
            "volume":
            _pick_first_present_value(row, ("volume", "成交量")),
            "turnover":
            _pick_first_present_value(row, ("turnover", "成交额")),
            "change_pct":
            _pick_first_present_value(row, ("change_pct", "涨跌幅")),
            "change_amount":
            _pick_first_present_value(row, ("change_amount", "涨跌额")),
            "turnover_rate":
            _pick_first_present_value(row, ("turnover_rate", "换手率")),
            "amplitude":
            _pick_first_present_value(row, ("amplitude", "振幅")),
            "date":
            _pick_first_present_value(row, ("date", "日期", "时间")),
        }
        item = {
            key: _normalize_scalar(value)
            for key, value in item.items() if value is not None
        }
        normalized = normalize_contract_mapping(item, REALTIME_QUOTES_CONTRACT)
        if "market" not in normalized:
            normalized["market"] = market_name
        if "quote_id" not in normalized and "symbol" in normalized:
            normalized["quote_id"] = normalized["symbol"]
        ensure_mapping_has_required_fields(
            normalized, REALTIME_QUOTES_CONTRACT
        )
        normalized["provider_name"] = provider_name
        rows.append(normalized)
    return rows


def _standardize_provider_records_frame(
    frame: pd.DataFrame,
    *,
    provider_name: str,
) -> list[dict[str, object]]:
    if frame is None or frame.empty:
        return []

    rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        item = {
            "name": _pick_first_present_value(row, ("name", "板块名称", "名称")),
            "code": _pick_first_present_value(row, ("code", "代码")),
            "latest": _pick_first_present_value(row, ("latest", "最新价")),
            "change_pct":
            _pick_first_present_value(row, ("change_pct", "涨跌幅")),
            "provider_name": provider_name,
        }
        item = {
            key: _normalize_scalar(value)
            for key, value in item.items() if value is not None
        }
        normalized = normalize_contract_mapping(
            item, PROVIDER_RECORDS_CONTRACT
        )
        ensure_mapping_has_required_fields(
            normalized, PROVIDER_RECORDS_CONTRACT
        )
        rows.append(normalized)
    return rows


def _standardize_generic_payload(result: object) -> object:
    if isinstance(result, pd.DataFrame):
        return [
            {
                str(key): _normalize_scalar(value)
                for key, value in row.items()
            } for row in result.to_dict(orient="records")
        ]
    if isinstance(result, pd.Series):
        return {
            str(key): _normalize_scalar(value)
            for key, value in result.to_dict().items()
        }
    if isinstance(result, Mapping):
        return {
            str(key): _standardize_generic_payload(value)
            for key, value in result.items()
        }
    if isinstance(result,
                  Sequence) and not isinstance(result,
                                               (str, bytes, bytearray)):
        payload: list[object] = []
        for item in result:
            if isinstance(item, (Mapping, pd.DataFrame, pd.Series)):
                payload.append(_standardize_generic_payload(item))
            elif hasattr(item, "_asdict"):
                payload.append(_standardize_generic_payload(item._asdict()))
            else:
                payload.append(_normalize_scalar(item))
        return payload
    return _normalize_scalar(result)


def _pick_first_present_value(
    row: pd.Series, candidates: tuple[str, ...]
) -> object | None:
    for candidate in candidates:
        if candidate in row.index and pd.notna(row[candidate]):
            return row[candidate]
    return None


def _normalize_scalar(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "isoformat") and not isinstance(value, str):
        try:
            return value.isoformat()
        except Exception:  # noqa: BLE001
            pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:  # noqa: BLE001
            return str(value)
    return value


def _filter_search_rows(
    rows: list[dict[str, object]],
    query: str,
) -> list[dict[str, object]]:
    lowered = query.strip().lower()
    if not lowered:
        return rows

    filtered: list[dict[str, object]] = []
    for row in rows:
        candidates = [
            str(row.get("code", "")),
            str(row.get("name", "")),
            str(row.get("pinyin", "")),
            str(row.get("quote_id", "")),
        ]
        if any(lowered in candidate.lower() for candidate in candidates
               if candidate and candidate != "None"):
            filtered.append(row)
    return filtered


def _deduplicate_search_rows(
    rows: list[dict[str, object]]
) -> list[dict[str, object]]:
    deduplicated: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row.get("code", "")), str(row.get("classify", "")))
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(row)
    return deduplicated


__all__ = [
    "PRICE_HISTORY_COMMAND_KEYS",
    "PROFILE_COMMAND_KEYS",
    "REALTIME_COMMAND_KEYS",
    "SIDE_EFFECT_COMMAND_KEYS",
    "SCALAR_LIST_COMMAND_KEYS",
    "_extract_execution_limit",
    "_sanitize_provider_request",
    "_extract_market_value",
    "_coerce_request_sequence",
    "_single_or_multi",
    "_get_single_request_value",
    "_standardize_profile_payload",
    "_normalize_profile_mapping",
    "_get_request_value",
    "_coerce_symbol_list",
    "_coerce_frame_mapping",
    "_materialize_provider_payload",
    "_coerce_history_frame",
    "_standardize_history_frame",
    "_standardize_fund_nav_history_frame",
    "_standardize_realtime_quotes_frame",
    "_standardize_provider_records_frame",
    "_standardize_generic_payload",
    "_pick_first_present_value",
    "_normalize_scalar",
    "_filter_search_rows",
    "_deduplicate_search_rows",
    "FUND_NAV_HISTORY_CONTRACT",
    "HISTORY_BARS_CONTRACT",
    "PROFILE_INFO_CONTRACT",
    "PROVIDER_RECORDS_CONTRACT",
    "REALTIME_QUOTES_CONTRACT",
    "SEARCH_RESULTS_CONTRACT",
    "StandardizationError",
    "ensure_mapping_has_required_fields",
    "normalize_contract_mapping",
    "BackendName",
    "EXECUTION_LIMIT_REQUEST_KEY",
]
