"""波动率类技术指标。"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from efinance_cli.indicators.base import ema, rma, true_range
from efinance_cli.indicators.utils import rolling_std, safe_divide, to_series, validate_period


def atr(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    period: int = 14,
) -> pd.Series:
    """平均真实波幅 ATR。"""
    return rma(true_range(high, low, close), period)


def natr(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    period: int = 14,
) -> pd.Series:
    """标准化 ATR。"""
    close_series = to_series(close)
    return safe_divide(atr(high, low, close, period), close_series) * 100


def historical_volatility(
    close: pd.Series | Iterable[float],
    period: int = 20,
    annualize_factor: int = 252,
) -> pd.Series:
    """历史波动率。"""
    validate_period(period)
    close_series = to_series(close)
    log_return = np.log(safe_divide(close_series, close_series.shift(1)))
    return rolling_std(log_return, period) * np.sqrt(annualize_factor)


def chaikin_volatility(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    ema_period: int = 10,
    change_period: int = 10,
) -> pd.Series:
    """Chaikin Volatility。"""
    hl_range = to_series(high) - to_series(low)
    ema_range = ema(hl_range, ema_period)
    return safe_divide(ema_range - ema_range.shift(change_period), ema_range.shift(change_period)) * 100


def mass_index(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    ema_period: int = 9,
    sum_period: int = 25,
) -> pd.Series:
    """Mass Index。"""
    hl_range = (to_series(high) - to_series(low)).abs()
    single = ema(hl_range, ema_period)
    double = ema(single, ema_period)
    ratio = safe_divide(single, double)
    return ratio.rolling(sum_period, min_periods=sum_period).sum()
