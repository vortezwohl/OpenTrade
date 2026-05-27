"""基础价格序列算子与均线类指标。

这些算子是其他技术指标的底层积木，负责提供不同风格的平滑、窗口极值和典型价格。
它们保持纯函数形态，只依赖输入序列本身，不感知任何上层交易语义。
"""

from __future__ import annotations

import math
from typing import Iterable

import pandas as pd

from efinance_cli.indicators.utils import rolling_mean, to_series, validate_period


def sma(values: pd.Series | Iterable[float], period: int, min_periods: int | None = None) -> pd.Series:
    """简单移动平均线。

    Args:
        values: 输入价格或数值序列。
        period: 均线窗口长度。
        min_periods: 最小有效样本数；默认等于窗口长度。

    Returns:
        简单移动平均序列。
    """
    series = to_series(values)
    return rolling_mean(series, period, min_periods=min_periods)


def ema(values: pd.Series | Iterable[float], period: int, adjust: bool = False) -> pd.Series:
    """指数移动平均线。"""
    validate_period(period)
    series = to_series(values)
    return series.ewm(span=period, adjust=adjust, min_periods=period).mean()


def rma(values: pd.Series | Iterable[float], period: int) -> pd.Series:
    """Wilder 平滑均线，也常被视作 RSI 的内部均线。"""
    validate_period(period)
    series = to_series(values)
    return series.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def wma(values: pd.Series | Iterable[float], period: int) -> pd.Series:
    """加权移动平均线，权重随时间线性递增。"""
    validate_period(period)
    series = to_series(values)
    weights = pd.Series(range(1, period + 1), dtype="float64")
    divisor = float(weights.sum())
    return series.rolling(window=period, min_periods=period).apply(
        lambda window: float((window * weights).sum()) / divisor,
        raw=False,
    )


def dema(values: pd.Series | Iterable[float], period: int) -> pd.Series:
    """双指数移动平均线。"""
    first = ema(values, period)
    second = ema(first, period)
    return 2 * first - second


def tema(values: pd.Series | Iterable[float], period: int) -> pd.Series:
    """三重指数移动平均线。"""
    first = ema(values, period)
    second = ema(first, period)
    third = ema(second, period)
    return 3 * first - 3 * second + third


def trima(values: pd.Series | Iterable[float], period: int) -> pd.Series:
    """三角移动平均线。"""
    validate_period(period)
    series = sma(values, math.ceil(period / 2))
    return sma(series, math.floor(period / 2) + 1)


def hma(values: pd.Series | Iterable[float], period: int) -> pd.Series:
    """Hull Moving Average，兼顾平滑与低延迟。"""
    validate_period(period)
    half = max(1, period // 2)
    sqrt_period = max(1, int(math.sqrt(period)))
    raw = 2 * wma(values, half) - wma(values, period)
    return wma(raw, sqrt_period)


def zlema(values: pd.Series | Iterable[float], period: int) -> pd.Series:
    """零滞后 EMA。"""
    validate_period(period)
    series = to_series(values)
    lag = max(1, (period - 1) // 2)
    adjusted = series + (series - series.shift(lag))
    return ema(adjusted, period)


def highest(values: pd.Series | Iterable[float], period: int) -> pd.Series:
    """滚动窗口最高值。"""
    validate_period(period)
    series = to_series(values)
    return series.rolling(window=period, min_periods=period).max()


def lowest(values: pd.Series | Iterable[float], period: int) -> pd.Series:
    """滚动窗口最低值。"""
    validate_period(period)
    series = to_series(values)
    return series.rolling(window=period, min_periods=period).min()


def median_price(high: pd.Series | Iterable[float], low: pd.Series | Iterable[float]) -> pd.Series:
    """中价 `(high + low) / 2`。"""
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    return (high_series + low_series) / 2


def typical_price(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
) -> pd.Series:
    """典型价格 `(high + low + close) / 3`。"""
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    return (high_series + low_series + close_series) / 3


def true_range(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
) -> pd.Series:
    """真实波幅 True Range。"""
    high_series = to_series(high, name="high")
    low_series = to_series(low, name="low")
    close_series = to_series(close, name="close")
    previous_close = close_series.shift(1)
    components = pd.concat(
        [
            (high_series - low_series).abs(),
            (high_series - previous_close).abs(),
            (low_series - previous_close).abs(),
        ],
        axis=1,
    )
    return components.max(axis=1)
