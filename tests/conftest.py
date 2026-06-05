"""Pytest 级别的测试环境初始化。

该文件确保测试时优先导入当前工作树下的 `opentrade` 包，而不是用户环境中已
安装的其他同名包，否则会造成命令面、模型定义与渲染逻辑的回归结果失真。

同时提供多个测试文件共用的标准样本数据 fixture，避免各测试文件重复构造相同 数据导致漂移。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def sample_ohlcv_frame() -> pd.DataFrame:
    """返回一段标准的 OHLCV 历史行情样本 DataFrame。

    该 fixture 使用中文列名，与 efinance 返回的原始列名风格一致，适用于 指标计算、增强层与契约标准化测试。
    """
    return pd.DataFrame(
        {
            "日期": pd.date_range("2025-01-02", periods=30,
                                freq="B").astype(str),
            "开盘": [10.0 + i * 0.15 for i in range(30)],
            "收盘": [10.1 + i * 0.15 for i in range(30)],
            "最高": [10.2 + i * 0.15 for i in range(30)],
            "最低": [9.9 + i * 0.15 for i in range(30)],
            "成交量": [10000 + i * 200 for i in range(30)],
        }
    )


@pytest.fixture(scope="session")
def sample_empty_dataframe() -> pd.DataFrame:
    """返回一个结构正确但无数据的空 DataFrame，用于边界测试。"""
    return pd.DataFrame(columns=["日期", "开盘", "收盘", "最高", "最低", "成交量"])


@pytest.fixture(scope="session")
def sample_single_row_dataframe() -> pd.DataFrame:
    """返回仅包含单行数据的 OHLCV DataFrame，用于边界测试。"""
    return pd.DataFrame(
        [
            {
                "日期": "2025-01-02",
                "开盘": 10.0,
                "收盘": 10.1,
                "最高": 10.2,
                "最低": 9.9,
                "成交量": 10000,
            }
        ]
    )


@pytest.fixture(scope="session")
def sample_profile_data() -> dict[str, object]:
    """返回一份标准的股票 profile 样本字典，用于 provider handler 测试。"""
    return {
        "code": "000001",
        "name": "平安银行",
        "market": "A_stock",
        "industry": "银行",
        "market_cap": 3_000_000_000_000,
        "pe": 5.2,
        "pb": 0.6,
    }
