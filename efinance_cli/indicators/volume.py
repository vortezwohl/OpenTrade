"""成交量与资金流类指标。"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from efinance_cli.indicators.base import ema, typical_price
from efinance_cli.indicators.utils import rolling_mean, safe_divide, to_series, validate_period


def obv(close: pd.Series | Iterable[float], volume: pd.Series | Iterable[float]) -> pd.Series:
    """能量潮 OBV。"""
    close_series = to_series(close)
    volume_series = to_series(volume)
    direction = close_series.diff().fillna(0).apply(lambda value: 1 if value > 0 else (-1 if value < 0 else 0))
    return (direction * volume_series).cumsum()


def accumulation_distribution(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    volume: pd.Series | Iterable[float],
) -> pd.Series:
    """累积/派发线 ADL。"""
    high_series = to_series(high)
    low_series = to_series(low)
    close_series = to_series(close)
    volume_series = to_series(volume)
    money_flow_multiplier = safe_divide(
        (close_series - low_series) - (high_series - close_series),
        high_series - low_series,
    ).fillna(0)
    return (money_flow_multiplier * volume_series).cumsum()


def chaikin_money_flow(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    volume: pd.Series | Iterable[float],
    period: int = 20,
) -> pd.Series:
    """Chaikin Money Flow。"""
    validate_period(period)
    adl_component = accumulation_distribution(high, low, close, volume).diff().fillna(0)
    volume_series = to_series(volume)
    return safe_divide(
        adl_component.rolling(period, min_periods=period).sum(),
        volume_series.rolling(period, min_periods=period).sum(),
    )


def chaikin_oscillator(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    volume: pd.Series | Iterable[float],
    fast_period: int = 3,
    slow_period: int = 10,
) -> pd.Series:
    """Chaikin Oscillator。"""
    adl = accumulation_distribution(high, low, close, volume)
    return ema(adl, fast_period) - ema(adl, slow_period)


def mfi(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    volume: pd.Series | Iterable[float],
    period: int = 14,
) -> pd.Series:
    """资金流量指标 MFI。"""
    validate_period(period)
    tp = typical_price(high, low, close)
    volume_series = to_series(volume)
    raw_money_flow = tp * volume_series
    direction = tp.diff()
    positive_flow = raw_money_flow.where(direction > 0, 0.0)
    negative_flow = raw_money_flow.where(direction < 0, 0.0).abs()
    positive_sum = positive_flow.rolling(period, min_periods=period).sum()
    negative_sum = negative_flow.rolling(period, min_periods=period).sum()
    money_ratio = safe_divide(positive_sum, negative_sum)
    return 100 - (100 / (1 + money_ratio))


def vwap(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    close: pd.Series | Iterable[float],
    volume: pd.Series | Iterable[float],
    group: pd.Series | None = None,
) -> pd.Series:
    """成交量加权平均价 VWAP。

    Args:
        group: 可选分组键，例如交易日序列；传入后将按组分别累计。
    """
    tp = typical_price(high, low, close)
    volume_series = to_series(volume)
    weighted = tp * volume_series
    if group is None:
        return weighted.cumsum() / volume_series.cumsum()
    weighted_cumsum = weighted.groupby(group).cumsum()
    volume_cumsum = volume_series.groupby(group).cumsum()
    return weighted_cumsum / volume_cumsum


def force_index(
    close: pd.Series | Iterable[float],
    volume: pd.Series | Iterable[float],
    period: int = 13,
) -> pd.Series:
    """Force Index。"""
    close_series = to_series(close)
    volume_series = to_series(volume)
    raw = close_series.diff() * volume_series
    return ema(raw, period)


def ease_of_movement(
    high: pd.Series | Iterable[float],
    low: pd.Series | Iterable[float],
    volume: pd.Series | Iterable[float],
    period: int = 14,
) -> pd.DataFrame:
    """简易波动指标 EMV。"""
    high_series = to_series(high)
    low_series = to_series(low)
    volume_series = to_series(volume)
    midpoint_move = ((high_series + low_series) / 2).diff()
    box_ratio = safe_divide(volume_series / 100000000, high_series - low_series)
    emv_raw = safe_divide(midpoint_move, box_ratio)
    emv_ma = rolling_mean(emv_raw, period)
    return pd.concat({"emv": emv_raw, "emv_ma": emv_ma}, axis=1)


def price_volume_trend(close: pd.Series | Iterable[float], volume: pd.Series | Iterable[float]) -> pd.Series:
    """价量趋势 PVT。"""
    close_series = to_series(close)
    volume_series = to_series(volume)
    pct_change = safe_divide(close_series.diff(), close_series.shift(1)).fillna(0)
    return (pct_change * volume_series).cumsum()


def volume_ratio(volume: pd.Series | Iterable[float], period: int = 5) -> pd.Series:
    """量比型算子，当前成交量相对过去均量。"""
    volume_series = to_series(volume)
    return safe_divide(volume_series, rolling_mean(volume_series, period))
