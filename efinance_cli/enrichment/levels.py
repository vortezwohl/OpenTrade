"""技术指标等级定义。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IndicatorLevelConfig:
    """指标等级配置。"""

    name: str
    history_window: int
    realtime_limit: int


LEVELS: dict[str, IndicatorLevelConfig] = {
    "basic": IndicatorLevelConfig(name="basic", history_window=60, realtime_limit=50),
    "advanced": IndicatorLevelConfig(name="advanced", history_window=120, realtime_limit=80),
    "full": IndicatorLevelConfig(name="full", history_window=200, realtime_limit=120),
}

LEVEL_ALIASES: dict[str, str] = {
    "1": "basic",
    "2": "advanced",
    "3": "full",
}


def normalize_indicator_level(level: str) -> str:
    """把等级别名统一转换为规范名称。"""
    normalized = LEVEL_ALIASES.get(level, level)
    if normalized not in LEVELS:
        return "basic"
    return normalized
