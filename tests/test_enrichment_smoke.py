"""技术指标增强层的最小烟雾测试。"""

from __future__ import annotations

import unittest

import pandas as pd

from efinance_cli.enrichment.indicators import enrich_history_frame
from efinance_cli.enrichment.levels import normalize_indicator_level
from tests.cli_regression_support import print_observation


def build_ohlcv_frame() -> pd.DataFrame:
    """构造一段带 OHLCV 列的样本行情。"""
    return pd.DataFrame(
        {
            "日期": pd.date_range("2025-01-01", periods=40, freq="D").astype(str),
            "开盘": [10 + i * 0.1 for i in range(40)],
            "收盘": [10.1 + i * 0.1 for i in range(40)],
            "最高": [10.2 + i * 0.1 for i in range(40)],
            "最低": [9.8 + i * 0.1 for i in range(40)],
            "成交量": [1000 + i * 50 for i in range(40)],
        }
    )


class EnrichmentSmokeTest(unittest.TestCase):
    """验证增强层最小可用性。"""

    def test_level_aliases(self) -> None:
        """数字等级别名应能映射为规范名。"""
        print_observation(
            "指标等级别名映射",
            {
                "1": normalize_indicator_level("1"),
                "2": normalize_indicator_level("2"),
                "3": normalize_indicator_level("3"),
            },
        )
        self.assertEqual(normalize_indicator_level("1"), "basic")
        self.assertEqual(normalize_indicator_level("2"), "advanced")
        self.assertEqual(normalize_indicator_level("3"), "full")

    def test_basic_history_enrichment_adds_core_columns(self) -> None:
        """基础等级应补充核心指标列。"""
        frame = build_ohlcv_frame()
        enriched = enrich_history_frame(frame, "basic")
        print_observation("basic 增强列", list(enriched.columns))
        print_observation("basic 增强尾行", enriched.tail(1).to_string(index=False))
        for column in [
            "ma5",
            "ma10",
            "ma20",
            "ema12",
            "ema26",
            "macd_dif",
            "macd_dea",
            "macd_histogram",
            "rsi14",
            "kdj_k",
            "boll_middle",
            "atr14",
            "obv",
        ]:
            self.assertIn(column, enriched.columns)

    def test_advanced_history_enrichment_adds_extended_columns(self) -> None:
        """进阶等级应补充扩展指标列。"""
        frame = build_ohlcv_frame()
        enriched = enrich_history_frame(frame, "advanced")
        print_observation("advanced 增强列", list(enriched.columns))
        print_observation("advanced 增强尾行", enriched.tail(1).to_string(index=False))
        for column in [
            "roc12",
            "bias6",
            "bbi",
            "adx",
            "supertrend",
            "mfi14",
            "vwap",
            "vr",
        ]:
            self.assertIn(column, enriched.columns)

    def test_full_history_enrichment_adds_full_columns(self) -> None:
        """全量等级应补充完整指标列。"""
        frame = build_ohlcv_frame()
        enriched = enrich_history_frame(frame, "full")
        print_observation("full 增强列", list(enriched.columns))
        print_observation("full 增强尾行", enriched.tail(1).to_string(index=False))
        for column in [
            "tenkan",
            "kijun",
            "parabolic_sar",
            "pivot_pivot",
            "fib_0.5",
            "support_20",
            "adl",
            "chaikin_osc",
        ]:
            self.assertIn(column, enriched.columns)
