"""价格结构与关键价位类算子。"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from efinance_cli.indicators.utils import to_frame, to_series, validate_period


def pivot_points(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
) -> pd.DataFrame:
    """经典枢轴点位。"""
    high_series = to_series(high)
    low_series = to_series(low)
    close_series = to_series(close)
    pivot = (high_series + low_series + close_series) / 3
    r1 = 2 * pivot - low_series
    s1 = 2 * pivot - high_series
    r2 = pivot + (high_series - low_series)
    s2 = pivot - (high_series - low_series)
    r3 = high_series + 2 * (pivot - low_series)
    s3 = low_series - 2 * (high_series - pivot)
    return to_frame({"pivot": pivot, "r1": r1, "s1": s1, "r2": r2, "s2": s2, "r3": r3, "s3": s3})


def fibonacci_retracement(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    period: int = 60,
) -> pd.DataFrame:
    """滚动窗口斐波那契回撤位。"""
    validate_period(period)
    high_series = to_series(high)
    low_series = to_series(low)
    highest_high = high_series.rolling(period, min_periods=period).max()
    lowest_low = low_series.rolling(period, min_periods=period).min()
    diff = highest_high - lowest_low
    return to_frame(
        {
            "0.0": highest_high,
            "0.236": highest_high - diff * 0.236,
            "0.382": highest_high - diff * 0.382,
            "0.5": highest_high - diff * 0.5,
            "0.618": highest_high - diff * 0.618,
            "0.786": highest_high - diff * 0.786,
            "1.0": lowest_low,
        }
    )


def rolling_support_resistance(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    period: int = 20,
) -> pd.DataFrame:
    """滚动支撑阻力位。"""
    validate_period(period)
    high_series = to_series(high)
    low_series = to_series(low)
    resistance = high_series.rolling(period, min_periods=period).max()
    support = low_series.rolling(period, min_periods=period).min()
    middle = (support + resistance) / 2
    return to_frame({"support": support, "middle": middle, "resistance": resistance})
