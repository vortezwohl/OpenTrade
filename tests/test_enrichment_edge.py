"""技术指标增强层的边界输入测试。

验证 enrich_history_frame 在各种非标准输入场景下的抗崩溃能力与合理降级行为。
这些场景在正常使用中较少出现，但一旦触发不应导致整个 CLI 命令报错退出。
"""

from __future__ import annotations

import unittest

import pandas as pd

from opentrade.enrichment.indicators import enrich_history_frame
from tests.cli_regression_support import print_observation


class EnrichmentEdgeTest(unittest.TestCase):
    """覆盖 enrich_history_frame 的边界输入场景。"""

    def test_empty_dataframe_does_not_crash(self) -> None:
        """空 DataFrame 应不抛出异常并返回空 DataFrame。"""
        frame = pd.DataFrame(columns=["日期", "开盘", "收盘", "最高", "最低", "成交量"])
        result = enrich_history_frame(frame, "basic")
        print_observation(
            "空 DataFrame 增强结果", {"columns": list(result.columns)}
        )

        self.assertIsInstance(result, pd.DataFrame)
        self.assertTrue(result.empty)

    def test_single_row_dataframe_does_not_crash(self) -> None:
        """单行 DataFrame 应不抛出异常并保持数据完整。"""
        frame = pd.DataFrame(
            [
                {
                    "日期": "2025-01-02",
                    "开盘": 10.0,
                    "收盘": 10.1,
                    "最高": 10.2,
                    "最低": 9.9,
                    "成交量": 10000,
                }
            ]
        )
        result = enrich_history_frame(frame, "full")
        print_observation(
            "单行 DataFrame 增强结果", {
                "columns": list(result.columns),
                "row_count": len(result),
            }
        )

        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 1)
        # 原始列应保留
        for col in ["日期", "开盘", "收盘"]:
            self.assertIn(col, result.columns)

    def test_missing_volume_column_skips_volume_indicators(self) -> None:
        """缺少 '成交量' 列时成交量依赖指标不应出现，其他指标正常。"""
        frame = pd.DataFrame(
            {
                "日期": pd.date_range("2025-01-02", periods=30,
                                    freq="B").astype(str),
                "开盘": [10.0 + i * 0.15 for i in range(30)],
                "收盘": [10.1 + i * 0.15 for i in range(30)],
                "最高": [10.2 + i * 0.15 for i in range(30)],
                "最低": [9.9 + i * 0.15 for i in range(30)],
            }
        )
        result = enrich_history_frame(frame, "advanced")
        print_observation("缺成交量列增强结果列", list(result.columns))

        # 基础指标应存在
        for col in ["ma5", "ma10", "ma20", "rsi14", "macd_dif"]:
            self.assertIn(col, result.columns)
        # 成交量依赖指标不应存在
        for col in ["obv", "mfi14", "vwap"]:
            self.assertNotIn(col, result.columns)

    def test_only_close_and_date_columns_present(self) -> None:
        """仅含 '收盘' 和 '日期' 时基于收盘价的指标正常，OHLC 指标缺失。"""
        frame = pd.DataFrame(
            {
                "日期": pd.date_range("2025-01-02", periods=30,
                                    freq="B").astype(str),
                "收盘": [10.1 + i * 0.15 for i in range(30)],
            }
        )
        result = enrich_history_frame(frame, "full")
        print_observation("仅收盘+日期增强结果列", list(result.columns))

        # 基于收盘价的指标应存在
        for col in ["ma5", "ma10", "ema12", "rsi14", "macd_dif"]:
            self.assertIn(col, result.columns)
        # 依赖 OHLC 的指标不应存在
        for col in ["kdj_k", "boll_middle", "atr14"]:
            self.assertNotIn(col, result.columns)

    def test_english_column_names_behave_same_as_chinese(self) -> None:
        """英文列名（open/close/high/low/volume）应与中文列名行为一致。"""
        frame_en = pd.DataFrame(
            {
                "date":
                pd.date_range("2025-01-02", periods=30, freq="B").astype(str),
                "open": [10.0 + i * 0.15 for i in range(30)],
                "close": [10.1 + i * 0.15 for i in range(30)],
                "high": [10.2 + i * 0.15 for i in range(30)],
                "low": [9.9 + i * 0.15 for i in range(30)],
                "volume": [10000 + i * 200 for i in range(30)],
            }
        )
        result_en = enrich_history_frame(frame_en.copy(), "basic")

        frame_cn = frame_en.rename(
            columns={
                "open": "开盘",
                "close": "收盘",
                "high": "最高",
                "low": "最低",
                "volume": "成交量",
                "date": "日期",
            }
        )
        result_cn = enrich_history_frame(frame_cn, "basic")

        print_observation("英文列名增强列", sorted(result_en.columns))
        print_observation("中文列名增强列", sorted(result_cn.columns))

        # 增强结果的核心指标列应一致（排除原始列名差异）
        en_indicator_cols = {
            c
            for c in result_en.columns if c not in frame_en.columns
        }
        cn_indicator_cols = {
            c
            for c in result_cn.columns if c not in frame_cn.columns
        }
        self.assertEqual(en_indicator_cols, cn_indicator_cols)

    def test_full_level_adds_ichimoku_and_parabolic_sar(self) -> None:
        """Full 等级应补充一目均衡、抛物线 SAR 与 pivot 衍生列。"""
        frame = pd.DataFrame(
            {
                "日期": pd.date_range("2025-01-02", periods=30,
                                    freq="B").astype(str),
                "开盘": [10.0 + i * 0.15 for i in range(30)],
                "收盘": [10.1 + i * 0.15 for i in range(30)],
                "最高": [10.2 + i * 0.15 for i in range(30)],
                "最低": [9.9 + i * 0.15 for i in range(30)],
                "成交量": [10000 + i * 200 for i in range(30)],
            }
        )
        result = enrich_history_frame(frame, "full")
        print_observation("full 等级增强列", list(result.columns))

        for col in ["tenkan", "kijun", "parabolic_sar", "senkou_a", "chikou"]:
            self.assertIn(col, result.columns)


if __name__ == "__main__":
    unittest.main()
