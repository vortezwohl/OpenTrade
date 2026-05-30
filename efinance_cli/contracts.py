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


SEARCH_RESULTS_CONTRACT = ResultContract(
    contract_name="search-results",
    required_fields=("code", "name"),
    optional_fields=("pinyin", "quote_id", "classify"),
)

HISTORY_BARS_CONTRACT = ResultContract(
    contract_name="history-bars",
    required_fields=("date", "symbol", "open", "close", "high", "low"),
    optional_fields=("volume", "turnover", "amplitude", "change_pct", "change_amount", "turnover_rate"),
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
