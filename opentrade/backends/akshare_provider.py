"""Akshare provider 实现。

该模块只承载 akshare backend 的请求适配、handler 与 provider 构建逻辑。 共享契约标准化、通用 request
helper 和跨 backend 工具统一放在 `providers_common.py`。
"""

from __future__ import annotations

import importlib
from typing import Mapping

import pandas as pd

from opentrade.backends.base import (
    BackendProvider,
    CapabilityHandler,
    ProviderContractError,
    ProviderRetryPolicy,
)
from opentrade.command_catalog import CommandDefinition, CommandKind
from opentrade.contracts import build_standard_result
from opentrade.models import RequestSchema
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
    _coerce_history_frame,
    _deduplicate_search_rows,
    _extract_market_value,
    _filter_search_rows,
    _get_request_value,
    _get_single_request_value,
    _standardize_fund_nav_history_frame,
    _standardize_history_frame,
    _standardize_profile_payload,
    _standardize_provider_records_frame,
    _standardize_realtime_quotes_frame,
    ensure_mapping_has_required_fields,
    normalize_contract_mapping,
)


def _adapt_akshare_search_request(
    request_data: Mapping[str, object]
) -> dict[str, object]:
    """把 shared 搜索请求翻译为 akshare 搜索所需参数。"""
    return {
        "market":
        _get_request_value(request_data, "market", "market_type"),
        "query":
        str(_get_request_value(request_data, "keyword", "query")).strip(),
        "result_count":
        int(
            _get_request_value(
                request_data, "result_count", "count", default=5
            )
        ),
    }


def _adapt_akshare_stock_history_request(
    request_data: Mapping[str, object]
) -> dict[str, object]:
    """把 shared 历史行情请求翻译为 akshare `stock_zh_a_hist` 参数。"""
    market = _extract_market_value(
        _get_request_value(request_data, "market", "market_type")
    )
    if market not in (None, "", "A_stock"):
        raise ValueError("Akshare stock.price.history 当前仅支持 A_stock 市场")

    adjust_map = {0: "", 1: "qfq", 2: "hfq"}
    period_map = {101: "daily", 102: "weekly", 103: "monthly"}
    symbol = _get_single_request_value(
        request_data,
        "stock.price.history",
        "symbol",
        "symbols",
        "stock_codes",
    )
    return {
        "symbol":
        symbol,
        "period":
        period_map[int(
            _get_request_value(
                request_data, "timeframe", "klt", "period", default=101
            )
        )],
        "start_date":
        str(
            _get_request_value(
                request_data, "start_date", "beg", default="19000101"
            )
        ),
        "end_date":
        str(
            _get_request_value(
                request_data, "end_date", "end", default="20500101"
            )
        ),
        "adjust":
        adjust_map[int(
            _get_request_value(
                request_data, "adjustment", "fqt", "adjust", default=1
            )
        )],
    }


def _adapt_akshare_stock_profile_request(
    request_data: Mapping[str, object]
) -> dict[str, object]:
    """把 shared 资料请求翻译为 akshare `stock_individual_info_em` 参数。"""
    market = _extract_market_value(
        _get_request_value(request_data, "market", "market_type")
    )
    if market not in (None, "", "A_stock"):
        raise ValueError("Akshare stock.profile 当前仅支持 A_stock 市场")

    return {
        "symbol":
        _get_single_request_value(
            request_data,
            "stock.profile",
            "symbol",
            "symbols",
            "stock_codes",
        ),
    }


def _adapt_akshare_stock_live_request(
    request_data: Mapping[str, object]
) -> dict[str, object]:
    """把 shared 实时行情请求翻译为 akshare 市场过滤。"""
    market = _extract_market_value(
        _get_request_value(request_data, "market", "market_type", "fs")
    )
    if market in (None, ""):
        market = "A_stock"
    if market != "A_stock":
        raise ValueError("Akshare stock.price.live 当前仅支持 A_stock 市场")
    return {"market": market}


def _adapt_akshare_fund_nav_history_request(
    request_data: Mapping[str, object]
) -> dict[str, object]:
    """把 shared 基金净值历史请求翻译为 akshare `fund_open_fund_info_em` 参数。"""
    return {
        "symbol":
        _get_single_request_value(
            request_data,
            "fund.nav.history",
            "symbol",
            "fund_code",
        ),
        "indicator":
        "单位净值走势",
    }


class AkshareSearchHandler(CapabilityHandler):
    """`akshare` 的搜索能力实现。"""

    capability_name = "instrument.search"

    def execute(self, request_data: dict[str, object]):
        akshare = _load_akshare_module()
        adapted_request = _adapt_akshare_search_request(request_data)
        market = adapted_request["market"]
        query = str(adapted_request["query"])
        result_count = int(adapted_request["result_count"])

        loaders = self._build_catalog_loaders(akshare, market)
        rows: list[dict[str, object]] = []
        errors: list[str] = []
        for classify, loader in loaders:
            try:
                frame = loader()
            except NETWORK_RELATED_EXCEPTIONS:
                raise
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
            raw_payload={
                "errors": errors,
                "total_candidates": len(rows)
            },
        )

    @staticmethod
    def _build_catalog_loaders(akshare: object,
                               market: object) -> list[tuple[str, object]]:
        loaders: list[tuple[str, object]] = []
        market_name = str(market) if market not in (None, "") else None
        if market_name in {None, "A_stock"}:
            loaders.extend(
                [
                    (
                        "A_stock",
                        lambda: akshare.stock_info_sh_name_code("主板A股")
                    ),
                    (
                        "A_stock",
                        lambda: akshare.stock_info_sz_name_code("A股列表")
                    ),
                ]
            )
        if market_name is None:
            loaders.append(("fund", akshare.fund_name_em))
        if market_name in {None, "US_stock"} and hasattr(akshare,
                                                         "get_us_stock_name"):
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
                    "name": str(row.get("基金代码", "")).strip(),
                    "pinyin": str(row.get("基金代码", "")).strip() or None,
                    "quote_id": str(row.get("基金代码", "")).strip(),
                    "classify": str(row.get("基金代码", "")).strip() or classify,
                }
                self._append_if_valid(rows, item)
            return rows

        if classify == "US_stock":
            for _, row in frame.iterrows():
                display_name = str(row.get("cname", "")).strip() or str(
                    row.get("name", "")
                ).strip()
                item = {
                    "code": str(row.get("symbol", "")).strip(),
                    "name": display_name,
                    "pinyin": str(row.get("name", "")).strip() or None,
                    "quote_id": str(row.get("symbol", "")).strip(),
                    "classify": classify,
                }
                self._append_if_valid(rows, item)
            return rows

        raise StandardizationError(
            f"Unsupported akshare catalog classify: {classify}"
        )

    @staticmethod
    def _append_if_valid(
        rows: list[dict[str, object]],
        item: dict[str, object],
    ) -> None:
        try:
            normalized = normalize_contract_mapping(
                item, SEARCH_RESULTS_CONTRACT
            )
            ensure_mapping_has_required_fields(
                normalized, SEARCH_RESULTS_CONTRACT
            )
        except StandardizationError:
            return
        rows.append(normalized)


class AkshareStockPriceHistoryHandler(CapabilityHandler):
    """处理 akshare 的 A 股历史行情能力。"""

    capability_name = "stock.price.history"

    def execute(self, request_data: dict[str, object]):
        akshare = _load_akshare_module()
        adapted_request = _adapt_akshare_stock_history_request(request_data)
        frame = akshare.stock_zh_a_hist(**adapted_request)
        rows = _standardize_history_frame(
            frame,
            symbol=str(adapted_request["symbol"]),
            provider_name=BackendName.AKSHARE.value,
        )
        return build_standard_result(
            HISTORY_BARS_CONTRACT,
            rows,
            raw_payload=frame,
            metadata={"backend": BackendName.AKSHARE.value},
        )


class AkshareStockProfileHandler(CapabilityHandler):
    """处理 akshare 的 A 股资料能力。"""

    capability_name = "stock.profile"

    def execute(self, request_data: dict[str, object]):
        adapted_request = _adapt_akshare_stock_profile_request(request_data)
        akshare = _load_akshare_module()
        result = akshare.stock_individual_info_em(**adapted_request)
        data = _standardize_profile_payload(
            result, request_data, code_key="symbol"
        )
        return build_standard_result(
            PROFILE_INFO_CONTRACT,
            data,
            raw_payload=result,
            metadata={"backend": BackendName.AKSHARE.value},
        )


class AkshareStockPriceLiveHandler(CapabilityHandler):
    """处理 akshare 的 A 股实时行情能力。"""

    capability_name = "stock.price.live"

    def execute(self, request_data: dict[str, object]):
        adapted_request = _adapt_akshare_stock_live_request(request_data)
        akshare = _load_akshare_module()
        result = akshare.stock_zh_a_spot_em()
        frame = _coerce_history_frame(result)
        rows = _standardize_realtime_quotes_frame(
            frame,
            market_name=str(adapted_request["market"]),
            provider_name=BackendName.AKSHARE.value,
        )
        return build_standard_result(
            REALTIME_QUOTES_CONTRACT,
            rows,
            raw_payload=result,
            metadata={"backend": BackendName.AKSHARE.value},
        )


class AkshareFundNavHistoryHandler(CapabilityHandler):
    """处理 akshare 的基金净值历史能力。"""

    capability_name = "fund.nav.history"

    def execute(self, request_data: dict[str, object]):
        akshare = _load_akshare_module()
        adapted_request = _adapt_akshare_fund_nav_history_request(request_data)
        result = akshare.fund_open_fund_info_em(**adapted_request)
        frame = _coerce_history_frame(result)
        rows = _standardize_fund_nav_history_frame(
            frame,
            symbol=str(adapted_request["symbol"]),
        )
        return build_standard_result(
            FUND_NAV_HISTORY_CONTRACT,
            rows,
            raw_payload=result,
            metadata={"backend": BackendName.AKSHARE.value},
        )


class AkshareIndustryBoardsHandler(CapabilityHandler):
    """处理 akshare 行业板块扩展命令。"""

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


def _load_akshare_module():
    try:
        return importlib.import_module("akshare")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Akshare backend is unavailable because package "
            "'akshare' is not installed."
        ) from exc


def _build_akshare_retry_policy() -> ProviderRetryPolicy:
    """返回 akshare 的 provider 级统一重试策略。"""
    return ProviderRetryPolicy(
        retryable_exceptions=NETWORK_RELATED_EXCEPTIONS,
        passthrough_exceptions=(ProviderContractError, ),
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
                supported_backends=(BackendName.AKSHARE, ),
                allow_watch=True,
                has_side_effect=False,
                provider_name=BackendName.AKSHARE,
            ),
        ),
        retry_policy=_build_akshare_retry_policy(),
    )
