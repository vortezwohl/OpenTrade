"""技术指标算子子包的最小烟雾测试。

这些测试不追求验证每个指标的金融意义是否完全正确，而是优先确认：

- 子包可以被正常导入；
- 典型指标能够返回预期类型；
- 关键列名存在；
- 不会因为明显的实现错误在最小样本上直接崩溃。
"""

from __future__ import annotations

import unittest

import pandas as pd

from efinance_cli import indicators


def build_sample_frame() -> pd.DataFrame:
    """构造一段稳定的样例行情数据。"""
    return pd.DataFrame(
        {
            "open": [10, 10.5, 10.8, 11.0, 11.3, 11.1, 11.5, 11.9, 12.2, 12.0, 12.4, 12.8],
            "high": [10.2, 10.7, 11.0, 11.2, 11.5, 11.4, 11.8, 12.1, 12.4, 12.3, 12.7, 13.0],
            "low": [9.8, 10.1, 10.5, 10.7, 11.0, 10.9, 11.1, 11.6, 11.9, 11.7, 12.0, 12.4],
            "close": [10.1, 10.6, 10.9, 11.1, 11.2, 11.3, 11.7, 12.0, 12.1, 12.2, 12.6, 12.9],
            "volume": [100, 120, 130, 150, 145, 160, 180, 210, 205, 190, 220, 250],
        }
    )


class IndicatorSmokeTest(unittest.TestCase):
    """验证技术指标子包的最小可用性。"""

    def test_indicator_exports_exist(self) -> None:
        """确认关键导出存在。"""
        self.assertTrue(hasattr(indicators, "macd"))
        self.assertTrue(hasattr(indicators, "rsi"))
        self.assertTrue(hasattr(indicators, "obv"))
        self.assertTrue(hasattr(indicators, "atr"))
        self.assertTrue(hasattr(indicators, "bias"))

    def test_macd_returns_expected_columns(self) -> None:
        """MACD 应返回标准列。"""
        frame = build_sample_frame()
        result = indicators.macd(frame["close"], fast_period=3, slow_period=6, signal_period=3)
        self.assertEqual(list(result.columns), ["dif", "dea", "histogram"])

    def test_kdj_returns_expected_columns(self) -> None:
        """KDJ 应返回 K/D/J 三列。"""
        frame = build_sample_frame()
        result = indicators.kdj(frame["high"], frame["low"], frame["close"], k_period=5)
        self.assertEqual(list(result.columns), ["k", "d", "j"])

    def test_bollinger_bands_returns_expected_columns(self) -> None:
        """布林带应返回中轨、上下轨与附加列。"""
        frame = build_sample_frame()
        result = indicators.bollinger_bands(frame["close"], period=5)
        self.assertEqual(list(result.columns), ["middle", "upper", "lower", "bandwidth", "percent_b"])

    def test_obv_returns_series(self) -> None:
        """OBV 应返回与输入等长的 Series。"""
        frame = build_sample_frame()
        result = indicators.obv(frame["close"], frame["volume"])
        self.assertIsInstance(result, pd.Series)
        self.assertEqual(len(result), len(frame))

    def test_pivot_points_returns_expected_columns(self) -> None:
        """枢轴点位应返回七列。"""
        frame = build_sample_frame()
        result = indicators.pivot_points(frame["high"], frame["low"], frame["close"])
        self.assertEqual(list(result.columns), ["pivot", "r1", "s1", "r2", "s2", "r3", "s3"])
