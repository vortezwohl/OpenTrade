"""内建 provider 的骨架实现。

当前模块先承载首批共享能力的双后端适配：

- `instrument.search`
- `equity.price.history`

每个 handler 只负责单个 capability，把 provider 原始返回值收敛到共享结果契约。
"""

from __future__ import annotations

import importlib

import efinance
import pandas as pd

from efinance_cli.backends.base import BackendProvider, CapabilityHandler
from efinance_cli.contracts import (
    FUND_NAV_HISTORY_CONTRACT,
    HISTORY_BARS_CONTRACT,
    PROFILE_INFO_CONTRACT,
    REALTIME_QUOTES_CONTRACT,
    SEARCH_RESULTS_CONTRACT,
    StandardizationError,
    build_standard_result,
    ensure_mapping_has_required_fields,
    normalize_contract_mapping,
)
from efinance_cli.models import BackendName
from efinance_cli.retry_utils import call_with_network_retry


class EfinanceSearchHandler(CapabilityHandler):
    """`efinance` 的搜索能力骨架实现。"""

    capability_name = "instrument.search"

    def execute(self, request_data: dict[str, object]):
        market_type = None
        market_name = request_data.get("market")
        if isinstance(market_name, str) and market_name:
            market_type = getattr(efinance.utils.MarketType, market_name, None)
            if market_type is None:
                raise ValueError(f"Unknown market enum: {market_name}")

        result = call_with_network_retry(
            efinance.utils.search_quote,
            keyword=request_data["query"],
            market_type=market_type,
            count=request_data["result_count"],
            use_local=request_data["use_local_cache"],
        )
        rows: list[dict[str, object]] = []
        if result is None:
            return build_standard_result(SEARCH_RESULTS_CONTRACT, rows, raw_payload=result)
        if isinstance(result, list):
            rows = [item._asdict() for item in result]
        else:
            rows = [result._asdict()]
        rows = [normalize_contract_mapping(row, SEARCH_RESULTS_CONTRACT) for row in rows]
        for row in rows:
            ensure_mapping_has_required_fields(row, SEARCH_RESULTS_CONTRACT)
        return build_standard_result(SEARCH_RESULTS_CONTRACT, rows, raw_payload=result)


class EfinanceEquityPriceHistoryHandler(CapabilityHandler):
    """`efinance` 的权益类历史行情能力实现。"""

    capability_name = "equity.price.history"

    def execute(self, request_data: dict[str, object]):
        market_type = _resolve_efinance_market_type(request_data.get("market"))
        period_map = {
            "daily": 101,
            "weekly": 102,
            "monthly": 103,
        }
        adjust_map = {
            "qfq": 1,
            "hfq": 2,
            "none": 0,
        }
        period = str(request_data["period"])
        adjust = str(request_data["adjust"])
        result = call_with_network_retry(
            efinance.stock.get_quote_history,
            request_data["symbol"],
            beg=request_data["start_date"],
            end=request_data["end_date"],
            klt=period_map[period],
            fqt=adjust_map[adjust],
            market_type=market_type,
        )
        frame = _coerce_history_frame(result)
        rows = _standardize_history_frame(
            frame,
            symbol=str(request_data["symbol"]),
            provider_name=BackendName.EFINANCE.value,
        )
        return build_standard_result(
            HISTORY_BARS_CONTRACT,
            rows,
            raw_payload=result,
            metadata={
                "symbol": request_data["symbol"],
                "period": period,
                "adjust": adjust,
                "backend": BackendName.EFINANCE.value,
            },
        )


class EfinanceEquityProfileHandler(CapabilityHandler):
    """`efinance` 的权益类资料能力实现。"""

    capability_name = "equity.profile"

    def execute(self, request_data: dict[str, object]):
        result = call_with_network_retry(
            efinance.stock.get_base_info,
            str(request_data["symbol"]),
        )
        row = _coerce_profile_row(result)
        normalized = normalize_contract_mapping(row, PROFILE_INFO_CONTRACT)
        if "code" not in normalized:
            normalized["code"] = str(request_data["symbol"])
        ensure_mapping_has_required_fields(normalized, PROFILE_INFO_CONTRACT)
        return build_standard_result(
            PROFILE_INFO_CONTRACT,
            normalized,
            raw_payload=result,
            metadata={
                "symbol": request_data["symbol"],
                "market": request_data.get("market"),
                "backend": BackendName.EFINANCE.value,
            },
        )


class EfinanceFundNavHistoryHandler(CapabilityHandler):
    """`efinance` 的基金净值历史能力实现。"""

    capability_name = "fund.nav.history"

    def execute(self, request_data: dict[str, object]):
        result = call_with_network_retry(
            efinance.fund.get_quote_history,
            str(request_data["symbol"]),
        )
        frame = _coerce_history_frame(result)
        rows = _standardize_fund_nav_history_frame(
            frame,
            symbol=str(request_data["symbol"]),
        )
        limit = request_data.get("record_limit")
        if isinstance(limit, int) and limit > 0:
            rows = rows[:limit]
        return build_standard_result(
            FUND_NAV_HISTORY_CONTRACT,
            rows,
            raw_payload=result,
            metadata={
                "symbol": request_data["symbol"],
                "backend": BackendName.EFINANCE.value,
            },
        )


class EfinanceEquityPriceLiveHandler(CapabilityHandler):
    """`efinance` 的权益实时列表能力实现。"""

    capability_name = "equity.price.live"

    def execute(self, request_data: dict[str, object]):
        market = request_data.get("market")
        if market not in (None, "", "A_stock"):
            raise ValueError("Efinance equity.price.live 当前仅支持 A_stock 市场")

        result = call_with_network_retry(efinance.stock.get_realtime_quotes)
        frame = _coerce_history_frame(result)
        rows = _standardize_realtime_quotes_frame(
            frame,
            market_name="A_stock",
            provider_name=BackendName.EFINANCE.value,
        )
        limit = request_data.get("record_limit")
        if isinstance(limit, int) and limit > 0:
            rows = rows[:limit]
        return build_standard_result(
            REALTIME_QUOTES_CONTRACT,
            rows,
            raw_payload=result,
            metadata={
                "market": "A_stock",
                "backend": BackendName.EFINANCE.value,
            },
        )


class UnsupportedSearchHandler(CapabilityHandler):
    """表示 provider 骨架已注册，但能力尚未实现。"""

    capability_name = "instrument.search"

    def __init__(self, backend_name: BackendName) -> None:
        self.backend_name = backend_name

    def execute(self, request_data: dict[str, object]):
        raise NotImplementedError(
            f"Backend '{self.backend_name.value}' 的 capability '{self.capability_name}' 尚未实现"
        )


class AkshareSearchHandler(CapabilityHandler):
    """`akshare` 的搜索能力实现。

    当前实现优先聚合可独立调用的股票与基金名录接口：

    - 上交所 A 股列表；
    - 深交所 A 股列表；
    - 天天基金基金名录；
    - 美股名录（若 provider 环境可用）。

    设计原则：
    - 每个名录源独立加载，单路失败不拖垮整次搜索；
    - 若全部来源都失败，则显式报错；
    - 返回值仍收敛到共享搜索结果契约。
    """

    capability_name = "instrument.search"

    def execute(self, request_data: dict[str, object]):
        akshare = _load_akshare_module()
        market = request_data.get("market")
        query = str(request_data["query"]).strip()
        result_count = int(request_data["result_count"])

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
        """根据 market 约束构造名录加载器列表。"""

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
        """把 akshare 名录 DataFrame 转为共享搜索结果结构。"""

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
        """仅在满足搜索契约核心字段时追加记录。"""

        try:
            normalized = normalize_contract_mapping(item, SEARCH_RESULTS_CONTRACT)
            ensure_mapping_has_required_fields(normalized, SEARCH_RESULTS_CONTRACT)
        except StandardizationError:
            return
        rows.append(normalized)


class AkshareEquityPriceHistoryHandler(CapabilityHandler):
    """`akshare` 的权益类历史行情能力实现。"""

    capability_name = "equity.price.history"

    def execute(self, request_data: dict[str, object]):
        akshare = _load_akshare_module()
        market = request_data.get("market")
        if market not in (None, "", "A_stock"):
            raise ValueError("Akshare equity.price.history 当前仅支持 A_stock 市场")

        adjust = "" if request_data["adjust"] == "none" else str(request_data["adjust"])
        frame = akshare.stock_zh_a_hist(
            symbol=str(request_data["symbol"]),
            period=str(request_data["period"]),
            start_date=str(request_data["start_date"]),
            end_date=str(request_data["end_date"]),
            adjust=adjust,
        )
        rows = _standardize_history_frame(
            frame,
            symbol=str(request_data["symbol"]),
            provider_name=BackendName.AKSHARE.value,
        )
        return build_standard_result(
            HISTORY_BARS_CONTRACT,
            rows,
            raw_payload=frame,
            metadata={
                "symbol": request_data["symbol"],
                "period": request_data["period"],
                "adjust": request_data["adjust"],
                "backend": BackendName.AKSHARE.value,
            },
        )


class AkshareEquityProfileHandler(CapabilityHandler):
    """`akshare` 的权益类资料能力实现。"""

    capability_name = "equity.profile"

    def execute(self, request_data: dict[str, object]):
        market = request_data.get("market")
        if market not in (None, "", "A_stock"):
            raise ValueError("Akshare equity.profile 当前仅支持 A_stock 市场")

        akshare = _load_akshare_module()
        result = akshare.stock_individual_info_em(symbol=str(request_data["symbol"]))
        row = _coerce_profile_row(result)
        normalized = normalize_contract_mapping(row, PROFILE_INFO_CONTRACT)
        if "code" not in normalized:
            normalized["code"] = str(request_data["symbol"])
        ensure_mapping_has_required_fields(normalized, PROFILE_INFO_CONTRACT)
        return build_standard_result(
            PROFILE_INFO_CONTRACT,
            normalized,
            raw_payload=result,
            metadata={
                "symbol": request_data["symbol"],
                "market": request_data.get("market"),
                "backend": BackendName.AKSHARE.value,
            },
        )


class AkshareFundNavHistoryHandler(CapabilityHandler):
    """`akshare` 的基金净值历史能力实现。"""

    capability_name = "fund.nav.history"

    def execute(self, request_data: dict[str, object]):
        akshare = _load_akshare_module()
        result = akshare.fund_open_fund_info_em(
            symbol=str(request_data["symbol"]),
            indicator="单位净值走势",
        )
        frame = _coerce_history_frame(result)
        rows = _standardize_fund_nav_history_frame(
            frame,
            symbol=str(request_data["symbol"]),
        )
        limit = request_data.get("record_limit")
        if isinstance(limit, int) and limit > 0:
            rows = rows[:limit]
        return build_standard_result(
            FUND_NAV_HISTORY_CONTRACT,
            rows,
            raw_payload=result,
            metadata={
                "symbol": request_data["symbol"],
                "backend": BackendName.AKSHARE.value,
            },
        )


class AkshareEquityPriceLiveHandler(CapabilityHandler):
    """`akshare` 的权益实时列表能力实现。"""

    capability_name = "equity.price.live"

    def execute(self, request_data: dict[str, object]):
        market = request_data.get("market")
        if market not in (None, "", "A_stock"):
            raise ValueError("Akshare equity.price.live 当前仅支持 A_stock 市场")

        akshare = _load_akshare_module()
        result = akshare.stock_zh_a_spot_em()
        frame = _coerce_history_frame(result)
        rows = _standardize_realtime_quotes_frame(
            frame,
            market_name="A_stock",
            provider_name=BackendName.AKSHARE.value,
        )
        limit = request_data.get("record_limit")
        if isinstance(limit, int) and limit > 0:
            rows = rows[:limit]
        return build_standard_result(
            REALTIME_QUOTES_CONTRACT,
            rows,
            raw_payload=result,
            metadata={
                "market": "A_stock",
                "backend": BackendName.AKSHARE.value,
            },
        )


def _load_akshare_module():
    """惰性加载 `akshare`，避免未安装时在导入阶段直接失败。"""

    try:
        return importlib.import_module("akshare")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Akshare backend is unavailable because package 'akshare' is not installed."
        ) from exc


def _resolve_efinance_market_type(market_name: object):
    """把共享 market 参数解析为 `efinance` 的市场枚举。"""

    if market_name in (None, ""):
        return None
    if not isinstance(market_name, str):
        raise ValueError(f"Unknown market enum: {market_name}")
    market_type = getattr(efinance.utils.MarketType, market_name, None)
    if market_type is None:
        raise ValueError(f"Unknown market enum: {market_name}")
    return market_type


def _coerce_history_frame(result: object) -> pd.DataFrame:
    """把 provider 历史结果收敛为单个 DataFrame。"""

    if isinstance(result, pd.DataFrame):
        return result
    if isinstance(result, dict):
        if len(result) != 1:
            raise StandardizationError("History capability 仅支持单标的结果")
        only_value = next(iter(result.values()))
        if isinstance(only_value, pd.DataFrame):
            return only_value
    raise StandardizationError(f"Unsupported history payload type: {type(result).__name__}")


def _coerce_profile_row(result: object) -> dict[str, object]:
    """把 provider 资料结果收敛为单行映射。"""

    if isinstance(result, pd.Series):
        return result.to_dict()
    if isinstance(result, pd.DataFrame):
        if result.empty:
            return {}
        if {"item", "value"}.issubset(result.columns):
            return {
                str(item): _normalize_scalar(value)
                for item, value in zip(result["item"], result["value"], strict=False)
            }
        return result.iloc[0].to_dict()
    if isinstance(result, dict):
        return result
    raise StandardizationError(f"Unsupported profile payload type: {type(result).__name__}")


def _standardize_history_frame(
    frame: pd.DataFrame,
    *,
    symbol: str,
    provider_name: str,
) -> list[dict[str, object]]:
    """把历史 DataFrame 标准化为共享历史契约。"""

    if frame is None or frame.empty:
        return []

    rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        item = {
            "date": _pick_first_present_value(row, ("日期", "时间")),
            "symbol": _pick_first_present_value(row, ("股票代码", "代码")) or symbol,
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
        rows.append(normalized)
    return rows


def _standardize_fund_nav_history_frame(
    frame: pd.DataFrame,
    *,
    symbol: str,
) -> list[dict[str, object]]:
    """把基金净值历史 DataFrame 标准化为共享基金净值契约。"""

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
    """把实时行情列表标准化为共享实时契约。"""

    if frame is None or frame.empty:
        return []

    rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        item = {
            "symbol": _pick_first_present_value(row, ("symbol", "代码", "股票代码", "证券代码")),
            "name": _pick_first_present_value(row, ("name", "名称", "股票名称", "证券简称")),
            "close": _pick_first_present_value(row, ("close", "最新价", "收盘")),
            "quote_id": _pick_first_present_value(row, ("quote_id", "行情ID", "symbol", "代码", "股票代码", "证券代码")),
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


def _pick_first_present_value(row: pd.Series, candidates: tuple[str, ...]) -> object | None:
    """从候选列名里提取第一个非空值。"""

    for candidate in candidates:
        if candidate in row.index and pd.notna(row[candidate]):
            return row[candidate]
    return None


def _normalize_scalar(value: object) -> object:
    """把 provider 原始标量标准化为基础 Python 类型。"""

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
    """按 query 对候选结果做大小写无关的模糊过滤。"""

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
    """按 code + classify 去重，保留首个命中的结果。"""

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
    """构造 `efinance` provider。"""

    return BackendProvider(
        backend_name=BackendName.EFINANCE,
        handlers={
            "equity.price.live": EfinanceEquityPriceLiveHandler(),
            "fund.nav.history": EfinanceFundNavHistoryHandler(),
            "equity.profile": EfinanceEquityProfileHandler(),
            "equity.price.history": EfinanceEquityPriceHistoryHandler(),
            "instrument.search": EfinanceSearchHandler(),
        },
    )


def build_akshare_provider() -> BackendProvider:
    """构造 `akshare` provider。

    当前阶段先实现共享搜索能力，其余能力后续逐步迁移。
    """

    return BackendProvider(
        backend_name=BackendName.AKSHARE,
        handlers={
            "equity.price.live": AkshareEquityPriceLiveHandler(),
            "fund.nav.history": AkshareFundNavHistoryHandler(),
            "equity.profile": AkshareEquityProfileHandler(),
            "equity.price.history": AkshareEquityPriceHistoryHandler(),
            "instrument.search": AkshareSearchHandler(),
        },
    )
