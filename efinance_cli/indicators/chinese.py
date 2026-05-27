"""国内常见技术分析软件风格指标。

这些指标在 A 股语境中更常见，很多交易软件会直接提供同名字段。这里把它们实现为
纯算子，方便后续在策略或命令层直接复用。
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from efinance_cli.indicators.base import sma
from efinance_cli.indicators.utils import safe_divide, to_frame, to_series, validate_period
from efinance_cli.indicators.volume import ease_of_movement


def bias(values: pd.Series | Iterable[float], period: int = 6) -> pd.Series:
    """乖离率 BIAS。"""
    series = to_series(values)
    ma = sma(series, period)
    return safe_divide(series - ma, ma) * 100


def bbi(values: pd.Series | Iterable[float], periods: tuple[int, int, int, int] = (3, 6, 12, 24)) -> pd.Series:
    """多空指标 BBI。"""
    series = to_series(values)
    return sum(sma(series, period) for period in periods) / len(periods)


def psy(values: pd.Series | Iterable[float], period: int = 12, ma_period: int = 6) -> pd.DataFrame:
    """心理线 PSY。"""
    validate_period(period)
    series = to_series(values)
    up_count = series.diff().gt(0).rolling(period, min_periods=period).sum()
    psy_series = up_count / period * 100
    psy_ma = sma(psy_series, ma_period)
    return to_frame({"psy": psy_series, "psy_ma": psy_ma})


def vr(close: pd.Series | Iterable[float], volume: pd.Series | Iterable[float], period: int = 26) -> pd.Series:
    """成交量变异率 VR。"""
    close_series = to_series(close)
    volume_series = to_series(volume)
    previous_close = close_series.shift(1)
    av = volume_series.where(close_series > previous_close, 0.0)
    bv = volume_series.where(close_series < previous_close, 0.0)
    cv = volume_series.where(close_series == previous_close, 0.0)
    numerator = av.rolling(period, min_periods=period).sum() + cv.rolling(period, min_periods=period).sum() / 2
    denominator = bv.rolling(period, min_periods=period).sum() + cv.rolling(period, min_periods=period).sum() / 2
    return safe_divide(numerator, denominator) * 100


def mtm(values: pd.Series | Iterable[float], period: int = 12, ma_period: int = 6) -> pd.DataFrame:
    """动量线 MTM。"""
    series = to_series(values)
    mtm_series = series - series.shift(period)
    mtm_ma = sma(mtm_series, ma_period)
    return to_frame({"mtm": mtm_series, "mtm_ma": mtm_ma})


def dma(values: pd.Series | Iterable[float], short_period: int = 10, long_period: int = 50, ama_period: int = 10) -> pd.DataFrame:
    """平行线差指标 DMA。"""
    series = to_series(values)
    dif = sma(series, short_period) - sma(series, long_period)
    ama = sma(dif, ama_period)
    return to_frame({"dif": dif, "ama": ama})


def brar(
    open_: pd.Series | Iterable[float],
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    period: int = 26,
) -> pd.DataFrame:
    """BRAR 指标。"""
    open_series = to_series(open_, name="open")
    high_series = to_series(high)
    low_series = to_series(low)
    close_series = to_series(close)
    previous_close = close_series.shift(1)

    ar = safe_divide(
        (high_series - open_series).rolling(period, min_periods=period).sum(),
        (open_series - low_series).rolling(period, min_periods=period).sum(),
    ) * 100
    br = safe_divide(
        (high_series - previous_close).clip(lower=0).rolling(period, min_periods=period).sum(),
        (previous_close - low_series).clip(lower=0).rolling(period, min_periods=period).sum(),
    ) * 100
    return to_frame({"ar": ar, "br": br})


def cr(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    period: int = 26,
) -> pd.DataFrame:
    """CR 能量指标。"""
    high_series = to_series(high)
    low_series = to_series(low)
    close_series = to_series(close)
    mid = close_series.shift(1)
    up = (high_series - mid).clip(lower=0)
    down = (mid - low_series).clip(lower=0)
    cr_series = safe_divide(
        up.rolling(period, min_periods=period).sum(),
        down.rolling(period, min_periods=period).sum(),
    ) * 100
    ma1 = sma(cr_series, 5)
    ma2 = sma(cr_series, 10)
    ma3 = sma(cr_series, 20)
    ma4 = sma(cr_series, 40)
    return to_frame({"cr": cr_series, "ma1": ma1, "ma2": ma2, "ma3": ma3, "ma4": ma4})


def emv(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    volume: pd.Series | Iterable[float],
    period: int = 14,
) -> pd.DataFrame:
    """EMV 指标，封装 `ease_of_movement` 的常用名称。"""
    return ease_of_movement(high, low, volume, period)


def asi(
    open_: pd.Series | Iterable[float],
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    period: int = 26,
) -> pd.DataFrame:
    """振动升降指标 ASI。"""
    open_series = to_series(open_, name="open")
    high_series = to_series(high)
    low_series = to_series(low)
    close_series = to_series(close)
    previous_close = close_series.shift(1)
    previous_open = open_series.shift(1)

    a = (high_series - previous_close).abs()
    b = (low_series - previous_close).abs()
    c = (high_series - previous_open).abs()
    d = (previous_close - previous_open).abs()
    e = close_series - previous_close
    f = close_series - open_series
    g = previous_close - previous_open

    x = e + f / 2 + g
    k = pd.concat([a, b], axis=1).max(axis=1)
    r = pd.Series(index=close_series.index, dtype="float64")
    r[:] = 0.0
    r = r.where(~((a > b) & (a > c)), a + b / 2 + d / 4)
    r = r.where(~((b > c) & (b > a)), b + a / 2 + d / 4)
    r = r.where(~((c >= a) & (c >= b)), c + d / 4)
    si = 16 * safe_divide(x, r) * k
    asi_series = si.cumsum()
    asit = sma(asi_series, period)
    return to_frame({"si": si, "asi": asi_series, "asit": asit})
