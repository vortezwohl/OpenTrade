"""趋势类技术指标。

本模块聚焦于趋势方向、趋势强度和趋势通道类指标，覆盖中短线分析中最常见的趋势
判断工具。返回值以 `Series` 或 `DataFrame` 为主，方便直接与行情数据拼接。
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from efinance_cli.indicators.base import ema, highest, lowest, rma, sma, true_range, typical_price
from efinance_cli.indicators.utils import rolling_std, safe_divide, to_frame, to_series, validate_period


def macd(
    values: pd.Series | Iterable[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> pd.DataFrame:
    """MACD 指标，返回 DIF、DEA 与柱体值。"""
    fast = ema(values, fast_period)
    slow = ema(values, slow_period)
    dif = fast - slow
    dea = ema(dif, signal_period)
    histogram = (dif - dea) * 2
    return to_frame({"dif": dif, "dea": dea, "histogram": histogram})


def bollinger_bands(
    values: pd.Series | Iterable[float],
    period: int = 20,
    std_multiplier: float = 2.0,
) -> pd.DataFrame:
    """布林带。"""
    middle = sma(values, period)
    deviation = rolling_std(to_series(values), period)
    upper = middle + deviation * std_multiplier
    lower = middle - deviation * std_multiplier
    bandwidth = safe_divide(upper - lower, middle)
    percent_b = safe_divide(to_series(values) - lower, upper - lower)
    return to_frame(
        {
            "middle": middle,
            "upper": upper,
            "lower": lower,
            "bandwidth": bandwidth,
            "percent_b": percent_b,
        }
    )


def donchian_channel(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    period: int = 20,
) -> pd.DataFrame:
    """唐奇安通道。"""
    upper = highest(high, period)
    lower = lowest(low, period)
    middle = (upper + lower) / 2
    return to_frame({"upper": upper, "middle": middle, "lower": lower})


def keltner_channel(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    ema_period: int = 20,
    atr_period: int = 10,
    atr_multiplier: float = 2.0,
) -> pd.DataFrame:
    """Keltner Channel。"""
    mid = ema(typical_price(high, low, close), ema_period)
    atr_series = rma(true_range(high, low, close), atr_period)
    upper = mid + atr_series * atr_multiplier
    lower = mid - atr_series * atr_multiplier
    return to_frame({"middle": mid, "upper": upper, "lower": lower})


def moving_average_envelope(
    values: pd.Series | Iterable[float],
    period: int = 20,
    offset: float = 0.03,
) -> pd.DataFrame:
    """均线包络线。"""
    center = sma(values, period)
    upper = center * (1 + offset)
    lower = center * (1 - offset)
    return to_frame({"middle": center, "upper": upper, "lower": lower})


def aroon_indicator(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    period: int = 25,
) -> pd.DataFrame:
    """Aroon 指标。"""
    validate_period(period)
    high_series = to_series(high)
    low_series = to_series(low)

    aroon_up = high_series.rolling(window=period, min_periods=period).apply(
        lambda window: ((period - 1 - (period - 1 - np.argmax(window.values))) / (period - 1)) * 100,
        raw=False,
    )
    aroon_down = low_series.rolling(window=period, min_periods=period).apply(
        lambda window: ((period - 1 - (period - 1 - np.argmin(window.values))) / (period - 1)) * 100,
        raw=False,
    )
    oscillator = aroon_up - aroon_down
    return to_frame({"aroon_up": aroon_up, "aroon_down": aroon_down, "oscillator": oscillator})


def dmi(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    period: int = 14,
) -> pd.DataFrame:
    """方向运动指标 DMI。"""
    validate_period(period)
    high_series = to_series(high)
    low_series = to_series(low)

    up_move = high_series.diff()
    down_move = -low_series.diff()

    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    atr_series = rma(true_range(high, low, close), period)
    plus_di = safe_divide(rma(plus_dm, period) * 100, atr_series)
    minus_di = safe_divide(rma(minus_dm, period) * 100, atr_series)
    return to_frame({"plus_di": plus_di, "minus_di": minus_di})


def adx(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    period: int = 14,
) -> pd.DataFrame:
    """平均趋向指数 ADX。"""
    dmi_frame = dmi(high, low, close, period)
    plus_di = dmi_frame["plus_di"]
    minus_di = dmi_frame["minus_di"]
    dx = safe_divide((plus_di - minus_di).abs(), plus_di + minus_di) * 100
    adx_series = rma(dx, period)
    adxr_series = (adx_series + adx_series.shift(period)) / 2
    return to_frame(
        {
            "plus_di": plus_di,
            "minus_di": minus_di,
            "dx": dx,
            "adx": adx_series,
            "adxr": adxr_series,
        }
    )


def supertrend(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    atr_period: int = 10,
    multiplier: float = 3.0,
) -> pd.DataFrame:
    """SuperTrend 指标。"""
    high_series = to_series(high)
    low_series = to_series(low)
    close_series = to_series(close)
    atr_series = rma(true_range(high, low, close), atr_period)
    hl2 = (high_series + low_series) / 2
    basic_upper = hl2 + multiplier * atr_series
    basic_lower = hl2 - multiplier * atr_series

    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    trend = pd.Series(index=close_series.index, dtype="float64")
    direction = pd.Series(index=close_series.index, dtype="int64")

    for i in range(1, len(close_series)):
        final_upper.iloc[i] = (
            basic_upper.iloc[i]
            if close_series.iloc[i - 1] > final_upper.iloc[i - 1]
            else min(basic_upper.iloc[i], final_upper.iloc[i - 1])
        )
        final_lower.iloc[i] = (
            basic_lower.iloc[i]
            if close_series.iloc[i - 1] < final_lower.iloc[i - 1]
            else max(basic_lower.iloc[i], final_lower.iloc[i - 1])
        )

        if close_series.iloc[i] <= final_upper.iloc[i]:
            trend.iloc[i] = final_upper.iloc[i]
            direction.iloc[i] = -1
        else:
            trend.iloc[i] = final_lower.iloc[i]
            direction.iloc[i] = 1

    return to_frame(
        {
            "supertrend": trend,
            "upper_band": final_upper,
            "lower_band": final_lower,
            "direction": direction,
        }
    )


def parabolic_sar(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    step: float = 0.02,
    max_step: float = 0.2,
) -> pd.Series:
    """抛物线 SAR。"""
    high_series = to_series(high)
    low_series = to_series(low)
    sar = pd.Series(index=high_series.index, dtype="float64")
    long = True
    af = step
    ep = high_series.iloc[0]
    sar.iloc[0] = low_series.iloc[0]

    for i in range(1, len(high_series)):
        prev_sar = sar.iloc[i - 1]
        sar.iloc[i] = prev_sar + af * (ep - prev_sar)

        if long:
            sar.iloc[i] = min(sar.iloc[i], low_series.iloc[i - 1], low_series.iloc[i])
            if low_series.iloc[i] < sar.iloc[i]:
                long = False
                sar.iloc[i] = ep
                ep = low_series.iloc[i]
                af = step
            else:
                if high_series.iloc[i] > ep:
                    ep = high_series.iloc[i]
                    af = min(af + step, max_step)
        else:
            sar.iloc[i] = max(sar.iloc[i], high_series.iloc[i - 1], high_series.iloc[i])
            if high_series.iloc[i] > sar.iloc[i]:
                long = True
                sar.iloc[i] = ep
                ep = high_series.iloc[i]
                af = step
            else:
                if low_series.iloc[i] < ep:
                    ep = low_series.iloc[i]
                    af = min(af + step, max_step)
    return sar


def ichimoku_cloud(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_b_period: int = 52,
    displacement: int = 26,
) -> pd.DataFrame:
    """一目均衡表。"""
    high_series = to_series(high)
    low_series = to_series(low)
    close_series = to_series(close)

    tenkan = (highest(high_series, tenkan_period) + lowest(low_series, tenkan_period)) / 2
    kijun = (highest(high_series, kijun_period) + lowest(low_series, kijun_period)) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(displacement)
    senkou_b = ((highest(high_series, senkou_b_period) + lowest(low_series, senkou_b_period)) / 2).shift(displacement)
    chikou = close_series.shift(-displacement)
    return to_frame(
        {
            "tenkan": tenkan,
            "kijun": kijun,
            "senkou_a": senkou_a,
            "senkou_b": senkou_b,
            "chikou": chikou,
        }
    )
