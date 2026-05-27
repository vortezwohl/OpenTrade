"""动量类技术指标。

动量指标更关注上涨或下跌速度、超买超卖状态以及拐点敏感度。中短线场景里，
RSI、KDJ、CCI、ROC 一类算子通常是最常用的基础构件。
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from efinance_cli.indicators.base import ema, highest, lowest, rma, sma, typical_price
from efinance_cli.indicators.utils import safe_divide, to_frame, to_series, validate_period


def momentum(values: pd.Series | Iterable[float], period: int = 10) -> pd.Series:
    """动量值，等于当前值减去 N 周期前值。"""
    validate_period(period)
    series = to_series(values)
    return series - series.shift(period)


def roc(values: pd.Series | Iterable[float], period: int = 12) -> pd.Series:
    """变化率 ROC。"""
    validate_period(period)
    series = to_series(values)
    return safe_divide(series - series.shift(period), series.shift(period)) * 100


def rsi(values: pd.Series | Iterable[float], period: int = 14) -> pd.Series:
    """相对强弱指标 RSI。"""
    validate_period(period)
    series = to_series(values)
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    average_gain = rma(gain, period)
    average_loss = rma(loss, period)
    rs = safe_divide(average_gain, average_loss)
    return 100 - (100 / (1 + rs))


def stochastic_oscillator(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    k_period: int = 14,
    d_period: int = 3,
    smooth_period: int = 3,
) -> pd.DataFrame:
    """随机指标的通用版本，返回 %K 与 %D。"""
    validate_period(k_period)
    high_series = to_series(high)
    low_series = to_series(low)
    close_series = to_series(close)
    lowest_low = lowest(low_series, k_period)
    highest_high = highest(high_series, k_period)
    raw_k = safe_divide(close_series - lowest_low, highest_high - lowest_low) * 100
    k = sma(raw_k, smooth_period, min_periods=smooth_period)
    d = sma(k, d_period, min_periods=d_period)
    return to_frame({"k": k, "d": d})


def kdj(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    k_period: int = 9,
    k_smooth: int = 3,
    d_smooth: int = 3,
) -> pd.DataFrame:
    """KDJ 指标。"""
    stochastic = stochastic_oscillator(
        high=high,
        low=low,
        close=close,
        k_period=k_period,
        d_period=d_smooth,
        smooth_period=k_smooth,
    )
    k = stochastic["k"]
    d = stochastic["d"]
    j = 3 * k - 2 * d
    return to_frame({"k": k, "d": d, "j": j})


def cci(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    period: int = 14,
) -> pd.Series:
    """顺势指标 CCI。"""
    tp = typical_price(high, low, close)
    ma = sma(tp, period)
    md = tp.rolling(window=period, min_periods=period).apply(
        lambda window: (window - window.mean()).abs().mean(),
        raw=False,
    )
    return safe_divide(tp - ma, 0.015 * md)


def williams_r(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    period: int = 14,
) -> pd.Series:
    """威廉指标 %R。"""
    highest_high = highest(high, period)
    lowest_low = lowest(low, period)
    close_series = to_series(close)
    return -safe_divide(highest_high - close_series, highest_high - lowest_low) * 100


def trix(values: pd.Series | Iterable[float], period: int = 12, signal_period: int = 9) -> pd.DataFrame:
    """TRIX 三重平滑动量指标。"""
    triple_ema = ema(ema(ema(values, period), period), period)
    trix_line = safe_divide(triple_ema.diff(), triple_ema.shift(1)) * 100
    signal = sma(trix_line, signal_period)
    return to_frame({"trix": trix_line, "signal": signal})


def tsi(
    values: pd.Series | Iterable[float],
    long_period: int = 25,
    short_period: int = 13,
    signal_period: int = 7,
) -> pd.DataFrame:
    """真实强弱指数 TSI。"""
    series = to_series(values)
    diff = series.diff()
    double_smoothed = ema(ema(diff, long_period), short_period)
    double_smoothed_abs = ema(ema(diff.abs(), long_period), short_period)
    tsi_line = safe_divide(double_smoothed, double_smoothed_abs) * 100
    signal = ema(tsi_line, signal_period)
    return to_frame({"tsi": tsi_line, "signal": signal})


def ultimate_oscillator(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    short_period: int = 7,
    medium_period: int = 14,
    long_period: int = 28,
) -> pd.Series:
    """终极振荡器。"""
    high_series = to_series(high)
    low_series = to_series(low)
    close_series = to_series(close)
    previous_close = close_series.shift(1)
    buying_pressure = close_series - pd.concat([low_series, previous_close], axis=1).min(axis=1)
    true_low = pd.concat([low_series, previous_close], axis=1).min(axis=1)
    true_high = pd.concat([high_series, previous_close], axis=1).max(axis=1)
    tr = true_high - true_low
    avg_short = safe_divide(buying_pressure.rolling(short_period).sum(), tr.rolling(short_period).sum())
    avg_medium = safe_divide(buying_pressure.rolling(medium_period).sum(), tr.rolling(medium_period).sum())
    avg_long = safe_divide(buying_pressure.rolling(long_period).sum(), tr.rolling(long_period).sum())
    return 100 * ((4 * avg_short) + (2 * avg_medium) + avg_long) / 7


def dpo(values: pd.Series | Iterable[float], period: int = 20) -> pd.Series:
    """去趋势价格振荡器 DPO。"""
    validate_period(period)
    series = to_series(values)
    offset = int(period / 2 + 1)
    return series.shift(offset) - sma(series, period)


def ppo(
    values: pd.Series | Iterable[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> pd.DataFrame:
    """百分比价格振荡器 PPO。"""
    fast = ema(values, fast_period)
    slow = ema(values, slow_period)
    ppo_line = safe_divide(fast - slow, slow) * 100
    signal = ema(ppo_line, signal_period)
    histogram = ppo_line - signal
    return to_frame({"ppo": ppo_line, "signal": signal, "histogram": histogram})
