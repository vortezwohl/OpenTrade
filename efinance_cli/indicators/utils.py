"""技术指标算子共享工具函数。

该文件负责统一做输入序列规范化、数值安全处理和滚动窗口辅助，避免各指标函数重复
编写样板代码。所有指标函数都应优先复用这里的工具，以减少边界行为不一致的风险。
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def to_series(values: pd.Series | Iterable[float], name: str | None = None) -> pd.Series:
    """把输入值规范化为浮点 `Series`。

    Args:
        values: 原始输入序列，可为 Pandas Series 或可迭代对象。
        name: 可选的序列名；当输入本身已带名称且未显式传入时，沿用原名。

    Returns:
        统一转为 `float64` 的 Pandas Series。
    """
    if isinstance(values, pd.Series):
        series = values.copy()
        if name is not None:
            series.name = name
        return pd.to_numeric(series, errors="coerce").astype(float)
    series = pd.Series(list(values), name=name, dtype="float64")
    return pd.to_numeric(series, errors="coerce").astype(float)


def to_frame(series_map: dict[str, pd.Series]) -> pd.DataFrame:
    """把多列 `Series` 合并为 `DataFrame`。"""
    return pd.concat(series_map, axis=1)


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """做逐元素安全除法，自动规避除零。"""
    denominator = denominator.replace(0, np.nan)
    return numerator / denominator


def rolling_apply(series: pd.Series, window: int, func, min_periods: int | None = None) -> pd.Series:
    """对滚动窗口应用自定义函数。"""
    if min_periods is None:
        min_periods = window
    return series.rolling(window=window, min_periods=min_periods).apply(func, raw=False)


def validate_period(period: int, name: str = "period") -> int:
    """校验周期参数必须为正整数。"""
    if period <= 0:
        raise ValueError(f"{name} 必须为正整数，实际为 {period}")
    return period


def shifted(series: pd.Series, periods: int = 1) -> pd.Series:
    """简化 `shift` 调用。"""
    return series.shift(periods)


def rolling_sum(series: pd.Series, period: int, min_periods: int | None = None) -> pd.Series:
    """滚动求和。"""
    validate_period(period)
    return series.rolling(window=period, min_periods=min_periods or period).sum()


def rolling_mean(series: pd.Series, period: int, min_periods: int | None = None) -> pd.Series:
    """滚动均值。"""
    validate_period(period)
    return series.rolling(window=period, min_periods=min_periods or period).mean()


def rolling_std(series: pd.Series, period: int, min_periods: int | None = None, ddof: int = 0) -> pd.Series:
    """滚动标准差。"""
    validate_period(period)
    return series.rolling(window=period, min_periods=min_periods or period).std(ddof=ddof)
