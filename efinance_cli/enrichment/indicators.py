"""把技术指标算子应用到行情表。"""

from __future__ import annotations

import pandas as pd

from efinance_cli import indicators


def enrich_history_frame(frame: pd.DataFrame, level: str) -> pd.DataFrame:
    """对历史 K 线表直接附加技术指标列。"""
    normalized = normalize_history_columns(frame)
    close = normalized.get("close")
    if close is None:
        return frame

    enriched = frame.copy()
    add_basic_indicators(enriched, normalized)
    if level in {"advanced", "full"}:
        add_advanced_indicators(enriched, normalized)
    if level == "full":
        add_full_indicators(enriched, normalized)
    return enriched


def normalize_history_columns(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """识别不同市场 K 线表中的标准列。"""
    column_map = {
        "open": ["开盘", "今开", "单位净值", "open"],
        "high": ["最高", "high"],
        "low": ["最低", "low"],
        "close": ["收盘", "最新价", "单位净值", "close"],
        "volume": ["成交量", "volume"],
    }
    normalized: dict[str, pd.Series] = {}
    for standard_name, candidates in column_map.items():
        for candidate in candidates:
            if candidate in frame.columns:
                normalized[standard_name] = pd.to_numeric(frame[candidate], errors="coerce")
                break
    return normalized


def add_basic_indicators(frame: pd.DataFrame, columns: dict[str, pd.Series]) -> None:
    """附加基础指标。"""
    close = columns["close"]
    frame["ma5"] = indicators.sma(close, 5)
    frame["ma10"] = indicators.sma(close, 10)
    frame["ma20"] = indicators.sma(close, 20)
    frame["ema12"] = indicators.ema(close, 12)
    frame["ema26"] = indicators.ema(close, 26)

    macd_frame = indicators.macd(close)
    frame["macd_dif"] = macd_frame["dif"]
    frame["macd_dea"] = macd_frame["dea"]
    frame["macd_histogram"] = macd_frame["histogram"]
    frame["rsi14"] = indicators.rsi(close, 14)

    if {"high", "low", "close"}.issubset(columns):
        high = columns["high"]
        low = columns["low"]
        kdj_frame = indicators.kdj(high, low, close)
        frame["kdj_k"] = kdj_frame["k"]
        frame["kdj_d"] = kdj_frame["d"]
        frame["kdj_j"] = kdj_frame["j"]

        boll = indicators.bollinger_bands(close, 20)
        frame["boll_middle"] = boll["middle"]
        frame["boll_upper"] = boll["upper"]
        frame["boll_lower"] = boll["lower"]
        frame["atr14"] = indicators.atr(high, low, close, 14)

    if "volume" in columns:
        volume = columns["volume"]
        frame["obv"] = indicators.obv(close, volume)
        frame["volume_ratio_5"] = indicators.volume_ratio(volume, 5)


def add_advanced_indicators(frame: pd.DataFrame, columns: dict[str, pd.Series]) -> None:
    """附加进阶指标。"""
    close = columns["close"]
    frame["roc12"] = indicators.roc(close, 12)
    frame["bias6"] = indicators.bias(close, 6)
    frame["bbi"] = indicators.bbi(close)
    frame["ppo"] = indicators.ppo(close)["ppo"]
    frame["ppo_signal"] = indicators.ppo(close)["signal"]
    frame["trix"] = indicators.trix(close)["trix"]
    frame["tsi"] = indicators.tsi(close)["tsi"]

    if {"high", "low", "close"}.issubset(columns):
        high = columns["high"]
        low = columns["low"]
        frame["cci14"] = indicators.cci(high, low, close, 14)
        frame["williams_r14"] = indicators.williams_r(high, low, close, 14)

        dmi_frame = indicators.adx(high, low, close, 14)
        frame["plus_di"] = dmi_frame["plus_di"]
        frame["minus_di"] = dmi_frame["minus_di"]
        frame["adx"] = dmi_frame["adx"]

        donchian = indicators.donchian_channel(high, low, 20)
        frame["donchian_upper"] = donchian["upper"]
        frame["donchian_lower"] = donchian["lower"]

        keltner = indicators.keltner_channel(high, low, close, 20, 10, 2.0)
        frame["keltner_upper"] = keltner["upper"]
        frame["keltner_lower"] = keltner["lower"]
        frame["natr14"] = indicators.natr(high, low, close, 14)

        supertrend = indicators.supertrend(high, low, close, 10, 3.0)
        frame["supertrend"] = supertrend["supertrend"]
        frame["supertrend_direction"] = supertrend["direction"]

    if "volume" in columns and {"high", "low", "close"}.issubset(columns):
        high = columns["high"]
        low = columns["low"]
        volume = columns["volume"]
        frame["mfi14"] = indicators.mfi(high, low, close, volume, 14)
        frame["pvt"] = indicators.price_volume_trend(close, volume)
        frame["cmf20"] = indicators.chaikin_money_flow(high, low, close, volume, 20)
        frame["force_index13"] = indicators.force_index(close, volume, 13)
        frame["vwap"] = indicators.vwap(high, low, close, volume)
        frame["vr"] = indicators.vr(close, volume, 26)
        frame["psy"] = indicators.psy(close)["psy"]


def add_full_indicators(frame: pd.DataFrame, columns: dict[str, pd.Series]) -> None:
    """附加全量指标。"""
    close = columns["close"]
    frame["mass_index"] = None

    if {"high", "low", "close"}.issubset(columns):
        high = columns["high"]
        low = columns["low"]

        ichimoku = indicators.ichimoku_cloud(high, low, close)
        frame["tenkan"] = ichimoku["tenkan"]
        frame["kijun"] = ichimoku["kijun"]
        frame["senkou_a"] = ichimoku["senkou_a"]
        frame["senkou_b"] = ichimoku["senkou_b"]
        frame["chikou"] = ichimoku["chikou"]

        frame["parabolic_sar"] = indicators.parabolic_sar(high, low)
        frame["mass_index"] = indicators.mass_index(high, low)

        pivots = indicators.pivot_points(high, low, close)
        for column in pivots.columns:
            frame[f"pivot_{column}"] = pivots[column]

        fib = indicators.fibonacci_retracement(high, low, 60)
        for column in fib.columns:
            frame[f"fib_{column}"] = fib[column]

        sr = indicators.rolling_support_resistance(high, low, 20)
        frame["support_20"] = sr["support"]
        frame["resistance_20"] = sr["resistance"]

    if "volume" in columns and {"high", "low", "close"}.issubset(columns):
        high = columns["high"]
        low = columns["low"]
        volume = columns["volume"]
        frame["adl"] = indicators.accumulation_distribution(high, low, close, volume)
        frame["chaikin_osc"] = indicators.chaikin_oscillator(high, low, close, volume)
        frame["chaikin_volatility"] = indicators.chaikin_volatility(high, low)
        frame["emv"] = indicators.emv(high, low, volume)["emv"]
