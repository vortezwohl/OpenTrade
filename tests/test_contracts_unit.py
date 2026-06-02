"""数据契约标准化层的独立单元测试。

验证 contracts.py 中 uild_standard_result、
ormalize_contract_mapping
与 ensure_mapping_has_required_fields 的核心路径与边界行为。这些函数是
provider 返回值进入 observation 的数据防线，其正确性直接影响整个系统的
输出一致性。
"""

from __future__ import annotations

import unittest

import pandas as pd

from opentrade.contracts import (
    HISTORY_BARS_CONTRACT,
    PROFILE_INFO_CONTRACT,
    REALTIME_QUOTES_CONTRACT,
    SEARCH_RESULTS_CONTRACT,
    StandardizationError,
    build_standard_result,
    ensure_mapping_has_required_fields,
    normalize_contract_mapping,
)
from tests.cli_regression_support import print_observation


class ContractsUnitTest(unittest.TestCase):
    """覆盖契约标准化层的核心函数。"""

    # ------------------------------------------------------------------
    # build_standard_result
    # ------------------------------------------------------------------

    def test_build_standard_result_with_dataframe(self) -> None:
        """正常 DataFrame 输入应返回正确的 StandardResult。"""
        frame = pd.DataFrame(
            [{"日期": "2025-01-02", "股票代码": "000001", "开盘": 10.0, "收盘": 10.5, "最高": 10.6, "最低": 9.9}]
        )
        result = build_standard_result(contract=HISTORY_BARS_CONTRACT, data=frame)
        print_observation("build_standard_result 正常 DataFrame", result)
        self.assertEqual(result.contract_name, "history-bars")
        self.assertIsInstance(result.data, pd.DataFrame)

    def test_build_standard_result_with_list_of_dicts(self) -> None:
        """列表输入应正确设置 contract_name 和 data。"""
        data = [{"code": "000001", "name": "平安银行"}]
        result = build_standard_result(
            contract=SEARCH_RESULTS_CONTRACT,
            data=data,
            provider_fields={"backend": "efinance"},
        )
        self.assertEqual(result.contract_name, "search-results")
        self.assertEqual(result.data, data)
        self.assertEqual(result.provider_fields, {"backend": "efinance"})

    def test_build_standard_result_with_empty_dataframe(self) -> None:
        """空 DataFrame 应不崩溃，返回结构完整的结果。"""
        result = build_standard_result(contract=HISTORY_BARS_CONTRACT, data=pd.DataFrame())
        self.assertEqual(result.contract_name, "history-bars")

    # ------------------------------------------------------------------
    # normalize_contract_mapping
    # ------------------------------------------------------------------

    def test_normalize_chinese_column_names_to_english(self) -> None:
        """中文列名应被映射为标准英文别名。"""
        mapping = {"A股代码": "000001", "A股简称": "平安银行"}
        normalized = normalize_contract_mapping(mapping, SEARCH_RESULTS_CONTRACT)
        print_observation("normalize 中文->英文", normalized)
        self.assertEqual(normalized.get("code"), "000001")
        self.assertEqual(normalized.get("name"), "平安银行")

    def test_normalize_with_english_keys_direct(self) -> None:
        """英文 key 已在别名表中时应直接匹配。"""
        mapping = {"code": "000001", "name": "平安银行"}
        normalized = normalize_contract_mapping(mapping, SEARCH_RESULTS_CONTRACT)
        self.assertEqual(normalized["code"], "000001")
        self.assertEqual(normalized["name"], "平安银行")

    def test_normalize_picks_first_valid_alias(self) -> None:
        """多个别名均存在时取第一个匹配。"""
        mapping = {"symbol": "AAPL", "代码": "105.AAPL"}
        normalized = normalize_contract_mapping(mapping, SEARCH_RESULTS_CONTRACT)
        self.assertEqual(normalized["code"], "AAPL")

    def test_normalize_skips_null_aliases(self) -> None:
        """别名字段值为 None 或空串时跳过。"""
        mapping = {"symbol": None, "证券代码": "000001"}
        normalized = normalize_contract_mapping(mapping, PROFILE_INFO_CONTRACT)
        self.assertEqual(normalized["code"], "000001")

    def test_normalize_profile_info_contract(self) -> None:
        """PROFILE_INFO_CONTRACT 应正确映射中文资料字段。"""
        mapping = {"股票代码": "600519", "股票名称": "贵州茅台", "市盈率(动)": 28.5, "市净率": 9.8}
        normalized = normalize_contract_mapping(mapping, PROFILE_INFO_CONTRACT)
        self.assertEqual(normalized["code"], "600519")
        self.assertEqual(normalized["name"], "贵州茅台")
        self.assertEqual(normalized["pe"], 28.5)
        self.assertEqual(normalized["pb"], 9.8)

    # ------------------------------------------------------------------
    # ensure_mapping_has_required_fields
    # ------------------------------------------------------------------

    def test_all_required_fields_present_passes_silently(self) -> None:
        """所有必填字段存在应静默通过。"""
        mapping = {"code": "000001", "name": "平安银行"}
        ensure_mapping_has_required_fields(mapping, SEARCH_RESULTS_CONTRACT)

    def test_missing_required_field_raises_standardization_error(self) -> None:
        """缺少必填字段应抛出 StandardizationError。"""
        mapping = {"code": "000001"}
        with self.assertRaises(StandardizationError) as ctx:
            ensure_mapping_has_required_fields(mapping, SEARCH_RESULTS_CONTRACT)
        message = str(ctx.exception)
        self.assertIn("search-results", message)
        self.assertIn("name", message)

    def test_null_required_field_counted_as_missing(self) -> None:
        """必填字段值为 None 时应视为缺失。"""
        with self.assertRaises(StandardizationError):
            ensure_mapping_has_required_fields({"code": "000001", "name": None}, SEARCH_RESULTS_CONTRACT)

    def test_empty_string_required_field_counted_as_missing(self) -> None:
        """必填字段值为空串时应视为缺失。"""
        with self.assertRaises(StandardizationError) as ctx:
            ensure_mapping_has_required_fields({"code": "", "name": "平安银行"}, SEARCH_RESULTS_CONTRACT)
        self.assertIn("code", str(ctx.exception))

    def test_multiple_missing_fields_all_reported(self) -> None:
        """多个缺失字段应在异常消息中全部列出。"""
        with self.assertRaises(StandardizationError) as ctx:
            ensure_mapping_has_required_fields({"date": "2025-01-02"}, HISTORY_BARS_CONTRACT)
        message = str(ctx.exception)
        for field in ("symbol", "open", "close", "high", "low"):
            self.assertIn(field, message)


if __name__ == "__main__":
    unittest.main()
