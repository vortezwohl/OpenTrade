"""Yfinance provider 实现。

该模块负责 yfinance backend 的 symbol 适配、Yahoo 数据提取、
handler 实现与 provider 构建。A 股代码到 Yahoo ticker 的翻译
也在这里闭合，避免调用方承担 provider 特有语义。
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from datetime import datetime, timedelta

import pandas as pd

from opentrade.backends.base import (
    BackendProvider,
    BackendRateLimitError,
    CapabilityHandler,
    ProviderContractError,
    ProviderExecutionError,
    ProviderRetryPolicy,
)
from opentrade.contracts import build_standard_result
from opentrade.models import (
    CommandDefinition,
    CommandKind,
    RequestField,
    RequestSchema,
)
from opentrade.retry_utils import NETWORK_RELATED_EXCEPTIONS
from opentrade.backends.providers_common import (
    BackendName,
    FUND_NAV_HISTORY_CONTRACT,
    HISTORY_BARS_CONTRACT,
    PROFILE_INFO_CONTRACT,
    PROVIDER_RECORDS_CONTRACT,
    REALTIME_QUOTES_CONTRACT,
    SEARCH_RESULTS_CONTRACT,
    StandardizationError,
    _coerce_symbol_list,
    _extract_execution_limit,
    _get_request_value,
    _get_single_request_value,
    _materialize_provider_payload,
    _normalize_profile_mapping,
    _normalize_scalar,
    ensure_mapping_has_required_fields,
    normalize_contract_mapping,
)


class YfinanceSearchHandler(CapabilityHandler):
    """处理 yfinance 的搜索能力。"""

    capability_name = "instrument.search"

    def execute(self, request_data: dict[str, object]):
        adapted_request = _adapt_yfinance_search_request(request_data)
        query = str(adapted_request["query"])
        if not query:
            raise ValueError("yfinance instrument.search 需要非空关键字")

        count = int(adapted_request["count"])
        market = adapted_request["market"]
        quotes = _run_yfinance_search(query=query, count=count)

        rows: list[dict[str, object]] = []
        for quote in quotes:
            normalized = _normalize_yfinance_search_quote(quote)
            if normalized is None:
                continue
            if not _yfinance_search_row_matches_market(normalized, market):
                continue
            ensure_mapping_has_required_fields(
                normalized, SEARCH_RESULTS_CONTRACT
            )
            rows.append(normalized)

        return build_standard_result(
            SEARCH_RESULTS_CONTRACT,
            rows[:count],
            raw_payload=quotes,
            metadata={"backend": BackendName.YFINANCE.value},
        )


class YfinanceHistoryHandler(CapabilityHandler):
    """处理 yfinance 的历史行情能力。"""

    def __init__(self, capability_name: str) -> None:
        self.capability_name = capability_name

    def execute(self, request_data: dict[str, object]):
        adapted_request = _adapt_yfinance_history_request(
            self.capability_name, request_data
        )
        symbol = str(adapted_request["symbol"])
        ticker = _build_yfinance_ticker(str(adapted_request["ticker"]))
        frame = _run_yfinance_history(
            ticker,
            adapted_request["history_kwargs"],
        )
        rows = _standardize_yfinance_history_frame(frame, symbol=symbol)
        return build_standard_result(
            HISTORY_BARS_CONTRACT,
            rows,
            raw_payload=frame,
            metadata={"backend": BackendName.YFINANCE.value},
        )


class YfinanceFundNavHistoryHandler(CapabilityHandler):
    """处理 yfinance 的基金净值历史能力。"""

    capability_name = "fund.nav.history"

    def execute(self, request_data: dict[str, object]):
        adapted_request = _adapt_yfinance_fund_nav_history_request(
            request_data
        )
        symbol = str(adapted_request["symbol"])
        ticker = _build_yfinance_ticker(str(adapted_request["ticker"]))
        frame = _run_yfinance_history(
            ticker,
            adapted_request["history_kwargs"],
        )
        rows = _standardize_yfinance_fund_nav_history_frame(
            frame, symbol=symbol
        )
        return build_standard_result(
            FUND_NAV_HISTORY_CONTRACT,
            rows,
            raw_payload=frame,
            metadata={"backend": BackendName.YFINANCE.value},
        )


class YfinanceRealtimeHandler(CapabilityHandler):
    """处理 yfinance 的最新价与快照能力。"""

    def __init__(self, capability_name: str) -> None:
        self.capability_name = capability_name

    def execute(self, request_data: dict[str, object]):
        adapted_request = _adapt_yfinance_realtime_request(
            self.capability_name, request_data
        )
        try:
            rows = [
                _build_yfinance_realtime_row(
                    self.capability_name,
                    item["symbol"],
                    item["ticker"],
                )
                for item in adapted_request["symbols"]
            ]
        except Exception as exc:  # noqa: BLE001
            raise ProviderExecutionError(
                BackendName.YFINANCE,
                self.capability_name,
                "execute",
                str(exc),
            ) from exc
        return build_standard_result(
            REALTIME_QUOTES_CONTRACT,
            rows,
            raw_payload=rows,
            metadata={"backend": BackendName.YFINANCE.value},
        )


class YfinanceProfileHandler(CapabilityHandler):
    """`yfinance` 的股票与通用行情资料能力实现。"""

    def __init__(self, capability_name: str) -> None:
        self.capability_name = capability_name

    def execute(self, request_data: dict[str, object]):
        adapted_request = _adapt_yfinance_profile_request(
            self.capability_name, request_data
        )
        symbol = str(adapted_request["symbol"])
        ticker = _build_yfinance_ticker(str(adapted_request["ticker"]))
        quote_info = _extract_yfinance_quote_info(ticker)
        metadata = _extract_yfinance_history_metadata(ticker)
        fast_info = _extract_yfinance_fast_info(ticker)

        payload = {
            "code": symbol,
            "name": (
                quote_info.get("shortName")
                or quote_info.get("longName")
                or metadata.get("shortName")
                or symbol
            ),
            "quote_id": symbol,
            "market": _resolve_yfinance_profile_market(
                symbol, quote_info, metadata
            ),
            "pe": quote_info.get("trailingPE") or quote_info.get("forwardPE"),
            "pb": quote_info.get("priceToBook"),
            "industry": quote_info.get("industry") or quote_info.get("sector"),
            "total_market_value": quote_info.get("marketCap")
            or fast_info.get("marketCap"),
        }
        normalized = _normalize_profile_mapping(payload, symbol)
        return build_standard_result(
            PROFILE_INFO_CONTRACT,
            normalized,
            raw_payload=quote_info,
            provider_fields={
                "info": _materialize_provider_payload(quote_info),
                "history_metadata": _materialize_provider_payload(metadata),
                "fast_info": _materialize_provider_payload(fast_info),
            },
            metadata={"backend": BackendName.YFINANCE.value},
        )


class YfinanceFundProfileHandler(CapabilityHandler):
    """`yfinance` 的基金资料能力实现。"""

    capability_name = "fund.profile"

    def execute(self, request_data: dict[str, object]):
        adapted_request = _adapt_yfinance_fund_profile_request(request_data)
        symbol = str(adapted_request["symbol"])
        ticker = _build_yfinance_ticker(str(adapted_request["ticker"]))
        quote_info = _extract_yfinance_quote_info(ticker)
        metadata = _extract_yfinance_history_metadata(ticker)
        funds_data = _extract_yfinance_funds_data(ticker)

        payload = {
            "code": symbol,
            "name": (
                quote_info.get("shortName")
                or quote_info.get("longName")
                or funds_data.get("fund_overview", {}).get("family")
                or symbol
            ),
            "quote_id": symbol,
            "market": "fund",
        }
        normalized = _normalize_profile_mapping(payload, symbol)
        return build_standard_result(
            PROFILE_INFO_CONTRACT,
            normalized,
            raw_payload=quote_info,
            provider_fields={
                "info": _materialize_provider_payload(quote_info),
                "history_metadata": _materialize_provider_payload(metadata),
                "funds_data": funds_data,
            },
            metadata={"backend": BackendName.YFINANCE.value},
        )


class YfinanceQuoteNewsHandler(CapabilityHandler):
    """`yfinance` 的 Yahoo 新闻扩展命令实现。"""

    capability_name = "yfinance.quote.news"

    def execute(self, request_data: dict[str, object]):
        symbol = _normalize_yfinance_symbol(
            str(_get_request_value(request_data, "quote_id", "symbol")),
        )
        count = int(
            _get_request_value(
                request_data, "result_count", "count", default=10
            )
        )
        ticker = _build_yfinance_ticker(symbol)
        news_items = _extract_yfinance_news(ticker)[:count]

        rows: list[dict[str, object]] = []
        for item in news_items:
            normalized = normalize_contract_mapping(
                {
                    "name": item.get("title")
                    or item.get("publisher")
                    or symbol,
                    "symbol": symbol,
                    "code": item.get("publisher"),
                    "provider_name": BackendName.YFINANCE.value,
                },
                PROVIDER_RECORDS_CONTRACT,
            )
            ensure_mapping_has_required_fields(
                normalized, PROVIDER_RECORDS_CONTRACT
            )
            rows.append(normalized)

        return build_standard_result(
            PROVIDER_RECORDS_CONTRACT,
            rows,
            raw_payload=news_items,
            metadata={
                "backend": BackendName.YFINANCE.value,
                "extension_command": self.capability_name,
            },
        )


def _load_yfinance_module():
    try:
        return importlib.import_module("yfinance")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "yfinance backend is unavailable because package "
            "'yfinance' is not installed."
        ) from exc


def _load_yfinance_exceptions():
    return importlib.import_module("yfinance.exceptions")


def _normalize_yfinance_symbol(value: str) -> str:
    return value.strip().upper()


def _run_yfinance_with_guardrails(callback, *args, **kwargs):
    try:
        return callback(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        exceptions_module = _load_yfinance_exceptions()
        rate_limit_error = getattr(exceptions_module, "YFRateLimitError")
        invalid_period_error = getattr(
            exceptions_module, "YFInvalidPeriodError"
        )
        if isinstance(exc, rate_limit_error):
            raise BackendRateLimitError(
                "Yahoo rate limited the request. Please retry later."
            ) from exc
        if isinstance(exc, invalid_period_error):
            raise ProviderContractError(
                BackendName.YFINANCE, "yfinance.history", "adapt", str(exc)
            ) from exc
        raise


def _build_yfinance_retry_policy() -> ProviderRetryPolicy:
    """返回 yfinance 的 provider 级统一重试策略。"""
    return ProviderRetryPolicy(
        retryable_exceptions=NETWORK_RELATED_EXCEPTIONS,
        rate_limit_exceptions=(BackendRateLimitError,),
        passthrough_exceptions=(ProviderContractError,),
    )


def _build_yfinance_ticker(symbol: str):
    yfinance = _load_yfinance_module()
    return yfinance.Ticker(_normalize_yfinance_symbol(symbol))


def _run_yfinance_search(*, query: str, count: int) -> list[dict[str, object]]:
    yfinance = _load_yfinance_module()
    search = _run_yfinance_with_guardrails(
        yfinance.Search,
        query,
        max_results=max(count, 1),
        news_count=0,
        lists_count=0,
        include_research=False,
        include_nav_links=False,
        raise_errors=True,
    )
    return list(getattr(search, "quotes", []) or [])


def _normalize_yfinance_search_quote(
    quote: Mapping[str, object],
) -> dict[str, object] | None:
    symbol = quote.get("symbol")
    if symbol in (None, ""):
        return None
    name = (
        quote.get("shortname")
        or quote.get("longname")
        or quote.get("name")
        or symbol
    )
    classify = (
        quote.get("quoteType")
        or quote.get("typeDisp")
        or quote.get("exchange")
    )
    payload = {
        "code": str(symbol),
        "name": str(name),
        "quote_id": str(symbol),
        "classify": str(classify) if classify not in (None, "") else None,
    }
    if quote.get("exchange"):
        payload["pinyin"] = str(quote.get("exchange"))
    return normalize_contract_mapping(payload, SEARCH_RESULTS_CONTRACT)


def _yfinance_search_row_matches_market(
    row: Mapping[str, object],
    market: object,
) -> bool:
    if market in (None, ""):
        return True
    classify = str(row.get("classify", "")).upper()
    market_name = str(market)
    if market_name == "US_stock":
        return (
            "EQUITY" in classify
            or "ETF" in classify
            or "MUTUALFUND" in classify
        )
    if market_name == "A_stock":
        return ".SS" in str(row.get("code", "")) or ".SZ" in str(
            row.get("code", "")
        )
    return True


def _adapt_yfinance_search_request(
    request_data: Mapping[str, object],
) -> dict[str, object]:
    """把 shared 资料请求翻译为 yfinance 请求参数。"""
    return {
        "query": str(
            _get_request_value(request_data, "keyword", "query", default="")
        ).strip(),
        "count": int(
            _get_request_value(
                request_data, "result_count", "count", default=5
            )
        ),
        "market": _get_request_value(request_data, "market", "market_type"),
    }


def _adapt_yfinance_history_request(
    command_key: str,
    request_data: Mapping[str, object],
) -> dict[str, object]:
    """把 shared 历史行情请求翻译为 yfinance `Ticker.history` 参数。"""
    symbols = _resolve_yfinance_history_symbols(command_key, request_data)
    if len(symbols) != 1:
        raise ProviderContractError(
            BackendName.YFINANCE,
            command_key,
            "adapt",
            f"yfinance {command_key} 只支持单个标的",
        )
    symbol = symbols[0]
    history_kwargs = _build_yfinance_history_kwargs(request_data)
    _validate_yfinance_history_request(command_key, history_kwargs)
    return {
        "symbol": symbol,
        "ticker": _normalize_yfinance_shared_symbol(
            symbol,
            market=_get_request_value(request_data, "market", "market_type"),
            command_key=command_key,
        ),
        "history_kwargs": history_kwargs,
    }


def _adapt_yfinance_fund_nav_history_request(
    request_data: Mapping[str, object],
) -> dict[str, object]:
    """把 shared 基金净值历史请求翻译为 yfinance `Ticker.history` 参数。"""
    symbol = _normalize_yfinance_symbol(
        _get_single_request_value(
            request_data, "fund.nav.history", "symbol", "fund_code"
        ),
    )
    return {
        "symbol": symbol,
        "ticker": _normalize_yfinance_fund_symbol(
            symbol, command_key="fund.nav.history"
        ),
        "history_kwargs": {
            "period": "max",
            "interval": "1d",
            "auto_adjust": False,
            "back_adjust": False,
        },
    }


def _adapt_yfinance_realtime_request(
    command_key: str,
    request_data: Mapping[str, object],
) -> dict[str, object]:
    """把 shared 最新价或快照请求翻译为 yfinance 请求参数。"""
    return {
        "symbols": _resolve_yfinance_realtime_symbols(
            command_key,
            request_data,
            execution_limit=_extract_execution_limit(request_data),
        ),
    }


def _adapt_yfinance_profile_request(
    command_key: str,
    request_data: Mapping[str, object],
) -> dict[str, object]:
    """把 shared 资料请求翻译为 yfinance 请求参数。"""
    symbol = _resolve_yfinance_profile_symbol(command_key, request_data)
    return {
        "symbol": symbol,
        "ticker": _normalize_yfinance_shared_symbol(
            symbol,
            market=_get_request_value(request_data, "market", "market_type"),
            command_key=command_key,
        ),
    }


def _adapt_yfinance_fund_profile_request(
    request_data: Mapping[str, object],
) -> dict[str, object]:
    """把 shared 基金资料请求翻译为 yfinance 请求参数。"""
    values = _coerce_symbol_list(
        _get_request_value(
            request_data, "symbols", "fund_codes", "symbol", default=[]
        )
    )
    if len(values) != 1:
        raise ProviderContractError(
            BackendName.YFINANCE,
            "fund.profile",
            "adapt",
            "yfinance fund.profile 只支持单个标的",
        )
    symbol = _normalize_yfinance_symbol(values[0])
    return {
        "symbol": symbol,
        "ticker": _normalize_yfinance_fund_symbol(
            symbol, command_key="fund.profile"
        ),
    }


def _normalize_yfinance_shared_symbol(
    value: str,
    *,
    market: object,
    command_key: str,
) -> str:
    """把共享 symbol 翻译成 Yahoo 可接受的 ticker。"""
    symbol = _normalize_yfinance_symbol(value)
    if symbol.endswith((".SS", ".SZ", ".HK")):
        return symbol
    market_name = str(market) if market not in (None, "") else None
    if market_name == "Hongkong":
        return symbol + ".HK"
    if market_name == "A_stock":
        return _translate_a_share_to_yahoo_ticker(symbol, command_key)
    return symbol


def _translate_a_share_to_yahoo_ticker(symbol: str, command_key: str) -> str:
    """把 6 位 A 股代码翻译成 Yahoo ticker。"""
    if symbol.startswith(("600", "601", "603", "605", "688", "689")):
        return symbol + ".SS"
    if symbol.startswith(("000", "001", "002", "003", "300", "301")):
        return symbol + ".SZ"
    raise ProviderContractError(
        BackendName.YFINANCE,
        command_key,
        "adapt",
        f"无法从共享 A 股代码推导 Yahoo ticker: {symbol}",
    )


def _normalize_yfinance_fund_symbol(
    value: str,
    *,
    command_key: str,
) -> str:
    """基金共享标识在 yfinance 下只接受 Yahoo 自身 ticker。"""
    symbol = _normalize_yfinance_symbol(value)
    if symbol.isdigit():
        raise ProviderContractError(
            BackendName.YFINANCE,
            command_key,
            "adapt",
            "yfinance 当前不支持大陆基金代码，请改用 Efinance/Akshare 或直接传 Yahoo 基金 ticker",
        )
    return symbol


def _build_yfinance_history_kwargs(
    request_data: Mapping[str, object],
) -> dict[str, object]:
    interval = {
        1: "1m",
        5: "5m",
        15: "15m",
        30: "30m",
        60: "60m",
        101: "1d",
        102: "1wk",
        103: "1mo",
    }.get(
        int(
            _get_request_value(
                request_data, "timeframe", "klt", "period", default=101
            )
        ),
        "1d",
    )
    auto_adjust = (
        int(
            _get_request_value(
                request_data, "adjustment", "fqt", "adjust", default=1
            )
        )
        == 1
    )
    return {
        "start": _normalize_yfinance_date(
            _get_request_value(
                request_data, "start_date", "beg", default="19000101"
            ),
        ),
        "end": _normalize_yfinance_date(
            _get_request_value(
                request_data, "end_date", "end", default="20500101"
            ),
        ),
        "interval": interval,
        "auto_adjust": auto_adjust,
        "back_adjust": False,
    }


def _normalize_yfinance_date(value: object) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    return text


def _validate_yfinance_history_request(
    command_key: str,
    history_kwargs: Mapping[str, object],
) -> None:
    """校验 yfinance 分时历史窗口，避免直接触发 provider 侧硬失败。"""
    interval = str(history_kwargs.get("interval") or "")
    intraday_limits = {
        "1m": 8,
        "5m": 60,
        "15m": 60,
        "30m": 60,
        "60m": 730,
    }
    limit_days = intraday_limits.get(interval)
    if limit_days is None:
        return

    start_text = history_kwargs.get("start")
    end_text = history_kwargs.get("end")
    if not start_text or not end_text:
        raise ProviderContractError(
            BackendName.YFINANCE,
            command_key,
            "adapt",
            f"yfinance {command_key} 的 {interval} 分时查询必须显式提供 start_date 和 end_date",
        )

    start_dt = datetime.fromisoformat(str(start_text))
    end_dt = datetime.fromisoformat(str(end_text))
    if end_dt <= start_dt:
        raise ProviderContractError(
            BackendName.YFINANCE,
            command_key,
            "adapt",
            f"yfinance {command_key} 要求 end_date 晚于 start_date",
        )

    span = end_dt - start_dt
    limit = timedelta(days=limit_days)
    if span > limit:
        raise ProviderContractError(
            BackendName.YFINANCE,
            command_key,
            "adapt",
            f"yfinance {command_key} 的 {interval} 分时窗口不能超过 {limit_days} 天",
        )

    earliest_allowed = datetime.now() - limit
    if start_dt < earliest_allowed:
        raise ProviderContractError(
            BackendName.YFINANCE,
            command_key,
            "adapt",
            f"yfinance {command_key} 的 {interval} 分时起始时间不能早于近 {limit_days} 天",
        )


def _run_yfinance_history(
    ticker, kwargs: Mapping[str, object]
) -> pd.DataFrame:
    frame = _run_yfinance_with_guardrails(ticker.history, **kwargs)
    if not isinstance(frame, pd.DataFrame):
        raise StandardizationError(
            "yfinance history result is not a DataFrame"
        )
    if isinstance(frame.index, pd.DatetimeIndex):
        frame = frame.reset_index()
    return frame


def _resolve_yfinance_history_symbols(
    command_key: str,
    request_data: Mapping[str, object],
) -> list[str]:
    key_map = {
        "stock.price.history": ("symbols", "stock_codes", "symbol"),
        "quote.price.history": ("symbols", "codes", "symbol"),
    }
    keys = key_map[command_key]
    values = _coerce_symbol_list(
        _get_request_value(request_data, *keys, default=[])
    )
    return [_normalize_yfinance_symbol(value) for value in values]


def _standardize_yfinance_history_frame(
    frame: pd.DataFrame,
    *,
    symbol: str,
) -> list[dict[str, object]]:
    rename_map = {
        "Date": "date",
        "Datetime": "date",
        "Open": "open",
        "Close": "close",
        "High": "high",
        "Low": "low",
        "Volume": "volume",
        "Dividends": "dividends",
        "Stock Splits": "stock_splits",
    }
    rows: list[dict[str, object]] = []
    if frame is None or frame.empty:
        return rows
    normalized_frame = frame.rename(columns=rename_map)
    if "date" in normalized_frame.columns:
        normalized_frame["date"] = normalized_frame["date"].apply(
            _normalize_scalar
        )
    for _, row in normalized_frame.iterrows():
        payload = {
            "date": row.get("date"),
            "symbol": symbol,
            "open": row.get("open"),
            "close": row.get("close"),
            "high": row.get("high"),
            "low": row.get("low"),
            "volume": row.get("volume"),
        }
        payload = {
            key: _normalize_scalar(value)
            for key, value in payload.items()
            if value is not None
        }
        normalized = normalize_contract_mapping(payload, HISTORY_BARS_CONTRACT)
        ensure_mapping_has_required_fields(normalized, HISTORY_BARS_CONTRACT)
        normalized["provider_name"] = BackendName.YFINANCE.value
        rows.append(normalized)
    return rows


def _standardize_yfinance_fund_nav_history_frame(
    frame: pd.DataFrame,
    *,
    symbol: str,
) -> list[dict[str, object]]:
    rows = _standardize_yfinance_history_frame(frame, symbol=symbol)
    normalized_rows: list[dict[str, object]] = []
    for row in rows:
        payload = {
            "date": row["date"],
            "symbol": row["symbol"],
            "unit_nav": row["close"],
        }
        if "close" in row:
            payload["accumulated_nav"] = row["close"]
        normalized = normalize_contract_mapping(
            payload, FUND_NAV_HISTORY_CONTRACT
        )
        ensure_mapping_has_required_fields(
            normalized, FUND_NAV_HISTORY_CONTRACT
        )
        normalized_rows.append(normalized)
    return normalized_rows


def _resolve_yfinance_realtime_symbols(
    command_key: str,
    request_data: Mapping[str, object],
    execution_limit: int | None = None,
) -> list[dict[str, str]]:
    key_map = {
        "quote.price.latest": ("symbols", "symbol"),
        "stock.price.latest": ("symbols", "symbol"),
        "stock.price.snapshot": ("symbol", "symbols"),
    }
    values = _coerce_symbol_list(
        _get_request_value(request_data, *key_map[command_key], default=[])
    )
    if len(values) != 1:
        raise ProviderContractError(
            BackendName.YFINANCE,
            command_key,
            "adapt",
            f"yfinance {command_key} 只支持单个标的",
        )
    if execution_limit is not None:
        values = values[:execution_limit]
    market = _get_request_value(request_data, "market", "market_type")
    symbols: list[dict[str, str]] = []
    for value in values:
        symbol = _normalize_yfinance_symbol(value)
        symbols.append(
            {
                "symbol": symbol,
                "ticker": _normalize_yfinance_shared_symbol(
                    symbol,
                    market=market,
                    command_key=command_key,
                ),
            }
        )
    return symbols


def _extract_yfinance_fast_info(ticker) -> dict[str, object]:
    fast_info = ticker.fast_info
    if hasattr(fast_info, "items"):
        return {str(key): fast_info.get(key) for key in fast_info.keys()}
    return {}


def _extract_yfinance_quote_info(ticker) -> dict[str, object]:
    return _run_yfinance_with_guardrails(lambda: dict(ticker.info or {}))


def _extract_yfinance_history_metadata(ticker) -> dict[str, object]:
    return _run_yfinance_with_guardrails(
        lambda: dict(ticker.history_metadata or {})
    )


def _extract_yfinance_funds_data(ticker) -> dict[str, object]:
    funds_data = ticker.funds_data
    return {
        "description": _normalize_scalar(
            getattr(funds_data, "description", None)
        ),
        "fund_overview": _materialize_provider_payload(
            getattr(funds_data, "fund_overview", None)
        ),
        "fund_operations": _materialize_provider_payload(
            getattr(funds_data, "fund_operations", None)
        ),
        "asset_classes": _materialize_provider_payload(
            getattr(funds_data, "asset_classes", None)
        ),
        "top_holdings": _materialize_provider_payload(
            getattr(funds_data, "top_holdings", None)
        ),
        "bond_ratings": _materialize_provider_payload(
            getattr(funds_data, "bond_ratings", None)
        ),
        "sector_weightings": _materialize_provider_payload(
            getattr(funds_data, "sector_weightings", None)
        ),
    }


def _resolve_yfinance_profile_symbol(
    command_key: str,
    request_data: Mapping[str, object],
) -> str:
    key_map = {
        "stock.profile": ("symbol", "symbols", "stock_codes"),
        "quote.profile": ("symbol", "symbols"),
    }
    values = _coerce_symbol_list(
        _get_request_value(request_data, *key_map[command_key], default=[])
    )
    if len(values) != 1:
        raise ProviderContractError(
            BackendName.YFINANCE,
            command_key,
            "adapt",
            f"yfinance {command_key} 只支持单个标的",
        )
    return _normalize_yfinance_symbol(values[0])


def _resolve_yfinance_profile_market(
    symbol: str,
    quote_info: Mapping[str, object],
    metadata: Mapping[str, object],
) -> str:
    market = (
        quote_info.get("market")
        or quote_info.get("quoteType")
        or metadata.get("instrumentType")
    )
    if market in (None, ""):
        if symbol.endswith((".SS", ".SZ")) or (
            symbol.isdigit() and len(symbol) == 6
        ):
            return "A_stock"
        return "US_stock"
    return str(market)


def _build_yfinance_realtime_row(
    command_key: str,
    symbol: str,
    ticker_symbol: str,
) -> dict[str, object]:
    ticker = _build_yfinance_ticker(ticker_symbol)
    fast_info = _extract_yfinance_fast_info(ticker)
    quote_info = _extract_yfinance_quote_info(ticker)
    metadata = _extract_yfinance_history_metadata(ticker)
    payload = {
        "symbol": symbol,
        "name": (
            quote_info.get("shortName")
            or quote_info.get("longName")
            or metadata.get("shortName")
            or symbol
        ),
        "close": fast_info.get("lastPrice")
        or metadata.get("regularMarketPrice"),
        "quote_id": symbol,
        "market": _resolve_yfinance_realtime_market(
            command_key, symbol, quote_info, metadata
        ),
        "open": fast_info.get("open") or metadata.get("regularMarketOpen"),
        "high": fast_info.get("dayHigh")
        or metadata.get("regularMarketDayHigh"),
        "low": fast_info.get("dayLow") or metadata.get("regularMarketDayLow"),
        "volume": fast_info.get("lastVolume")
        or metadata.get("regularMarketVolume"),
    }
    normalized = normalize_contract_mapping(payload, REALTIME_QUOTES_CONTRACT)
    ensure_mapping_has_required_fields(normalized, REALTIME_QUOTES_CONTRACT)
    normalized["provider_name"] = BackendName.YFINANCE.value
    return normalized


def _resolve_yfinance_realtime_market(
    command_key: str,
    symbol: str,
    quote_info: Mapping[str, object],
    metadata: Mapping[str, object],
) -> str:
    if command_key == "quote.price.latest":
        return "quote"
    market = quote_info.get("market") or metadata.get("exchangeName")
    if market not in (None, ""):
        return str(market)
    if symbol.endswith((".SS", ".SZ")) or (
        symbol.isdigit() and len(symbol) == 6
    ):
        return "A_stock"
    return "US_stock"


def _extract_yfinance_news(ticker) -> list[dict[str, object]]:
    return list(_run_yfinance_with_guardrails(lambda: list(ticker.news or [])))


def build_yfinance_provider() -> BackendProvider:
    handlers: dict[str, CapabilityHandler] = {
        "instrument.search": YfinanceSearchHandler(),
        "stock.price.history": YfinanceHistoryHandler("stock.price.history"),
        "quote.price.history": YfinanceHistoryHandler("quote.price.history"),
        "stock.price.latest": YfinanceRealtimeHandler("stock.price.latest"),
        "stock.price.snapshot": YfinanceRealtimeHandler(
            "stock.price.snapshot"
        ),
        "quote.price.latest": YfinanceRealtimeHandler("quote.price.latest"),
        "stock.profile": YfinanceProfileHandler("stock.profile"),
        "quote.profile": YfinanceProfileHandler("quote.profile"),
        "yfinance.quote.news": YfinanceQuoteNewsHandler(),
    }
    return BackendProvider(
        backend_name=BackendName.YFINANCE,
        handlers=handlers,
        extension_commands=(
            CommandDefinition(
                command_key="yfinance.quote.news",
                cli_path=("quote", "news"),
                capability="yfinance.quote.news",
                request_schema=RequestSchema(
                    schema_name="yfinance-quote-news-request",
                    fields=(
                        RequestField(
                            name="quote_id",
                            cli_name="quote-id",
                            annotation=str,
                            required=True,
                            help_text="Yahoo ticker / quote 标识。",
                        ),
                        RequestField(
                            name="result_count",
                            cli_name="result-count",
                            annotation=int,
                            required=False,
                            default=10,
                            help_text="返回新闻条数。",
                        ),
                    ),
                ),
                help_text="获取 Yahoo Finance 新闻列表（yfinance 专属扩展）。",
                kind=CommandKind.PROVIDER_EXTENSION,
                supported_backends=(BackendName.YFINANCE,),
                allow_watch=False,
                has_side_effect=False,
                provider_name=BackendName.YFINANCE,
            ),
        ),
        retry_policy=_build_yfinance_retry_policy(),
    )
