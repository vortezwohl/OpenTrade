"""标准结果契约模型。

该模块先定义首批共享能力需要的契约骨架，重点是把“核心字段、可选字段、原始字段、
扩展字段”四件事显式化。当前阶段覆盖：

- 搜索结果契约；
- 历史行情契约。

后续资料信息和实时行情契约继续沿同一路径扩展。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from efinance_cli.models import StandardResult


class StandardizationError(RuntimeError):
    """表示 provider 返回值无法满足共享能力的标准契约。"""


@dataclass(slots=True)
class ResultContract:
    """描述某类标准结果契约。

    Args:
        contract_name: 契约名。
        required_fields: 共享核心字段。
        optional_fields: 可选字段。
    """

    contract_name: str
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...] = field(default_factory=tuple)
    field_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)


SEARCH_RESULTS_CONTRACT = ResultContract(
    contract_name="search-results",
    required_fields=("code", "name"),
    optional_fields=("pinyin", "quote_id", "classify"),
    field_aliases={
        "code": ("code", "symbol", "证券代码", "A股代码", "基金代码"),
        "name": ("name", "cname", "证券简称", "A股简称", "基金简称"),
        "pinyin": ("pinyin", "name"),
        "quote_id": ("quote_id", "symbol", "code", "证券代码", "A股代码", "基金代码"),
        "classify": ("classify", "基金类型"),
    },
)

PROFILE_INFO_CONTRACT = ResultContract(
    contract_name="profile-info",
    required_fields=("code", "name"),
    optional_fields=("quote_id", "market", "pe", "pb", "industry", "total_market_value"),
    field_aliases={
        "code": ("code", "symbol", "股票代码", "代码", "证券代码", "quote_id"),
        "name": ("name", "股票名称", "名称", "证券简称", "cname"),
        "quote_id": ("quote_id", "行情ID", "quote_id", "symbol", "代码", "证券代码"),
        "market": ("market", "市场", "市场类型"),
        "pe": ("pe", "市盈率(动)", "市盈率", "PE"),
        "pb": ("pb", "市净率", "PB"),
        "industry": ("industry", "所处行业", "行业"),
        "total_market_value": ("total_market_value", "总市值"),
    },
)

HISTORY_BARS_CONTRACT = ResultContract(
    contract_name="history-bars",
    required_fields=("date", "symbol", "open", "close", "high", "low"),
    optional_fields=("volume", "turnover", "amplitude", "change_pct", "change_amount", "turnover_rate"),
    field_aliases={
        "date": ("date", "日期", "时间"),
        "symbol": ("symbol", "股票代码", "代码"),
        "open": ("open", "开盘", "今开", "单位净值"),
        "close": ("close", "收盘", "最新价", "单位净值"),
        "high": ("high", "最高"),
        "low": ("low", "最低"),
        "volume": ("volume", "成交量"),
        "turnover": ("turnover", "成交额"),
        "amplitude": ("amplitude", "振幅"),
        "change_pct": ("change_pct", "涨跌幅"),
        "change_amount": ("change_amount", "涨跌额"),
        "turnover_rate": ("turnover_rate", "换手率"),
    },
)


def ensure_mapping_has_required_fields(
    mapping: dict[str, Any],
    contract: ResultContract,
) -> None:
    """校验单条标准记录是否满足契约要求。"""

    missing = [field for field in contract.required_fields if field not in mapping or mapping[field] in (None, "")]
    if missing:
        joined = ", ".join(missing)
        raise StandardizationError(
            f"Contract '{contract.contract_name}' 缺少关键字段: {joined}"
        )


def build_standard_result(
    contract: ResultContract,
    data: Any,
    raw_payload: Any = None,
    provider_fields: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> StandardResult:
    """构造统一标准结果封装对象。"""

    return StandardResult(
        contract_name=contract.contract_name,
        data=data,
        metadata=metadata or {},
        raw_payload=raw_payload,
        provider_fields=provider_fields or {},
    )


def normalize_contract_mapping(
    mapping: dict[str, Any],
    contract: ResultContract,
) -> dict[str, Any]:
    """按契约别名表把 provider 原始字段归一化为标准字段。"""

    normalized: dict[str, Any] = {}
    target_fields = (*contract.required_fields, *contract.optional_fields)
    for field_name in target_fields:
        aliases = contract.field_aliases.get(field_name, (field_name,))
        for alias in aliases:
            if alias in mapping and mapping[alias] not in (None, ""):
                normalized[field_name] = mapping[alias]
                break
    return normalized
