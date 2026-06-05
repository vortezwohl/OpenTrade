"""Efinance provider 实现。

该模块集中封装 efinance backend 的共享命令适配、动态 handler 与 provider 构建。 所有跨 backend
共享的契约标准化逻辑统一放在 `providers_common.py`，避免 provider 语义继续泄漏。
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from datetime import datetime
from math import ceil

import efinance
import pandas as pd

from opentrade.backends.base import (
    BackendProvider,
    CapabilityHandler,
    ProviderContractError,
    ProviderExecutionError,
    ProviderResponseError,
    ProviderRetryPolicy,
)
from opentrade.command_catalog import (
    SHARED_COMMANDS,
    get_command_binding,
    get_single_backend_command_definitions,
)
from opentrade.contracts import (
    SCALAR_LIST_CONTRACT,
    SCALAR_VALUE_CONTRACT,
    SIDE_EFFECT_STATUS_CONTRACT,
    build_standard_result,
)
from opentrade.retry_utils import NETWORK_RELATED_EXCEPTIONS
from opentrade.backends.providers_common import (
    BackendName,
    FUND_NAV_HISTORY_CONTRACT,
    HISTORY_BARS_CONTRACT,
    PRICE_HISTORY_COMMAND_KEYS,
    PROFILE_COMMAND_KEYS,
    PROFILE_INFO_CONTRACT,
    PROVIDER_RECORDS_CONTRACT,
    REALTIME_COMMAND_KEYS,
    REALTIME_QUOTES_CONTRACT,
    SCALAR_LIST_COMMAND_KEYS,
    SEARCH_RESULTS_CONTRACT,
    SIDE_EFFECT_COMMAND_KEYS,
    StandardizationError,
    _coerce_frame_mapping,
    _coerce_history_frame,
    _coerce_request_sequence,
    _coerce_symbol_list,
    _extract_execution_limit,
    _extract_market_value,
    _get_request_value,
    _get_single_request_value,
    _normalize_scalar,
    _sanitize_provider_request,
    _single_or_multi,
    _standardize_fund_nav_history_frame,
    _standardize_generic_payload,
    _standardize_history_frame,
    _standardize_profile_payload,
    _standardize_realtime_quotes_frame,
    ensure_mapping_has_required_fields,
    normalize_contract_mapping,
)


class EfinanceSearchHandler(CapabilityHandler):
    """`efinance` 的默认搜索能力实现。"""

    capability_name = "instrument.search"

    def execute(self, request_data: dict[str, object]):
        adapted_request = _adapt_efinance_search_request(request_data)
        result = efinance.utils.search_quote(**adapted_request)
        return _build_search_standard_result(result)


class EfinanceGenericHandler(CapabilityHandler):
    """按命令绑定动态调用 `efinance` 的通用 handler。"""

    def __init__(self, capability_name: str) -> None:
        self.capability_name = capability_name

    def execute(self, request_data: dict[str, object]):
        binding = get_command_binding(self.capability_name)
        module_name = binding["module"]
        function_name = binding["function"]
        if module_name is None or function_name is None:
            raise RuntimeError(f"命令 {self.capability_name} 缺少上游绑定")

        execution_limit = _extract_execution_limit(request_data)
        if (execution_limit is not None and self.capability_name in {
                "market.price.live", "bond.price.live", "futures.price.live"
        }):
            try:
                if self.capability_name == "market.price.live":
                    fs = _resolve_efinance_market_fs(
                        _get_request_value(request_data, "market", "fs"),
                    )
                elif self.capability_name == "bond.price.live":
                    fs = _resolve_efinance_market_fs("bond")
                else:
                    fs = _resolve_efinance_market_fs("futures")
            except Exception as exc:  # noqa: BLE001
                raise ProviderContractError(
                    BackendName.EFINANCE,
                    self.capability_name,
                    "adapt",
                    str(exc),
                ) from exc

            try:
                result = _build_limited_efinance_live_frame(
                    fs, execution_limit
                )
            except Exception as exc:  # noqa: BLE001
                raise ProviderExecutionError(
                    BackendName.EFINANCE,
                    self.capability_name,
                    "execute",
                    str(exc),
                ) from exc

            try:
                return _standardize_efinance_result(
                    self.capability_name,
                    request_data,
                    result,
                )
            except StandardizationError as exc:
                raise ProviderResponseError(
                    BackendName.EFINANCE,
                    self.capability_name,
                    "standardize",
                    str(exc),
                ) from exc

        callback = getattr(getattr(efinance, module_name), function_name)
        try:
            adapted_request = _adapt_efinance_request(
                self.capability_name, request_data
            )
        except Exception as exc:  # noqa: BLE001
            raise ProviderContractError(
                BackendName.EFINANCE,
                self.capability_name,
                "adapt",
                str(exc),
            ) from exc

        try:
            result = callback(**adapted_request)
        except Exception as exc:  # noqa: BLE001
            raise ProviderExecutionError(
                BackendName.EFINANCE,
                self.capability_name,
                "execute",
                str(exc),
            ) from exc

        try:
            return _standardize_efinance_result(
                self.capability_name, request_data, result
            )
        except StandardizationError as exc:
            raise ProviderResponseError(
                BackendName.EFINANCE,
                self.capability_name,
                "standardize",
                str(exc),
            ) from exc


def _adapt_efinance_search_request(
    request_data: Mapping[str, object]
) -> dict[str, object]:
    """把 shared 搜索请求翻译为 `efinance.utils.search_quote` 参数。"""
    market = _get_request_value(request_data, "market", "market_type")
    return {
        "keyword":
        str(_get_request_value(request_data, "keyword", "query")).strip(),
        "market_type":
        _resolve_efinance_market_type(market),
        "count":
        int(
            _get_request_value(
                request_data, "result_count", "count", default=5
            )
        ),
        "use_local":
        bool(
            _get_request_value(
                request_data, "use_local_cache", "use_local", default=True
            )
        ),
    }


def _adapt_efinance_request(
    command_key: str,
    request_data: Mapping[str, object],
) -> dict[str, object]:
    """把 efinance 的 shared 与 extension 请求统一适配为上游 kwargs。"""
    return _adapt_efinance_shared_request(command_key, request_data)


def _adapt_efinance_shared_request(
    command_key: str,
    request_data: Mapping[str, object],
) -> dict[str, object]:
    """把 shared normalized request 翻译为 efinance 上游 kwargs。"""
    execution_limit = _extract_execution_limit(request_data)

    if command_key == "stock.price.history":
        return _adapt_efinance_history_request(
            request_data, code_field_name="stock_codes"
        )
    if command_key == "stock.price.latest":
        return {
            "stock_codes":
            _single_or_multi(
                _coerce_request_sequence(
                    request_data, "symbols", "stock_codes", "symbol"
                ),
            ),
        }
    if command_key == "stock.price.live":
        return {
            "fs":
            _resolve_efinance_live_fs(
                _get_request_value(
                    request_data, "market", "market_type", "fs"
                ),
            ),
        }
    if command_key == "market.price.live":
        return {
            "fs":
            _resolve_efinance_market_fs(
                _get_request_value(request_data, "market", "fs"),
            ),
        }
    if command_key == "stock.price.snapshot":
        return {
            "stock_code":
            _get_single_request_value(
                request_data,
                command_key,
                "symbol",
                "stock_code",
                "stock_codes",
            ),
        }
    if command_key == "stock.profile":
        return {
            "stock_codes":
            _get_single_request_value(
                request_data,
                command_key,
                "symbol",
                "symbols",
                "stock_codes",
            ),
        }
    if command_key == "fund.nav.history":
        return {
            "fund_code":
            _get_single_request_value(
                request_data,
                command_key,
                "symbol",
                "fund_code",
            ),
            "pz":
            int(
                _get_request_value(
                    request_data, "max_pages", "pz", default=40000
                )
            ),
        }
    if command_key == "fund.profile":
        return {
            "fund_codes":
            _single_or_multi(
                _coerce_request_sequence(
                    request_data, "symbols", "fund_codes", "symbol"
                ),
            ),
        }
    if command_key == "quote.price.history":
        return _adapt_efinance_quote_history_request(request_data)
    if command_key == "quote.price.latest":
        quote_ids = _resolve_efinance_quote_ids(request_data, command_key)
        if execution_limit is not None:
            quote_ids = quote_ids[:execution_limit]
        return {
            "quote_id_list": _single_or_multi(quote_ids),
        }
    if command_key == "quote.profile":
        return {
            "quote_id": _resolve_efinance_quote_id(request_data, command_key),
        }
    if command_key == "stock.holders.latest-count":
        return {
            "date":
            _normalize_efinance_date(
                _get_request_value(request_data, "date"),
                field_name="date",
                command_key=command_key,
            ),
        }
    if command_key == "stock.leaderboard.daily":
        return {
            "start_date":
            _normalize_efinance_date(
                _get_request_value(request_data, "start_date"),
                field_name="start_date",
                command_key=command_key,
            ),
            "end_date":
            _normalize_efinance_date(
                _get_request_value(request_data, "end_date"),
                field_name="end_date",
                command_key=command_key,
            ),
        }
    if command_key == "stock.performance.quarterly":
        return {
            "date":
            _normalize_efinance_date(
                _get_request_value(request_data, "date"),
                field_name="date",
                command_key=command_key,
            ),
        }
    return _sanitize_provider_request(request_data)


def _resolve_efinance_quote_ids(
    request_data: Mapping[str, object],
    command_key: str,
) -> list[str]:
    """把共享行情标识解析为东财 quote_id 列表。"""
    symbols = _coerce_request_sequence(
        request_data,
        "symbols",
        "symbol",
    )
    return [efinance.utils.get_quote_id(symbol) for symbol in symbols]


def _resolve_efinance_quote_id(
    request_data: Mapping[str, object],
    command_key: str,
) -> str:
    """把单个共享行情标识解析为东财 quote_id。"""
    symbol = _get_single_request_value(
        request_data,
        command_key,
        "symbol",
        "symbols",
    )
    return efinance.utils.get_quote_id(symbol)


def _looks_like_efinance_quote_id(value: object) -> bool:
    """判断输入值是否已经是 efinance / 东方财富使用的 quote_id。

    Args:
        value: 待判断的原始请求值，通常来自 shared request 的 `codes` / `symbols`。

    Returns:
        当值形如 `105.AAPL`、前缀为数字市场编号且后续带代码段时返回 `True`；否则返回 `False`。
    """
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or "." not in text:
        return False
    market_prefix, code = text.split(".", 1)
    return market_prefix.isdigit() and bool(code)


def _normalize_efinance_date(
    value: object,
    *,
    field_name: str,
    command_key: str,
) -> str:
    """把 shared 日期输入归一化为 efinance 上游要求的 `%Y-%m-%d`。"""
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{command_key} 缺少日期字段 {field_name}")
    if len(text) == 8 and text.isdigit():
        return datetime.strptime(text, "%Y%m%d").strftime("%Y-%m-%d")
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        datetime.strptime(text, "%Y-%m-%d")
        return text
    raise ValueError(f"{command_key} 的 {field_name} 仅支持 YYYYMMDD 或 YYYY-MM-DD")


def _resolve_efinance_market_fs(market_name: object) -> str:
    """把 shared market 解析为可直接请求的 efinance `fs` 表达式。"""
    market = _extract_market_value(market_name)
    if market in (None, ""):
        raise ValueError("market.price.live 需要明确的 market 参数")
    mapping = {
        "A_stock": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23",
        "US_stock": "m:105,m:106,m:107",
        "Hongkong": "m:128 t:3,m:128 t:4,m:128 t:1,m:128 t:2",
        "bond": "b:MK0354",
        "futures": "m:113,m:114,m:115,m:8,m:142,m:225",
    }
    if isinstance(market, str) and market.startswith(("m:", "b:")):
        return market
    resolved = mapping.get(str(market))
    if resolved is None:
        raise ValueError(f"market.price.live 不支持 shared market: {market}")
    return resolved


def _build_limited_efinance_live_frame(fs: str, limit: int) -> pd.DataFrame:
    """按 limit 只抓取东财实时列表的必要页数。"""
    config_module = importlib.import_module("efinance.common.config")
    getter_module = importlib.import_module("efinance.common.getter")
    columns = dict(config_module.EASTMONEY_QUOTE_FIELDS)
    fields = ",".join(columns.keys())
    page_size = min(max(limit, 1), 200)
    page_count = max(1, ceil(limit / page_size))
    frames: list[pd.DataFrame] = []

    for page_number in range(1, page_count + 1):
        params = (
            ("pn", page_number),
            ("pz", page_size),
            ("po", "1"),
            ("np", "1"),
            ("fltt", "2"),
            ("invt", "2"),
            ("fid", "f3"),
            ("fs", fs),
            ("fields", fields),
        )
        response = getter_module.session.get(
            "http://push2.eastmoney.com/api/qt/clist/get",
            headers=config_module.EASTMONEY_REQUEST_HEADERS,
            params=params,
        ).json()
        diff = ((response.get("data") or {}).get("diff") or [])
        if not diff:
            continue
        page_frame = pd.DataFrame(diff)
        available_columns = [
            item for item in columns.keys() if item in page_frame.columns
        ]
        frames.append(page_frame[available_columns])

    if not frames:
        return pd.DataFrame(
            columns=list(columns.values()) + ["行情ID", "市场类型", "更新时间"]
        )

    frame = pd.concat(frames, axis=0, ignore_index=True)
    available_columns = [
        item for item in columns.keys() if item in frame.columns
    ]
    frame = frame[available_columns].rename(columns=columns)
    ordered_columns = [
        item for item in columns.values() if item in frame.columns
    ]
    frame = frame[ordered_columns]
    if "涨跌幅" in frame.columns:
        frame = frame.sort_values(by="涨跌幅", ascending=False, ignore_index=True)
    if "市场编号" in frame.columns and "代码" in frame.columns:
        frame["行情ID"] = frame["市场编号"].astype(str
                                             ) + "." + frame["代码"].astype(str)
        frame["市场类型"] = frame["市场编号"].astype(str).apply(
            lambda item: config_module.MARKET_NUMBER_DICT.get(item),
        )
        frame = frame.drop(columns=["市场编号"], errors="ignore")
    if "更新时间戳" in frame.columns:
        frame["更新时间"] = frame["更新时间戳"].apply(
            lambda item: str(pd.Timestamp.fromtimestamp(item)),
        )
        frame = frame.drop(columns=["更新时间戳"], errors="ignore")
    if "最新交易日" in frame.columns:
        frame["最新交易日"] = pd.to_datetime(
            frame["最新交易日"],
            format="%Y%m%d",
            errors="coerce",
        ).astype(str)
    return frame.head(limit)


def _adapt_efinance_history_request(
    request_data: Mapping[str, object],
    *,
    code_field_name: str,
) -> dict[str, object]:
    """将 shared history 请求翻译为 efinance `get_quote_history` 所需参数。"""
    request_keys = (
        ("symbols", "stock_codes", "symbol") if code_field_name == "stock_codes" else
        ("symbols", "codes", "symbol")
    )
    return {
        code_field_name:
        _single_or_multi(
            _coerce_request_sequence(request_data, *request_keys)
        ),
        "beg":
        str(
            _get_request_value(
                request_data, "start_date", "beg", default="19000101"
            )
        ),
        "end":
        str(
            _get_request_value(
                request_data, "end_date", "end", default="20500101"
            )
        ),
        "klt":
        int(
            _get_request_value(
                request_data, "timeframe", "klt", "period", default=101
            )
        ),
        "fqt":
        int(
            _get_request_value(
                request_data, "adjustment", "fqt", "adjust", default=1
            )
        ),
        "market_type":
        _resolve_efinance_market_type(
            _get_request_value(request_data, "market", "market_type"),
        ),
        "suppress_error":
        bool(
            _get_request_value(
                request_data, "ignore_errors", "suppress_error", default=False
            ),
        ),
        "use_id_cache":
        bool(_get_request_value(request_data, "use_id_cache", default=True)),
    }


def _adapt_efinance_quote_history_request(
    request_data: Mapping[str, object],
) -> dict[str, object]:
    """适配 `quote.price.history`，在输入已是 quote_id 时保留原值并显式开启 quote_id 模式。"""
    codes = _coerce_request_sequence(
        request_data,
        "symbols",
        "codes",
        "symbol",
        "code",
    )
    adapted_request = _adapt_efinance_history_request(
        request_data,
        code_field_name="codes",
    )
    if codes:
        adapted_request["codes"] = _single_or_multi(codes)
    if codes and all(_looks_like_efinance_quote_id(code) for code in codes):
        adapted_request["quote_id_mode"] = True
    return adapted_request


def _resolve_efinance_live_fs(market_name: object) -> str | None:
    """把 stock shared market 翻译为 efinance 支持的实时列表过滤。"""
    market = _extract_market_value(market_name)
    if market in (None, ""):
        return None
    mapping = {
        "A_stock": "沪深A股",
        "US_stock": "美股",
        "Hongkong": "港股",
        "futures": "期货",
    }
    resolved = mapping.get(str(market))
    if resolved is None:
        raise ValueError(
            f"Efinance stock.price.live 不支持 shared market: {market}"
        )
    return resolved


def _standardize_efinance_result(
    command_key: str,
    request_data: dict[str, object],
    result: object,
):
    if command_key in {"fund.profile", "bond.flow.today"
                       } and _looks_like_known_bad_payload(result):
        raise StandardizationError(
            f"{command_key} 命中了已知上游坏返回路径: {type(result).__name__}"
        )
    if command_key == "search.local":
        return _build_search_standard_result(result)
    if command_key in PRICE_HISTORY_COMMAND_KEYS:
        return _build_history_standard_result(
            command_key, request_data, result
        )
    if command_key == "fund.nav.history":
        symbol = str(_get_request_value(request_data, "symbol", "fund_code"))
        return _build_fund_nav_history_standard_result(result, symbol)
    if command_key == "fund.nav.history-batch":
        return _build_fund_nav_history_batch_result(result)
    if command_key in REALTIME_COMMAND_KEYS:
        return _build_realtime_standard_result(
            command_key, request_data, result
        )
    if command_key in PROFILE_COMMAND_KEYS:
        data = _standardize_profile_payload(result, request_data)
        return build_standard_result(
            PROFILE_INFO_CONTRACT,
            data,
            raw_payload=result,
            metadata={"backend": BackendName.EFINANCE.value},
        )
    if command_key == "resolve.quote-id":
        return build_standard_result(
            SCALAR_VALUE_CONTRACT,
            {"quote_id": _normalize_scalar(result)},
            raw_payload=result,
            metadata={"backend": BackendName.EFINANCE.value},
        )
    if command_key in SCALAR_LIST_COMMAND_KEYS:
        data = [_normalize_scalar(item) for item in list(result or [])]
        return build_standard_result(
            SCALAR_LIST_CONTRACT,
            data,
            raw_payload=result,
            metadata={"backend": BackendName.EFINANCE.value},
        )
    if command_key in SIDE_EFFECT_COMMAND_KEYS:
        return build_standard_result(
            SIDE_EFFECT_STATUS_CONTRACT,
            {
                "status": "ok",
                "message": f"{command_key} executed",
                "command_key": command_key,
            },
            raw_payload=result,
            metadata={"backend": BackendName.EFINANCE.value},
        )
    payload = _standardize_generic_payload(result)
    return build_standard_result(
        PROVIDER_RECORDS_CONTRACT,
        payload,
        raw_payload=result,
        metadata={"backend": BackendName.EFINANCE.value},
    )


def _build_search_standard_result(result: object):
    rows: list[dict[str, object]] = []
    if result is None:
        return build_standard_result(
            SEARCH_RESULTS_CONTRACT, rows, raw_payload=result
        )
    items = result if isinstance(result, list) else [result]
    for item in items:
        payload = item._asdict() if hasattr(item, "_asdict") else dict(item)
        normalized = normalize_contract_mapping(
            payload, SEARCH_RESULTS_CONTRACT
        )
        ensure_mapping_has_required_fields(normalized, SEARCH_RESULTS_CONTRACT)
        rows.append(normalized)
    return build_standard_result(
        SEARCH_RESULTS_CONTRACT, rows, raw_payload=result
    )


def _build_history_standard_result(
    command_key: str,
    request_data: dict[str, object],
    result: object,
):
    key_options = {
        "stock.price.history": ("symbols", "stock_codes", "symbol"),
        "bond.price.history": ("bond_codes", ),
        "futures.price.history": ("quote_ids", ),
        "quote.price.history": ("symbols", "codes", "symbol", "code"),
    }[command_key]
    symbols = _coerce_symbol_list(
        _get_request_value(request_data, *key_options, default=[])
    )
    frames = _coerce_frame_mapping(result)
    if isinstance(frames, pd.DataFrame):
        symbol = symbols[0] if symbols else ""
        rows = _standardize_history_frame(
            frames,
            symbol=symbol,
            provider_name=BackendName.EFINANCE.value,
        )
        return build_standard_result(
            HISTORY_BARS_CONTRACT,
            rows,
            raw_payload=result,
            metadata={"backend": BackendName.EFINANCE.value},
        )

    mapping: dict[str, list[dict[str, object]]] = {}
    for key, frame in frames.items():
        mapping[str(key)] = _standardize_history_frame(
            frame,
            symbol=str(key),
            provider_name=BackendName.EFINANCE.value,
        )
    return build_standard_result(
        HISTORY_BARS_CONTRACT,
        mapping,
        raw_payload=result,
        metadata={"backend": BackendName.EFINANCE.value},
    )


def _build_fund_nav_history_standard_result(result: object, symbol: str):
    frame = _coerce_history_frame(result)
    rows = _standardize_fund_nav_history_frame(frame, symbol=symbol)
    return build_standard_result(
        FUND_NAV_HISTORY_CONTRACT,
        rows,
        raw_payload=result,
        metadata={"backend": BackendName.EFINANCE.value},
    )


def _build_fund_nav_history_batch_result(result: object):
    if not isinstance(result, dict):
        raise StandardizationError("Fund nav batch result must be a mapping")
    mapping: dict[str, list[dict[str, object]]] = {}
    for key, frame in result.items():
        mapping[str(key)] = _standardize_fund_nav_history_frame(
            _coerce_history_frame(frame),
            symbol=str(key),
        )
    return build_standard_result(
        FUND_NAV_HISTORY_CONTRACT,
        mapping,
        raw_payload=result,
        metadata={"backend": BackendName.EFINANCE.value},
    )


def _build_realtime_standard_result(
    command_key: str,
    request_data: dict[str, object],
    result: object,
):
    if isinstance(result, pd.Series):
        frame = pd.DataFrame([result.to_dict()])
    else:
        frame = _coerce_history_frame(result)
    market_name = _extract_market_name(command_key, request_data)
    rows = _standardize_realtime_quotes_frame(
        frame,
        market_name=market_name,
        provider_name=BackendName.EFINANCE.value,
    )
    metadata = {"backend": BackendName.EFINANCE.value, "market": market_name}
    requested_limit = _extract_execution_limit(request_data)
    if requested_limit is not None and command_key in {
            "market.price.live",
            "bond.price.live",
            "futures.price.live",
            "quote.price.latest",
    }:
        metadata["execution_limit_requested"] = requested_limit
        metadata["execution_limit_applied"] = True
        metadata["execution_limit_mode"] = "provider-request"
    return build_standard_result(
        REALTIME_QUOTES_CONTRACT,
        rows,
        raw_payload=result,
        metadata=metadata,
    )


def _extract_market_name(
    command_key: str, request_data: dict[str, object]
) -> str:
    if command_key == "market.price.live":
        value = _get_request_value(request_data, "market", "fs")
    elif command_key in {"stock.price.live", "stock.price.latest",
                         "stock.price.snapshot"}:
        value = _get_request_value(request_data, "market", "fs", "market_type")
    else:
        value = _get_request_value(request_data, "market", "market_type")
    extracted = _extract_market_value(value)
    if extracted not in (None, ""):
        return str(extracted)

    default_market_map = {
        "stock.price.live": "A_stock",
        "stock.price.latest": "A_stock",
        "stock.price.snapshot": "A_stock",
        "bond.price.live": "bond",
        "futures.price.live": "futures",
        "quote.price.latest": "quote",
        "market.price.live": "market",
    }
    return default_market_map.get(command_key, "A_stock")


def _looks_like_known_bad_payload(result: object) -> bool:
    """识别已证实的上游坏返回形态，稳定归类为 provider response failure。"""
    return isinstance(result, bool) or result is None


def _resolve_efinance_market_type(market_name: object):
    if market_name in (None, ""):
        return None
    if isinstance(market_name, (list, tuple)):
        market_name = market_name[0] if market_name else None
    if market_name in (None, ""):
        return None
    if not isinstance(market_name, str):
        raise ValueError(f"Unknown market enum: {market_name}")
    market_type = getattr(efinance.utils.MarketType, market_name, None)
    if market_type is None:
        raise ValueError(f"Unknown market enum: {market_name}")
    return market_type


def _build_efinance_retry_policy() -> ProviderRetryPolicy:
    """返回 efinance 的 provider 级统一重试策略。"""
    return ProviderRetryPolicy(
        retryable_exceptions=NETWORK_RELATED_EXCEPTIONS,
        passthrough_exceptions=(ProviderContractError, ),
    )


def build_efinance_provider() -> BackendProvider:
    handlers: dict[str, CapabilityHandler] = {}
    for definition in SHARED_COMMANDS:
        if BackendName.EFINANCE not in definition.supported_backends:
            continue
        if definition.command_key == "instrument.search":
            handlers[definition.capability] = EfinanceSearchHandler()
        else:
            handlers[definition.capability
                     ] = EfinanceGenericHandler(definition.capability)

    extension_commands = get_single_backend_command_definitions(
        BackendName.EFINANCE
    )
    for definition in extension_commands:
        handlers[definition.capability
                 ] = EfinanceGenericHandler(definition.capability)

    return BackendProvider(
        backend_name=BackendName.EFINANCE,
        handlers=handlers,
        extension_commands=extension_commands,
        retry_policy=_build_efinance_retry_policy(),
    )
