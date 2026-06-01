"""内建 provider 的实现。"""

from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from typing import Any

import efinance
import pandas as pd

from efinance_cli.backends.base import BackendProvider, CapabilityHandler
from efinance_cli.command_catalog import (
    SHARED_COMMANDS,
    get_command_binding,
    get_single_backend_command_definitions,
)
from efinance_cli.contracts import (
    FUND_NAV_HISTORY_CONTRACT,
    HISTORY_BARS_CONTRACT,
    PROFILE_INFO_CONTRACT,
    PROVIDER_RECORDS_CONTRACT,
    REALTIME_QUOTES_CONTRACT,
    SCALAR_LIST_CONTRACT,
    SCALAR_VALUE_CONTRACT,
    SEARCH_RESULTS_CONTRACT,
    SIDE_EFFECT_STATUS_CONTRACT,
    StandardizationError,
    build_standard_result,
    ensure_mapping_has_required_fields,
    normalize_contract_mapping,
)
from efinance_cli.models import (
    BackendName,
    CommandDefinition,
    CommandKind,
    RequestField,
    RequestSchema,
)
from efinance_cli.retry_utils import call_with_network_retry


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

YFINANCE_SHARED_COMMAND_KEYS = {
    "instrument.search",
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


class EfinanceSearchHandler(CapabilityHandler):
    """`efinance` 的默认搜索能力实现。"""

    capability_name = "instrument.search"

    def execute(self, request_data: dict[str, object]):
        market_type = _get_request_value(request_data, "market_type", "market")
        result = call_with_network_retry(
            efinance.utils.search_quote,
            keyword=_get_request_value(request_data, "keyword", "query"),
            market_type=_resolve_efinance_market_type(market_type),
            count=_get_request_value(request_data, "count", "result_count", default=5),
            use_local=_get_request_value(request_data, "use_local", "use_local_cache", default=True),
        )
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

        callback = getattr(getattr(efinance, module_name), function_name)
        if self.capability_name in SIDE_EFFECT_COMMAND_KEYS:
            result = callback(**request_data)
        else:
            result = call_with_network_retry(callback, **request_data)
        return _standardize_efinance_result(self.capability_name, request_data, result)


class AkshareSearchHandler(CapabilityHandler):
    """`akshare` 的搜索能力实现。"""

    capability_name = "instrument.search"

    def execute(self, request_data: dict[str, object]):
        akshare = _load_akshare_module()
        market = _get_request_value(request_data, "market_type", "market")
        query = str(_get_request_value(request_data, "keyword", "query")).strip()
        result_count = int(_get_request_value(request_data, "count", "result_count", default=5))

        loaders = self._build_catalog_loaders(akshare, market)
        rows: list[dict[str, object]] = []
        errors: list[str] = []
        for classify, loader in loaders:
            try:
                frame = loader()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{classify}: {exc}")
                continue
            rows.extend(self._standardize_catalog_rows(frame, classify))

        if not rows and errors:
            raise RuntimeError(
                "Akshare search catalogs unavailable: " + " | ".join(errors)
            )

        filtered = _filter_search_rows(rows, query)
        deduplicated = _deduplicate_search_rows(filtered)
        limited = deduplicated[:result_count]
        for row in limited:
            ensure_mapping_has_required_fields(row, SEARCH_RESULTS_CONTRACT)
        return build_standard_result(
            SEARCH_RESULTS_CONTRACT,
            limited,
            raw_payload={"errors": errors, "total_candidates": len(rows)},
        )

    def _build_catalog_loaders(self, akshare: object, market: object) -> list[tuple[str, object]]:
        loaders: list[tuple[str, object]] = []
        market_name = str(market) if market not in (None, "") else None
        if market_name in {None, "A_stock"}:
            loaders.extend(
                [
                    ("A_stock", lambda: akshare.stock_info_sh_name_code("主板A股")),
                    ("A_stock", lambda: akshare.stock_info_sz_name_code("A股列表")),
                ]
            )
        if market_name is None:
            loaders.append(("fund", akshare.fund_name_em))
        if market_name in {None, "US_stock"} and hasattr(akshare, "get_us_stock_name"):
            loaders.append(("US_stock", akshare.get_us_stock_name))
        return loaders

    def _standardize_catalog_rows(
        self,
        frame: pd.DataFrame,
        classify: str,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        if frame is None or frame.empty:
            return rows

        if classify == "A_stock":
            code_column = "证券代码" if "证券代码" in frame.columns else "A股代码"
            name_column = "证券简称" if "证券简称" in frame.columns else "A股简称"
            for _, row in frame.iterrows():
                item = {
                    "code": str(row.get(code_column, "")).strip(),
                    "name": str(row.get(name_column, "")).strip(),
                    "pinyin": None,
                    "quote_id": str(row.get(code_column, "")).strip(),
                    "classify": classify,
                }
                self._append_if_valid(rows, item)
            return rows

        if classify == "fund":
            for _, row in frame.iterrows():
                item = {
                    "code": str(row.get("基金代码", "")).strip(),
                    "name": str(row.get("基金简称", "")).strip(),
                    "pinyin": str(row.get("拼音缩写", "")).strip() or None,
                    "quote_id": str(row.get("基金代码", "")).strip(),
                    "classify": str(row.get("基金类型", "")).strip() or classify,
                }
                self._append_if_valid(rows, item)
            return rows

        if classify == "US_stock":
            for _, row in frame.iterrows():
                display_name = str(row.get("cname", "")).strip() or str(row.get("name", "")).strip()
                item = {
                    "code": str(row.get("symbol", "")).strip(),
                    "name": display_name,
                    "pinyin": str(row.get("name", "")).strip() or None,
                    "quote_id": str(row.get("symbol", "")).strip(),
                    "classify": classify,
                }
                self._append_if_valid(rows, item)
            return rows

        raise StandardizationError(f"Unsupported akshare catalog classify: {classify}")

    def _append_if_valid(
        self,
        rows: list[dict[str, object]],
        item: dict[str, object],
    ) -> None:
        try:
            normalized = normalize_contract_mapping(item, SEARCH_RESULTS_CONTRACT)
            ensure_mapping_has_required_fields(normalized, SEARCH_RESULTS_CONTRACT)
        except StandardizationError:
            return
        rows.append(normalized)


class AkshareStockPriceHistoryHandler(CapabilityHandler):
    capability_name = "stock.price.history"

    def execute(self, request_data: dict[str, object]):
        akshare = _load_akshare_module()
        market = _get_request_value(request_data, "market_type", "market")
        if market not in (None, "", "A_stock"):
            raise ValueError("Akshare stock.price.history 当前仅支持 A_stock 市场")

        symbols = _coerce_symbol_list(_get_request_value(request_data, "stock_codes", "symbol", default=[]))
        if len(symbols) != 1:
            raise ValueError("Akshare stock.price.history 当前仅支持单标的请求")

        adjust_map = {0: "", 1: "qfq", 2: "hfq"}
        period_map = {101: "daily", 102: "weekly", 103: "monthly"}
        frame = akshare.stock_zh_a_hist(
            symbol=symbols[0],
            period=period_map[int(_get_request_value(request_data, "klt", "period", default=101))],
            start_date=str(_get_request_value(request_data, "beg", "start_date", default="19000101")),
            end_date=str(_get_request_value(request_data, "end", "end_date", default="20500101")),
            adjust=adjust_map[int(_get_request_value(request_data, "fqt", "adjust", default=1))],
        )
        rows = _standardize_history_frame(
            frame,
            symbol=symbols[0],
            provider_name=BackendName.AKSHARE.value,
        )
        return build_standard_result(
            HISTORY_BARS_CONTRACT,
            rows,
            raw_payload=frame,
            metadata={"backend": BackendName.AKSHARE.value},
        )


class AkshareStockProfileHandler(CapabilityHandler):
    capability_name = "stock.profile"

    def execute(self, request_data: dict[str, object]):
        market = _get_request_value(request_data, "market_type", "market")
        if market not in (None, "", "A_stock"):
            raise ValueError("Akshare stock.profile 当前仅支持 A_stock 市场")

        symbols = _coerce_symbol_list(_get_request_value(request_data, "stock_codes", "symbol", default=[]))
        if len(symbols) != 1:
            raise ValueError("Akshare stock.profile 当前仅支持单标的请求")

        akshare = _load_akshare_module()
        result = akshare.stock_individual_info_em(symbol=symbols[0])
        data = _standardize_profile_payload(result, request_data, code_key="stock_codes")
        return build_standard_result(
            PROFILE_INFO_CONTRACT,
            data,
            raw_payload=result,
            metadata={"backend": BackendName.AKSHARE.value},
        )


class AkshareStockPriceLiveHandler(CapabilityHandler):
    capability_name = "stock.price.live"

    def execute(self, request_data: dict[str, object]):
        market = _extract_market_value(_get_request_value(request_data, "fs", "market"))
        if market not in (None, "", "A_stock"):
            raise ValueError("Akshare stock.price.live 当前仅支持 A_stock 市场")

        akshare = _load_akshare_module()
        result = akshare.stock_zh_a_spot_em()
        frame = _coerce_history_frame(result)
        rows = _standardize_realtime_quotes_frame(
            frame,
            market_name="A_stock",
            provider_name=BackendName.AKSHARE.value,
        )
        return build_standard_result(
            REALTIME_QUOTES_CONTRACT,
            rows,
            raw_payload=result,
            metadata={"backend": BackendName.AKSHARE.value},
        )


class AkshareFundNavHistoryHandler(CapabilityHandler):
    capability_name = "fund.nav.history"

    def execute(self, request_data: dict[str, object]):
        akshare = _load_akshare_module()
        result = akshare.fund_open_fund_info_em(
            symbol=str(_get_request_value(request_data, "fund_code", "symbol")),
            indicator="单位净值走势",
        )
        frame = _coerce_history_frame(result)
        rows = _standardize_fund_nav_history_frame(
            frame,
            symbol=str(_get_request_value(request_data, "fund_code", "symbol")),
        )
        return build_standard_result(
            FUND_NAV_HISTORY_CONTRACT,
            rows,
            raw_payload=result,
            metadata={"backend": BackendName.AKSHARE.value},
        )


class AkshareIndustryBoardsHandler(CapabilityHandler):
    capability_name = "akshare.industry.boards"

    def execute(self, request_data: dict[str, object]):
        _ = request_data
        akshare = _load_akshare_module()
        result = akshare.stock_board_industry_name_em()
        frame = _coerce_history_frame(result)
        rows = _standardize_provider_records_frame(
            frame,
            provider_name=BackendName.AKSHARE.value,
        )
        return build_standard_result(
            PROVIDER_RECORDS_CONTRACT,
            rows,
            raw_payload=result,
            metadata={
                "backend": BackendName.AKSHARE.value,
                "extension_command": "akshare.industry.boards",
            },
        )


class YfinanceSearchHandler(CapabilityHandler):
    """`yfinance` 的共享搜索能力实现。"""

    capability_name = "instrument.search"

    def execute(self, request_data: dict[str, object]):
        query = str(_get_request_value(request_data, "keyword", "query", default="")).strip()
        if not query:
            raise ValueError("yfinance instrument.search 需要非空关键字")

        count = int(_get_request_value(request_data, "count", "result_count", default=5))
        market = _get_request_value(request_data, "market_type", "market")
        quotes = _run_yfinance_search(query=query, count=count)

        rows: list[dict[str, object]] = []
        for quote in quotes:
            normalized = _normalize_yfinance_search_quote(quote)
            if normalized is None:
                continue
            if not _yfinance_search_row_matches_market(normalized, market):
                continue
            ensure_mapping_has_required_fields(normalized, SEARCH_RESULTS_CONTRACT)
            rows.append(normalized)

        return build_standard_result(
            SEARCH_RESULTS_CONTRACT,
            rows[:count],
            raw_payload=quotes,
            metadata={"backend": BackendName.YFINANCE.value},
        )


class YfinanceHistoryHandler(CapabilityHandler):
    """`yfinance` 的历史行情能力实现。"""

    def __init__(self, capability_name: str) -> None:
        self.capability_name = capability_name

    def execute(self, request_data: dict[str, object]):
        symbols = _resolve_yfinance_history_symbols(self.capability_name, request_data)
        if len(symbols) != 1:
            raise ValueError(f"yfinance {self.capability_name} 当前仅支持单标的请求")

        symbol = symbols[0]
        ticker = _build_yfinance_ticker(symbol)
        frame = _run_yfinance_history(
            ticker,
            _build_yfinance_history_kwargs(request_data),
        )
        rows = _standardize_yfinance_history_frame(frame, symbol=symbol)
        return build_standard_result(
            HISTORY_BARS_CONTRACT,
            rows,
            raw_payload=frame,
            metadata={"backend": BackendName.YFINANCE.value},
        )


class YfinanceFundNavHistoryHandler(CapabilityHandler):
    """`yfinance` 的基金净值历史能力实现。"""

    capability_name = "fund.nav.history"

    def execute(self, request_data: dict[str, object]):
        symbol = _normalize_yfinance_symbol(
            str(_get_request_value(request_data, "fund_code", "symbol")),
        )
        ticker = _build_yfinance_ticker(symbol)
        frame = _run_yfinance_history(
            ticker,
            {
                "period": "max",
                "interval": "1d",
                "auto_adjust": False,
                "back_adjust": False,
            },
        )
        rows = _standardize_yfinance_fund_nav_history_frame(frame, symbol=symbol)
        return build_standard_result(
            FUND_NAV_HISTORY_CONTRACT,
            rows,
            raw_payload=frame,
            metadata={"backend": BackendName.YFINANCE.value},
        )


class YfinanceRealtimeHandler(CapabilityHandler):
    """`yfinance` 的最新价与快照能力实现。"""

    def __init__(self, capability_name: str) -> None:
        self.capability_name = capability_name

    def execute(self, request_data: dict[str, object]):
        symbols = _resolve_yfinance_realtime_symbols(self.capability_name, request_data)
        rows = [
            _build_yfinance_realtime_row(self.capability_name, symbol)
            for symbol in symbols
        ]
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
        symbol = _resolve_yfinance_profile_symbol(self.capability_name, request_data)
        ticker = _build_yfinance_ticker(symbol)
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
            "market": _resolve_yfinance_profile_market(symbol, quote_info, metadata),
            "pe": quote_info.get("trailingPE") or quote_info.get("forwardPE"),
            "pb": quote_info.get("priceToBook"),
            "industry": quote_info.get("industry") or quote_info.get("sector"),
            "total_market_value": quote_info.get("marketCap") or fast_info.get("marketCap"),
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
        values = _coerce_symbol_list(_get_request_value(request_data, "fund_codes", "symbol", default=[]))
        if len(values) != 1:
            raise ValueError("yfinance fund.profile 当前仅支持单标的请求")

        symbol = _normalize_yfinance_symbol(values[0])
        ticker = _build_yfinance_ticker(symbol)
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
        count = int(_get_request_value(request_data, "result_count", "count", default=10))
        ticker = _build_yfinance_ticker(symbol)
        news_items = _extract_yfinance_news(ticker)[:count]

        rows: list[dict[str, object]] = []
        for item in news_items:
            normalized = normalize_contract_mapping(
                {
                    "name": item.get("title") or item.get("publisher") or symbol,
                    "symbol": symbol,
                    "code": item.get("publisher"),
                    "provider_name": BackendName.YFINANCE.value,
                },
                PROVIDER_RECORDS_CONTRACT,
            )
            ensure_mapping_has_required_fields(normalized, PROVIDER_RECORDS_CONTRACT)
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


def _standardize_efinance_result(
    command_key: str,
    request_data: dict[str, object],
    result: object,
):
    if command_key == "search.local":
        return _build_search_standard_result(result)
    if command_key in PRICE_HISTORY_COMMAND_KEYS:
        return _build_history_standard_result(command_key, request_data, result)
    if command_key == "fund.nav.history":
        symbol = str(_get_request_value(request_data, "fund_code", "symbol"))
        return _build_fund_nav_history_standard_result(result, symbol)
    if command_key == "fund.nav.history-batch":
        return _build_fund_nav_history_batch_result(result)
    if command_key in REALTIME_COMMAND_KEYS:
        return _build_realtime_standard_result(command_key, request_data, result)
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
        return build_standard_result(SEARCH_RESULTS_CONTRACT, rows, raw_payload=result)
    items = result if isinstance(result, list) else [result]
    for item in items:
        payload = item._asdict() if hasattr(item, "_asdict") else dict(item)
        normalized = normalize_contract_mapping(payload, SEARCH_RESULTS_CONTRACT)
        ensure_mapping_has_required_fields(normalized, SEARCH_RESULTS_CONTRACT)
        rows.append(normalized)
    return build_standard_result(SEARCH_RESULTS_CONTRACT, rows, raw_payload=result)


def _build_history_standard_result(
    command_key: str,
    request_data: dict[str, object],
    result: object,
):
    symbol_key = {
        "stock.price.history": "stock_codes",
        "bond.price.history": "bond_codes",
        "futures.price.history": "quote_ids",
        "quote.price.history": "codes",
    }[command_key]
    symbols = _coerce_symbol_list(request_data.get(symbol_key))
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
    return build_standard_result(
        REALTIME_QUOTES_CONTRACT,
        rows,
        raw_payload=result,
        metadata={"backend": BackendName.EFINANCE.value, "market": market_name},
    )


def _extract_market_name(command_key: str, request_data: dict[str, object]) -> str:
    if command_key == "market.price.live":
        value = request_data.get("fs")
    elif command_key in {"stock.price.live", "stock.price.latest", "stock.price.snapshot"}:
        value = request_data.get("fs")
    else:
        value = request_data.get("market_type")
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


def _extract_market_value(value: object) -> object | None:
    if value in (None, "", (), []):
        return None
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _standardize_profile_payload(
    result: object,
    request_data: dict[str, object],
    *,
    code_key: str | None = None,
) -> object:
    code_key = code_key or _profile_code_key_from_request(request_data)
    codes = _coerce_symbol_list(request_data.get(code_key)) if code_key else []

    if isinstance(result, pd.Series):
        normalized = _normalize_profile_mapping(result.to_dict(), codes[0] if codes else None)
        return normalized

    if isinstance(result, pd.DataFrame) and {"item", "value"}.issubset(result.columns):
        row = {
            str(item): _normalize_scalar(value)
            for item, value in zip(result["item"], result["value"], strict=False)
        }
        return _normalize_profile_mapping(row, codes[0] if codes else None)

    if isinstance(result, pd.DataFrame):
        rows: list[dict[str, object]] = []
        for index, (_, row) in enumerate(result.iterrows()):
            fallback_code = codes[index] if index < len(codes) else None
            rows.append(_normalize_profile_mapping(row.to_dict(), fallback_code))
        return rows

    if isinstance(result, dict):
        return _normalize_profile_mapping(result, codes[0] if codes else None)

    raise StandardizationError(f"Unsupported profile payload type: {type(result).__name__}")


def _normalize_profile_mapping(row: dict[str, object], fallback_code: str | None) -> dict[str, object]:
    normalized = normalize_contract_mapping(row, PROFILE_INFO_CONTRACT)
    if "code" not in normalized and fallback_code:
        normalized["code"] = fallback_code
    if "quote_id" not in normalized and "code" in normalized:
        normalized["quote_id"] = normalized["code"]
    if "name" not in normalized and fallback_code:
        normalized["name"] = fallback_code
    ensure_mapping_has_required_fields(normalized, PROFILE_INFO_CONTRACT)
    return normalized


def _profile_code_key_from_request(request_data: Mapping[str, object]) -> str | None:
    for key in ("stock_codes", "fund_codes", "bond_codes", "quote_id", "quote_id_list"):
        if key in request_data:
            return key
    return None


def _get_request_value(request_data: Mapping[str, object], *keys: str, default: object = None) -> object:
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


def _coerce_frame_mapping(result: object) -> pd.DataFrame | dict[str, pd.DataFrame]:
    if isinstance(result, pd.DataFrame):
        return result
    if isinstance(result, dict):
        mapping: dict[str, pd.DataFrame] = {}
        for key, value in result.items():
            if isinstance(value, pd.DataFrame):
                mapping[str(key)] = value
            else:
                raise StandardizationError("History payload mapping values must be DataFrame")
        return mapping
    raise StandardizationError(f"Unsupported history payload type: {type(result).__name__}")


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


def _load_akshare_module():
    try:
        return importlib.import_module("akshare")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Akshare backend is unavailable because package 'akshare' is not installed."
        ) from exc


def _load_yfinance_module():
    try:
        return importlib.import_module("yfinance")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "yfinance backend is unavailable because package 'yfinance' is not installed."
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
        invalid_period_error = getattr(exceptions_module, "YFInvalidPeriodError")
        if isinstance(exc, rate_limit_error):
            raise RuntimeError("Yahoo rate limited the request. Please retry later.") from exc
        if isinstance(exc, invalid_period_error):
            raise ValueError(str(exc)) from exc
        raise


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


def _normalize_yfinance_search_quote(quote: Mapping[str, object]) -> dict[str, object] | None:
    symbol = quote.get("symbol")
    if symbol in (None, ""):
        return None
    name = quote.get("shortname") or quote.get("longname") or quote.get("name") or symbol
    classify = quote.get("quoteType") or quote.get("typeDisp") or quote.get("exchange")
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
        return "EQUITY" in classify or "ETF" in classify or "MUTUALFUND" in classify
    if market_name == "A_stock":
        return ".SS" in str(row.get("code", "")) or ".SZ" in str(row.get("code", ""))
    return True


def _build_yfinance_history_kwargs(request_data: Mapping[str, object]) -> dict[str, object]:
    interval = {
        1: "1m",
        5: "5m",
        15: "15m",
        30: "30m",
        60: "60m",
        101: "1d",
        102: "1wk",
        103: "1mo",
    }.get(int(_get_request_value(request_data, "klt", "period", default=101)), "1d")
    auto_adjust = int(_get_request_value(request_data, "fqt", "adjust", default=1)) == 1
    return {
        "start": _normalize_yfinance_date(_get_request_value(request_data, "beg", "start_date", default="19000101")),
        "end": _normalize_yfinance_date(_get_request_value(request_data, "end", "end_date", default="20500101")),
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


def _run_yfinance_history(ticker, kwargs: Mapping[str, object]) -> pd.DataFrame:
    frame = _run_yfinance_with_guardrails(ticker.history, **kwargs)
    if not isinstance(frame, pd.DataFrame):
        raise StandardizationError("yfinance history result is not a DataFrame")
    if isinstance(frame.index, pd.DatetimeIndex):
        frame = frame.reset_index()
    return frame


def _resolve_yfinance_history_symbols(
    command_key: str,
    request_data: Mapping[str, object],
) -> list[str]:
    key_map = {
        "stock.price.history": ("stock_codes", "symbol"),
        "quote.price.history": ("codes", "symbol"),
    }
    keys = key_map[command_key]
    values = _coerce_symbol_list(_get_request_value(request_data, *keys, default=[]))
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
        normalized_frame["date"] = normalized_frame["date"].apply(_normalize_scalar)
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
        payload = {key: _normalize_scalar(value) for key, value in payload.items() if value is not None}
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
        normalized = normalize_contract_mapping(payload, FUND_NAV_HISTORY_CONTRACT)
        ensure_mapping_has_required_fields(normalized, FUND_NAV_HISTORY_CONTRACT)
        normalized_rows.append(normalized)
    return normalized_rows


def _resolve_yfinance_realtime_symbols(
    command_key: str,
    request_data: Mapping[str, object],
) -> list[str]:
    key_map = {
        "quote.price.latest": ("quote_id_list", "symbol"),
        "stock.price.latest": ("stock_codes", "symbol"),
        "stock.price.snapshot": ("stock_code", "symbol"),
    }
    values = _coerce_symbol_list(_get_request_value(request_data, *key_map[command_key], default=[]))
    if command_key in {"stock.price.latest", "stock.price.snapshot"} and len(values) != 1:
        raise ValueError(f"yfinance {command_key} 当前仅支持单标的请求")
    return [_normalize_yfinance_symbol(value) for value in values]


def _extract_yfinance_fast_info(ticker) -> dict[str, object]:
    fast_info = ticker.fast_info
    if hasattr(fast_info, "items"):
        return {str(key): fast_info.get(key) for key in fast_info.keys()}
    return {}


def _extract_yfinance_quote_info(ticker) -> dict[str, object]:
    return _run_yfinance_with_guardrails(lambda: dict(ticker.info or {}))


def _extract_yfinance_history_metadata(ticker) -> dict[str, object]:
    return _run_yfinance_with_guardrails(lambda: dict(ticker.history_metadata or {}))


def _extract_yfinance_funds_data(ticker) -> dict[str, object]:
    funds_data = ticker.funds_data
    return {
        "description": _normalize_scalar(getattr(funds_data, "description", None)),
        "fund_overview": _materialize_provider_payload(getattr(funds_data, "fund_overview", None)),
        "fund_operations": _materialize_provider_payload(getattr(funds_data, "fund_operations", None)),
        "asset_classes": _materialize_provider_payload(getattr(funds_data, "asset_classes", None)),
        "top_holdings": _materialize_provider_payload(getattr(funds_data, "top_holdings", None)),
        "bond_ratings": _materialize_provider_payload(getattr(funds_data, "bond_ratings", None)),
        "sector_weightings": _materialize_provider_payload(getattr(funds_data, "sector_weightings", None)),
    }


def _resolve_yfinance_profile_symbol(
    command_key: str,
    request_data: Mapping[str, object],
) -> str:
    key_map = {
        "stock.profile": ("stock_codes", "symbol"),
        "quote.profile": ("quote_id", "symbol"),
    }
    values = _coerce_symbol_list(_get_request_value(request_data, *key_map[command_key], default=[]))
    if len(values) != 1:
        raise ValueError(f"yfinance {command_key} 当前仅支持单标的请求")
    return _normalize_yfinance_symbol(values[0])


def _resolve_yfinance_profile_market(
    symbol: str,
    quote_info: Mapping[str, object],
    metadata: Mapping[str, object],
) -> str:
    market = quote_info.get("market") or quote_info.get("quoteType") or metadata.get("instrumentType")
    if market in (None, ""):
        if symbol.endswith((".SS", ".SZ")):
            return "A_stock"
        return "US_stock"
    return str(market)


def _build_yfinance_realtime_row(command_key: str, symbol: str) -> dict[str, object]:
    ticker = _build_yfinance_ticker(symbol)
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
        "close": fast_info.get("lastPrice") or metadata.get("regularMarketPrice"),
        "quote_id": symbol,
        "market": _resolve_yfinance_realtime_market(command_key, symbol, quote_info, metadata),
        "open": fast_info.get("open") or metadata.get("regularMarketOpen"),
        "high": fast_info.get("dayHigh") or metadata.get("regularMarketDayHigh"),
        "low": fast_info.get("dayLow") or metadata.get("regularMarketDayLow"),
        "volume": fast_info.get("lastVolume") or metadata.get("regularMarketVolume"),
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
    if symbol.endswith((".SS", ".SZ")):
        return "A_stock"
    return "US_stock"


def _extract_yfinance_news(ticker) -> list[dict[str, object]]:
    return list(_run_yfinance_with_guardrails(lambda: list(ticker.news or [])))


def _materialize_provider_payload(value: object) -> object:
    if isinstance(value, pd.DataFrame):
        return _standardize_generic_payload(value)
    if isinstance(value, pd.Series):
        return _standardize_generic_payload(value)
    if isinstance(value, Mapping):
        return _standardize_generic_payload(dict(value))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
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
    raise StandardizationError(f"Unsupported history payload type: {type(result).__name__}")


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
            "date": _pick_first_present_value(row, ("date", "日期", "时间")),
            "symbol": _pick_first_present_value(row, ("symbol", "股票代码", "债券代码", "期货代码", "代码")) or symbol,
            "open": _pick_first_present_value(row, ("开盘", "open")),
            "close": _pick_first_present_value(row, ("收盘", "最新价", "close")),
            "high": _pick_first_present_value(row, ("最高", "high")),
            "low": _pick_first_present_value(row, ("最低", "low")),
            "volume": _pick_first_present_value(row, ("成交量", "volume")),
            "turnover": _pick_first_present_value(row, ("成交额", "turnover")),
            "amplitude": _pick_first_present_value(row, ("振幅", "amplitude")),
            "change_pct": _pick_first_present_value(row, ("涨跌幅", "change_pct")),
            "change_amount": _pick_first_present_value(row, ("涨跌额", "change_amount")),
            "turnover_rate": _pick_first_present_value(row, ("换手率", "turnover_rate")),
        }
        item = {key: _normalize_scalar(value) for key, value in item.items() if value is not None}
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
            "date": _pick_first_present_value(row, ("date", "日期", "净值日期", "时间")),
            "symbol": _pick_first_present_value(row, ("symbol", "基金代码", "代码")) or symbol,
            "unit_nav": _pick_first_present_value(row, ("unit_nav", "单位净值")),
            "accumulated_nav": _pick_first_present_value(row, ("accumulated_nav", "累计净值")),
            "change_pct": _pick_first_present_value(row, ("change_pct", "涨跌幅", "日增长率")),
        }
        item = {key: _normalize_scalar(value) for key, value in item.items() if value is not None}
        normalized = normalize_contract_mapping(item, FUND_NAV_HISTORY_CONTRACT)
        if "symbol" not in normalized:
            normalized["symbol"] = symbol
        ensure_mapping_has_required_fields(normalized, FUND_NAV_HISTORY_CONTRACT)
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
            "symbol": _pick_first_present_value(
                row,
                ("symbol", "代码", "股票代码", "债券代码", "期货代码", "证券代码"),
            ),
            "name": _pick_first_present_value(
                row,
                ("name", "名称", "股票名称", "债券名称", "期货名称", "证券简称"),
            ),
            "close": _pick_first_present_value(row, ("close", "最新价", "收盘")),
            "quote_id": _pick_first_present_value(
                row,
                ("quote_id", "行情ID", "symbol", "代码", "股票代码", "债券代码", "期货代码", "证券代码"),
            ),
            "market": _pick_first_present_value(row, ("market", "市场", "市场类型")) or market_name,
            "open": _pick_first_present_value(row, ("open", "今开", "开盘")),
            "high": _pick_first_present_value(row, ("high", "最高")),
            "low": _pick_first_present_value(row, ("low", "最低")),
            "volume": _pick_first_present_value(row, ("volume", "成交量")),
            "turnover": _pick_first_present_value(row, ("turnover", "成交额")),
            "change_pct": _pick_first_present_value(row, ("change_pct", "涨跌幅")),
            "change_amount": _pick_first_present_value(row, ("change_amount", "涨跌额")),
            "turnover_rate": _pick_first_present_value(row, ("turnover_rate", "换手率")),
            "amplitude": _pick_first_present_value(row, ("amplitude", "振幅")),
            "date": _pick_first_present_value(row, ("date", "日期", "时间")),
        }
        item = {key: _normalize_scalar(value) for key, value in item.items() if value is not None}
        normalized = normalize_contract_mapping(item, REALTIME_QUOTES_CONTRACT)
        if "market" not in normalized:
            normalized["market"] = market_name
        if "quote_id" not in normalized and "symbol" in normalized:
            normalized["quote_id"] = normalized["symbol"]
        ensure_mapping_has_required_fields(normalized, REALTIME_QUOTES_CONTRACT)
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
            "change_pct": _pick_first_present_value(row, ("change_pct", "涨跌幅")),
            "provider_name": provider_name,
        }
        item = {key: _normalize_scalar(value) for key, value in item.items() if value is not None}
        normalized = normalize_contract_mapping(item, PROVIDER_RECORDS_CONTRACT)
        ensure_mapping_has_required_fields(normalized, PROVIDER_RECORDS_CONTRACT)
        rows.append(normalized)
    return rows


def _standardize_generic_payload(result: object) -> object:
    if isinstance(result, pd.DataFrame):
        return [
            {str(key): _normalize_scalar(value) for key, value in row.items()}
            for row in result.to_dict(orient="records")
        ]
    if isinstance(result, pd.Series):
        return {str(key): _normalize_scalar(value) for key, value in result.to_dict().items()}
    if isinstance(result, Mapping):
        return {str(key): _standardize_generic_payload(value) for key, value in result.items()}
    if isinstance(result, Sequence) and not isinstance(result, (str, bytes, bytearray)):
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


def _pick_first_present_value(row: pd.Series, candidates: tuple[str, ...]) -> object | None:
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
        if any(lowered in candidate.lower() for candidate in candidates if candidate and candidate != "None"):
            filtered.append(row)
    return filtered


def _deduplicate_search_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    deduplicated: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row.get("code", "")), str(row.get("classify", "")))
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(row)
    return deduplicated


def build_efinance_provider() -> BackendProvider:
    handlers: dict[str, CapabilityHandler] = {}
    for definition in SHARED_COMMANDS:
        if BackendName.EFINANCE not in definition.supported_backends:
            continue
        if definition.command_key == "instrument.search":
            handlers[definition.capability] = EfinanceSearchHandler()
        else:
            handlers[definition.capability] = EfinanceGenericHandler(definition.capability)

    extension_commands = get_single_backend_command_definitions(BackendName.EFINANCE)
    for definition in extension_commands:
        handlers[definition.capability] = EfinanceGenericHandler(definition.capability)

    return BackendProvider(
        backend_name=BackendName.EFINANCE,
        handlers=handlers,
        extension_commands=extension_commands,
    )


def build_akshare_provider() -> BackendProvider:
    return BackendProvider(
        backend_name=BackendName.AKSHARE,
        handlers={
            "akshare.industry.boards": AkshareIndustryBoardsHandler(),
            "stock.price.live": AkshareStockPriceLiveHandler(),
            "fund.nav.history": AkshareFundNavHistoryHandler(),
            "stock.profile": AkshareStockProfileHandler(),
            "stock.price.history": AkshareStockPriceHistoryHandler(),
            "instrument.search": AkshareSearchHandler(),
        },
        extension_commands=(
            CommandDefinition(
                command_key="akshare.industry.boards",
                cli_path=("stock", "industry", "boards"),
                capability="akshare.industry.boards",
                request_schema=RequestSchema(
                    schema_name="akshare-industry-boards-request",
                    fields=(),
                ),
                help_text="获取行业板块列表（akshare 专属扩展）。",
                kind=CommandKind.PROVIDER_EXTENSION,
                supported_backends=(BackendName.AKSHARE,),
                allow_watch=True,
                has_side_effect=False,
                provider_name=BackendName.AKSHARE,
            ),
        ),
    )


def build_yfinance_provider() -> BackendProvider:
    handlers: dict[str, CapabilityHandler] = {
        "instrument.search": YfinanceSearchHandler(),
        "stock.price.history": YfinanceHistoryHandler("stock.price.history"),
        "quote.price.history": YfinanceHistoryHandler("quote.price.history"),
        "stock.price.latest": YfinanceRealtimeHandler("stock.price.latest"),
        "stock.price.snapshot": YfinanceRealtimeHandler("stock.price.snapshot"),
        "quote.price.latest": YfinanceRealtimeHandler("quote.price.latest"),
        "stock.profile": YfinanceProfileHandler("stock.profile"),
        "quote.profile": YfinanceProfileHandler("quote.profile"),
        "fund.nav.history": YfinanceFundNavHistoryHandler(),
        "fund.profile": YfinanceFundProfileHandler(),
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
    )
