"""基金基础信息兼容层测试。

这些测试覆盖本项目对 `efinance.fund.get_base_info` 的本地兼容补丁，重点验证：
1. 单只基金在 CLI 传入单元素列表时仍返回 `Series`；
2. 数值字段会被安全转换为数值，不再触发 `pandas>=3` 的字符串 dtype 赋值异常；
3. 注册中心已经把 `fund.get_base_info` 指向本地兼容实现。
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from efinance_cli.fund_compat import get_base_info
from efinance_cli.registry import get_command_spec
from tests.cli_regression_support import print_observation


def build_payload(
    fund_code: str,
    short_name: str,
    increase_rate: str,
    unit_value: str,
) -> dict[str, dict[str, str]]:
    """构造基金基础信息接口的最小模拟载荷。

    Args:
        fund_code: 基金代码。
        short_name: 基金简称。
        increase_rate: 涨跌幅字符串。
        unit_value: 最新净值字符串。

    Returns:
        符合兼容层预期结构的模拟响应。
    """

    return {
        "Datas": {
            "FCODE": fund_code,
            "SHORTNAME": short_name,
            "ESTABDATE": "2020-01-01",
            "RZDF": increase_rate,
            "DWJZ": unit_value,
            "JJGS": "测试基金公司",
            "FSRQ": "2026-05-27",
            "COMMENTS": " 第一行\n第二行 ",
        }
    }


class FundCompatTest(unittest.TestCase):
    """验证基金基础信息兼容层的关键行为。"""

    @patch("efinance_cli.fund_compat._fetch_base_info_payload")
    def test_single_code_list_returns_series(self, mock_fetch: unittest.mock.Mock) -> None:
        """单元素列表输入应返回 `Series`，以兼容 CLI 的 variadic 参数解析。"""

        mock_fetch.return_value = build_payload("588510", "测试基金A", "0.14", "1.0014")

        result = get_base_info(["588510"])
        print_observation("单基金兼容层输出", result.to_string())

        self.assertIsInstance(result, pd.Series)
        self.assertEqual(result["基金代码"], "588510")
        self.assertEqual(result["基金简称"], "测试基金A")
        self.assertEqual(result["简介"], "第一行 第二行")
        self.assertIsInstance(result["涨跌幅"], float)
        self.assertIsInstance(result["最新净值"], float)
        self.assertEqual(result["最新净值"], 1.0014)

    @patch("efinance_cli.fund_compat._fetch_base_info_payload")
    def test_multiple_codes_return_dataframe(self, mock_fetch: unittest.mock.Mock) -> None:
        """多只基金输入应返回按输入顺序拼装的 `DataFrame`。"""

        mock_fetch.side_effect = [
            build_payload("588510", "测试基金A", "0.14", "1.0014"),
            build_payload("161725", "测试基金B", "-1.20", "0.9988"),
        ]

        result = get_base_info(["588510", "161725"])
        print_observation("多基金兼容层输出", result.to_string(index=False))

        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(result.shape, (2, 8))
        self.assertEqual(result.loc[0, "基金代码"], "588510")
        self.assertEqual(result.loc[1, "基金代码"], "161725")
        self.assertIsInstance(result.loc[0, "最新净值"], float)
        self.assertEqual(result.loc[1, "涨跌幅"], -1.2)

    def test_registry_uses_local_compat_callback(self) -> None:
        """注册中心应把 `fund.get_base_info` 绑定到本地兼容实现。"""

        spec = get_command_spec("fund", "get_base_info")
        print_observation(
            "fund.get_base_info 注册回调",
            {"callback_name": spec.callback.__name__, "is_local_compat": spec.callback is get_base_info},
        )
        self.assertIs(spec.callback, get_base_info)
