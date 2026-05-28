"""基金基础信息的本地兼容层。

该模块只处理 `efinance.fund.get_base_info` 在 `pandas>=3` 环境下的兼容问题。
上游实现会先构造字符串 dtype 的 `Series`，再通过装饰器原地写回浮点数，最终触发
`TypeError: Invalid value ... for dtype 'str'`。这里复用相同接口与数据源，但改为在
本地显式构造 `object` dtype 的结果，避免字符串列原地写回数值。
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import rich

from efinance.fund.config import EastmoneyFundHeaders
from efinance.fund.getter import fund_session
from efinance_cli.retry_utils import with_network_retry


_BASE_INFO_COLUMNS: dict[str, str] = {
    "FCODE": "基金代码",
    "SHORTNAME": "基金简称",
    "ESTABDATE": "成立日期",
    "RZDF": "涨跌幅",
    "DWJZ": "最新净值",
    "JJGS": "基金公司",
    "FSRQ": "净值更新日期",
    "COMMENTS": "简介",
}

_NUMERIC_FIELDS = {"涨跌幅", "最新净值"}


def _clean_text(value: Any) -> Any:
    """清洗接口返回的字符串值。

    Args:
        value: 东方财富接口返回的原始字段值。

    Returns:
        清洗后的字段值。非字符串原样返回，字符串会去除换行和首尾空白。
    """

    if not isinstance(value, str):
        return value
    return value.replace("\n", " ").strip()


def _convert_numeric_value(field_name: str, value: Any) -> Any:
    """按字段语义把可转数值的字符串转换为数值。

    Args:
        field_name: 当前字段的中文名。
        value: 清洗后的字段值。

    Returns:
        当字段允许数值化且值可解析时，返回 `float` 或 `int`；否则返回原值。
    """

    if field_name not in _NUMERIC_FIELDS:
        return value
    if not isinstance(value, str):
        return value
    if value in {"", "--"}:
        return value
    try:
        if value.isalnum():
            return int(value)
        return float(value)
    except ValueError:
        return value


def _build_base_info_series(items: dict[str, Any]) -> pd.Series:
    """把接口载荷构造成兼容 `pandas>=3` 的基金基础信息序列。

    Args:
        items: 东方财富接口 `Datas` 字段中的原始字典。

    Returns:
        采用 `object` dtype 构造的基金基础信息 `Series`。
    """

    cleaned: dict[str, Any] = {}
    for source_name, target_name in _BASE_INFO_COLUMNS.items():
        value = _clean_text(items.get(source_name))
        cleaned[target_name] = _convert_numeric_value(target_name, value)
    return pd.Series(cleaned, dtype="object")


@with_network_retry
def _fetch_base_info_payload(fund_code: str) -> dict[str, Any]:
    """请求单只基金的基础信息载荷。

    Args:
        fund_code: 6 位基金代码。

    Returns:
        东方财富接口返回的 JSON 字典。
    """

    params = (
        ("FCODE", fund_code),
        ("deviceid", "3EA024C2-7F22-408B-95E4-383D38160FB3"),
        ("plat", "Iphone"),
        ("product", "EFund"),
        ("version", "6.3.8"),
    )
    url = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNNBasicInformation"
    return fund_session.get(
        url,
        headers=EastmoneyFundHeaders,
        params=params,
    ).json()


def get_base_info_single(fund_code: str) -> pd.Series:
    """获取单只基金的基础信息。

    Args:
        fund_code: 6 位基金代码。

    Returns:
        基金基础信息 `Series`。当基金代码无效时，返回预定义列的空 `Series`。
    """

    json_response = _fetch_base_info_payload(fund_code)
    items = json_response.get("Datas") or {}
    if not items:
        rich.print("Fund code", fund_code, "may be invalid")
        return pd.Series(index=_BASE_INFO_COLUMNS.values(), dtype="object")
    return _build_base_info_series(items)


def get_base_info(fund_codes: str | list[str]) -> pd.Series | pd.DataFrame:
    """获取单只或多只基金的基础信息。

    该函数保持与 `efinance.fund.get_base_info` 相同的命名和返回约定，同时兼容
    CLI 把单个输入解析成单元素列表的情况。

    Args:
        fund_codes: 单个基金代码，或由多个基金代码组成的列表。

    Returns:
        单只基金时返回 `Series`，多只基金时返回 `DataFrame`。

    Raises:
        TypeError: 当入参既不是字符串，也不是可迭代基金代码集合时抛出。
    """

    if isinstance(fund_codes, str):
        return get_base_info_single(fund_codes)
    if not hasattr(fund_codes, "__iter__"):
        raise TypeError(f"Unsupported fund_codes argument: {fund_codes}")

    normalized_codes = [str(code) for code in fund_codes]
    if not normalized_codes:
        return pd.DataFrame(columns=_BASE_INFO_COLUMNS.values())
    if len(normalized_codes) == 1:
        return get_base_info_single(normalized_codes[0])

    rows = [get_base_info_single(code).to_dict() for code in normalized_codes]
    return pd.DataFrame(rows)
