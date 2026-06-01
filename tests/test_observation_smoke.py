"""structured observation 输出的组装与 shared 命令烟雾测试。

该文件只覆盖当前仍然真实存在的 shared 命令链路，重点验证：

- trace window 与 recent event 检测的基础契约；
- shared history / profile / live / fund-nav 结果进入 observation 的路径；
- shared capability 的标准历史补充接口；
- generic observation 仍可为未纳入专门模板的 shared 结果兜底。
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from efinance_cli.command_catalog import get_command_definition, get_shared_command_definition
from efinance_cli.enrichment.service import fetch_standard_history_for_request
from efinance_cli.models import (
    BackendName,
    BackendSelection,
    CommandSpec,
    InvocationRequest,
    ObservationPayload,
    OutputOptions,
)
from efinance_cli.observation import build_observation_output, detect_recent_events
from tests.cli_regression_support import print_observation


def build_history_frame() -> pd.DataFrame:
    """构造带多指标交叉与阈值事件的历史行情样本。"""
    return pd.DataFrame(
        {
            "股票代码": ["AAPL"] * 6,
            "股票名称": ["Apple Inc."] * 6,
            "日期": [
                "2026-05-21",
                "2026-05-22",
                "2026-05-23",
                "2026-05-26",
                "2026-05-27",
                "2026-05-28",
            ],
            "收盘": [99.0, 101.0, 100.0, 102.0, 104.0, 106.0],
            "开盘": [98.0, 100.0, 99.0, 101.0, 103.0, 105.0],
            "最高": [100.0, 102.0, 101.0, 103.0, 105.0, 107.0],
            "最低": [97.0, 99.0, 98.0, 100.0, 102.0, 104.0],
            "成交量": [1000, 1200, 1100, 1300, 1500, 1700],
            "ma5": [100.0, 100.0, 99.8, 100.5, 102.0, 103.0],
            "ma10": [100.2, 100.2, 100.1, 100.4, 101.0, 102.5],
            "ma20": [100.5, 100.5, 100.4, 100.3, 100.8, 101.4],
            "ema12": [99.7, 100.1, 100.0, 100.9, 101.8, 102.9],
            "ema26": [100.1, 100.2, 100.1, 100.5, 101.0, 101.7],
            "macd_dif": [-0.30, -0.10, 0.05, 0.20, 0.28, 0.36],
            "macd_dea": [-0.20, -0.12, -0.02, 0.08, 0.18, 0.26],
            "macd_histogram": [-0.10, 0.02, 0.07, 0.12, 0.10, 0.10],
            "rsi14": [45.0, 48.0, 51.0, 54.0, 56.0, 59.0],
            "kdj_k": [40.0, 45.0, 50.0, 55.0, 60.0, 62.0],
            "kdj_d": [42.0, 44.0, 47.0, 52.0, 57.0, 60.0],
            "kdj_j": [36.0, 47.0, 56.0, 61.0, 66.0, 66.0],
            "ppo": [-0.10, -0.05, 0.02, 0.06, 0.09, 0.12],
            "ppo_signal": [-0.08, -0.06, -0.01, 0.03, 0.06, 0.09],
            "atr14": [2.1, 2.0, 1.9, 2.0, 2.1, 2.2],
            "boll_upper": [103.0, 103.0, 103.0, 103.5, 104.0, 105.0],
            "boll_lower": [96.0, 96.0, 96.0, 96.5, 97.0, 97.5],
            "obv": [100.0, 220.0, 180.0, 320.0, 470.0, 640.0],
            "volume_ratio_5": [0.8, 0.9, 1.1, 1.2, 1.0, 1.3],
            "mfi14": [48.0, 50.0, 53.0, 55.0, 58.0, 60.0],
            "cmf20": [-0.05, -0.02, 0.01, 0.03, 0.06, 0.08],
            "supertrend": [101.5, 101.4, 101.2, 101.0, 102.0, 103.0],
            "supertrend_direction": [-1.0, -1.0, 1.0, 1.0, 1.0, 1.0],
            "plus_di": [18.0, 19.0, 21.0, 24.0, 26.0, 28.0],
            "minus_di": [22.0, 21.0, 20.0, 18.0, 17.0, 16.0],
        }
    )


def build_shared_stock_history_request(trace_window: int = 32) -> InvocationRequest:
    """构造 shared 股票历史 observation 请求。"""
    definition = get_shared_command_definition("stock.price.history")
    return InvocationRequest(
        spec=CommandSpec(
            module_name="shared",
            function_name="stock.price.history",
            callback=lambda **_: None,
            help_text="test",
        ),
        kwargs={
            "stock_codes": ["000001"],
            "market_type": "A_stock",
            "beg": "20260501",
            "end": "20260528",
            "klt": 101,
            "fqt": 1,
        },
        output=OutputOptions(
            format_name="table",
            indicator_level="full",
            view_mode="observation",
            trace_window=trace_window,
        ),
        command_definition=definition,
        backend_selection=BackendSelection(
            requested=BackendName.EFINANCE,
            resolved=BackendName.EFINANCE,
            source="explicit",
        ),
    )


def build_shared_stock_profile_request(trace_window: int = 32) -> InvocationRequest:
    """构造 shared 股票资料 observation 请求。"""
    definition = get_shared_command_definition("stock.profile")
    return InvocationRequest(
        spec=CommandSpec(
            module_name="shared",
            function_name="stock.profile",
            callback=lambda **_: None,
            help_text="test",
        ),
        kwargs={"stock_codes": ["000001"], "market_type": "A_stock"},
        output=OutputOptions(
            format_name="table",
            indicator_level="full",
            view_mode="observation",
            trace_window=trace_window,
        ),
        command_definition=definition,
        backend_selection=BackendSelection(
            requested=BackendName.EFINANCE,
            resolved=BackendName.EFINANCE,
            source="explicit",
        ),
    )


def build_shared_fund_nav_history_request(trace_window: int = 32) -> InvocationRequest:
    """构造 shared 基金净值历史 observation 请求。"""
    definition = get_shared_command_definition("fund.nav.history")
    return InvocationRequest(
        spec=CommandSpec(
            module_name="shared",
            function_name="fund.nav.history",
            callback=lambda **_: None,
            help_text="test",
        ),
        kwargs={"fund_code": "161725", "pz": 40000},
        output=OutputOptions(
            format_name="table",
            indicator_level="full",
            view_mode="observation",
            trace_window=trace_window,
        ),
        command_definition=definition,
        backend_selection=BackendSelection(
            requested=BackendName.EFINANCE,
            resolved=BackendName.EFINANCE,
            source="explicit",
        ),
    )


def build_shared_fund_nav_history_batch_request(trace_window: int = 32) -> InvocationRequest:
    """构造 shared 基金批量净值历史 observation 请求。"""
    definition = get_command_definition("fund.nav.history-batch")
    return InvocationRequest(
        spec=CommandSpec(
            module_name="shared",
            function_name="fund.nav.history-batch",
            callback=lambda **_: None,
            help_text="test",
        ),
        kwargs={"fund_codes": ["161725", "110022"], "pz": 40000},
        output=OutputOptions(
            format_name="table",
            indicator_level="full",
            view_mode="observation",
            trace_window=trace_window,
        ),
        command_definition=definition,
        backend_selection=BackendSelection(
            requested=BackendName.EFINANCE,
            resolved=BackendName.EFINANCE,
            source="explicit",
        ),
    )


def build_shared_bond_history_request(trace_window: int = 32) -> InvocationRequest:
    """构造 shared 债券历史 observation 请求。"""
    definition = get_command_definition("bond.price.history")
    return InvocationRequest(
        spec=CommandSpec(
            module_name="shared",
            function_name="bond.price.history",
            callback=lambda **_: None,
            help_text="test",
        ),
        kwargs={
            "bond_codes": ["113519"],
            "beg": "20260501",
            "end": "20260528",
            "klt": 101,
            "fqt": 1,
        },
        output=OutputOptions(
            format_name="table",
            indicator_level="full",
            view_mode="observation",
            trace_window=trace_window,
        ),
        command_definition=definition,
        backend_selection=BackendSelection(
            requested=BackendName.EFINANCE,
            resolved=BackendName.EFINANCE,
            source="explicit",
        ),
    )


def build_shared_quote_profile_request(trace_window: int = 32) -> InvocationRequest:
    """构造 shared 通用行情资料 observation 请求。"""
    definition = get_shared_command_definition("quote.profile")
    return InvocationRequest(
        spec=CommandSpec(
            module_name="shared",
            function_name="quote.profile",
            callback=lambda **_: None,
            help_text="test",
        ),
        kwargs={"quote_id": "1.000001"},
        output=OutputOptions(
            format_name="table",
            indicator_level="full",
            view_mode="observation",
            trace_window=trace_window,
        ),
        command_definition=definition,
        backend_selection=BackendSelection(
            requested=BackendName.EFINANCE,
            resolved=BackendName.EFINANCE,
            source="explicit",
        ),
    )


def build_shared_stock_live_request(trace_window: int = 32, limit: int | None = None) -> InvocationRequest:
    """构造 shared 股票实时 observation 请求。"""
    definition = get_shared_command_definition("stock.price.live")
    return InvocationRequest(
        spec=CommandSpec(
            module_name="shared",
            function_name="stock.price.live",
            callback=lambda **_: None,
            help_text="test",
        ),
        kwargs={"fs": (), "market_type": "A_stock"},
        output=OutputOptions(
            format_name="table",
            indicator_level="full",
            view_mode="observation",
            trace_window=trace_window,
            limit=limit,
        ),
        command_definition=definition,
        backend_selection=BackendSelection(
            requested=BackendName.EFINANCE,
            resolved=BackendName.EFINANCE,
            source="explicit",
        ),
    )


class ObservationSmokeTest(unittest.TestCase):
    """覆盖 shared observation 结构化输出的关键烟雾场景。"""

    def test_trace_window_defaults_to_32_and_accepts_user_override(self) -> None:
        """默认 trace window 为 32，用户传值时应按请求裁剪。"""
        frame = build_history_frame()
        default_payload = build_observation_output(build_shared_stock_history_request(), frame)
        override_payload = build_observation_output(build_shared_stock_history_request(trace_window=4), frame)
        self.assertIsInstance(default_payload, ObservationPayload)
        self.assertIsInstance(override_payload, ObservationPayload)
        print_observation("默认 trace payload.meta", default_payload.meta)
        print_observation("覆盖 trace payload.meta", override_payload.meta)

        self.assertEqual(default_payload.meta["trace_window"], 32)
        self.assertEqual(len(default_payload.trace_points[0].points), len(frame))
        self.assertEqual(override_payload.meta["trace_window"], 4)
        self.assertEqual(len(override_payload.trace_points[0].points), 4)
        self.assertEqual(override_payload.trace_points[0].points[0]["bar_offset"], -3)

    def test_recent_events_cover_multiple_indicator_families(self) -> None:
        """近期事件应覆盖均线交叉、阈值跨越、band touch 与方向变化。"""
        frame = build_history_frame()
        series_map = {
            column: pd.to_numeric(frame[column], errors="coerce")
            for column in frame.columns
            if column not in {"股票代码", "股票名称", "日期"}
        }
        series_map["close"] = pd.to_numeric(frame["收盘"], errors="coerce")
        events = detect_recent_events(frame, series_map)
        keys = {event.event_key for event in events}
        print_observation("recent event keys", sorted(keys))

        self.assertIn("ma5_crossed_above_ma10", keys)
        self.assertIn("macd_dif_crossed_above_macd_dea", keys)
        self.assertIn("rsi14_crossed_above_50", keys)
        self.assertIn("close_touched_upper_band_boll_upper", keys)
        self.assertIn("supertrend_direction_changed_positive", keys)
        self.assertIn("obv_rose_3_bars", keys)

    def test_shared_stock_history_can_build_observation_payload(self) -> None:
        """shared stock history 结果应能生成标准历史 observation。"""
        frame = build_history_frame().rename(
            columns={
                "股票代码": "symbol",
                "股票名称": "name",
                "日期": "date",
                "收盘": "close",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
            }
        )
        frame["symbol"] = "000001"
        payload = build_observation_output(build_shared_stock_history_request(trace_window=4), frame)
        print_observation("shared stock history payload", payload)

        self.assertIsInstance(payload, ObservationPayload)
        self.assertEqual(payload.meta["module"], "shared")
        self.assertEqual(payload.meta["function"], "stock.price.history")
        self.assertEqual(payload.meta["trace_window"], 4)
        self.assertEqual(payload.meta["row_count"], 4)
        self.assertEqual(payload.meta["code"], "000001")
        self.assertEqual(payload.meta["resolved_backend"], "efinance")
        self.assertEqual(payload.meta["final_backend"], "efinance")
        self.assertEqual(payload.meta["candidate_chain"], [])
        self.assertEqual(payload.latest_quote["close"], 106.0)
        self.assertTrue(payload.trace_points)
        self.assertTrue(payload.recent_events)

    def test_shared_stock_history_observation_exposes_final_backend_under_auto(self) -> None:
        frame = build_history_frame().rename(
            columns={
                "股票代码": "symbol",
                "股票名称": "name",
                "日期": "date",
                "收盘": "close",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
            }
        )
        frame["symbol"] = "AAPL"
        request = build_shared_stock_history_request(trace_window=4)
        request.backend_selection = BackendSelection(
            requested=None,
            resolved=BackendName.AUTO,
            source="default",
            candidate_chain=(BackendName.AKSHARE, BackendName.YFINANCE, BackendName.EFINANCE),
            final_backend=BackendName.YFINANCE,
        )

        payload = build_observation_output(request, frame)
        self.assertIsInstance(payload, ObservationPayload)
        self.assertEqual(payload.meta["requested_backend"], None)
        self.assertEqual(payload.meta["resolved_backend"], "auto")
        self.assertEqual(payload.meta["final_backend"], "yfinance")
        self.assertEqual(payload.meta["candidate_chain"], ["akshare", "yfinance", "efinance"])

    def test_shared_stock_history_observation_normalizes_provider_alias_columns(self) -> None:
        """shared stock history 应优先通过契约层兼容 provider 别名列。"""
        frame = build_history_frame().copy()
        payload = build_observation_output(build_shared_stock_history_request(trace_window=4), frame)

        print_observation("shared stock history alias payload", payload)
        self.assertIsInstance(payload, ObservationPayload)
        self.assertEqual(payload.meta["code"], "AAPL")
        self.assertEqual(payload.latest_quote["close"], 106.0)
        self.assertIn("close", payload.current_metrics)

    def test_shared_bond_history_can_build_observation_payload(self) -> None:
        frame = build_history_frame().rename(
            columns={
                "股票代码": "symbol",
                "股票名称": "name",
                "日期": "date",
                "收盘": "close",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
            }
        )
        frame["symbol"] = "113519"
        payload = build_observation_output(build_shared_bond_history_request(trace_window=4), frame)

        print_observation("shared bond history payload", payload)
        self.assertIsInstance(payload, ObservationPayload)
        self.assertEqual(payload.meta["function"], "bond.price.history")
        self.assertEqual(payload.meta["code"], "113519")
        self.assertEqual(payload.latest_quote["close"], 106.0)

    def test_shared_history_lookup_uses_standard_supplement_interface(self) -> None:
        """shared 历史回补应走标准补充接口，而不是旧 provider 直调。"""
        request = build_shared_stock_history_request(trace_window=4)
        standard_rows = [
            {
                "date": "2026-05-26",
                "symbol": "000001",
                "open": 10.0,
                "close": 10.2,
                "high": 10.3,
                "low": 9.9,
                "volume": 1000,
            },
            {
                "date": "2026-05-27",
                "symbol": "000001",
                "open": 10.2,
                "close": 10.4,
                "high": 10.5,
                "low": 10.1,
                "volume": 1200,
            },
        ]

        standard_result = type("MockStandardResult", (), {"data": standard_rows})()
        with patch("efinance_cli.facade.CommandFacade.invoke", return_value=standard_result) as mock_invoke:
            frame = fetch_standard_history_for_request(request, "000001", "basic")

        print_observation(
            "shared history lookup frame",
            frame.to_dict(orient="records") if frame is not None else None,
        )
        self.assertIsInstance(frame, pd.DataFrame)
        self.assertEqual(list(frame["symbol"]), ["000001", "000001"])
        mock_invoke.assert_called_once()

    def test_shared_stock_profile_can_build_observation_payload(self) -> None:
        """shared stock profile 结果应能复用共享历史回补生成 observation payload。"""
        profile_row = pd.Series(
            {
                "code": "000001",
                "name": "平安银行",
                "pe": 5.1,
                "industry": "银行",
            }
        )
        history_frame = build_history_frame().rename(
            columns={
                "股票代码": "symbol",
                "股票名称": "name",
                "日期": "date",
                "收盘": "close",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
            }
        )
        history_frame["symbol"] = "000001"

        with patch("efinance_cli.facade.CommandFacade.invoke") as mock_invoke:
            mock_invoke.return_value = type(
                "MockStandardResult",
                (),
                {"data": history_frame.to_dict(orient="records")},
            )()
            payload = build_observation_output(build_shared_stock_profile_request(trace_window=4), profile_row)

        print_observation("shared stock profile payload", payload)
        self.assertIsInstance(payload, ObservationPayload)
        self.assertEqual(payload.meta["module"], "shared")
        self.assertEqual(payload.meta["function"], "stock.profile")
        self.assertEqual(payload.meta["code"], "000001")
        self.assertEqual(payload.latest_quote["code"], "000001")
        self.assertEqual(payload.latest_quote["name"], "平安银行")
        self.assertEqual(payload.current_metrics["close"], 106.0)
        self.assertTrue(payload.trace_points)

    def test_shared_quote_profile_can_build_observation_payload(self) -> None:
        profile_row = pd.Series(
            {
                "quote_id": "1.000001",
                "name": "平安银行",
                "market": "A_stock",
            }
        )
        history_frame = build_history_frame().rename(
            columns={
                "股票代码": "symbol",
                "股票名称": "name",
                "日期": "date",
                "收盘": "close",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
            }
        )

        with patch("efinance_cli.facade.CommandFacade.invoke") as mock_invoke:
            mock_invoke.side_effect = lambda _definition, _backend, request_data: type(
                "MockStandardResult",
                (),
                {
                    "data": history_frame.assign(
                        symbol=request_data["codes"][0],
                    ).to_dict(orient="records")
                },
            )()
            payload = build_observation_output(build_shared_quote_profile_request(trace_window=4), profile_row)

        print_observation("shared quote profile payload", payload)
        self.assertIsInstance(payload, ObservationPayload)
        self.assertEqual(payload.meta["function"], "quote.profile")
        self.assertEqual(payload.meta["code"], "1.000001")
        self.assertEqual(payload.current_metrics["close"], 106.0)

    def test_shared_stock_profile_observation_normalizes_provider_alias_fields(self) -> None:
        """shared stock profile 应优先通过契约层兼容 provider 字段别名。"""
        profile_row = pd.Series(
            {
                "股票代码": "000001",
                "股票名称": "平安银行",
                "市盈率(动态)": 5.1,
                "所处行业": "银行",
            }
        )
        history_frame = build_history_frame().rename(
            columns={
                "股票代码": "symbol",
                "股票名称": "name",
                "日期": "date",
                "收盘": "close",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
            }
        )
        history_frame["symbol"] = "000001"

        with patch("efinance_cli.facade.CommandFacade.invoke") as mock_invoke:
            mock_invoke.return_value = type(
                "MockStandardResult",
                (),
                {"data": history_frame.to_dict(orient="records")},
            )()
            payload = build_observation_output(build_shared_stock_profile_request(trace_window=4), profile_row)

        print_observation("shared stock profile alias payload", payload)
        self.assertIsInstance(payload, ObservationPayload)
        self.assertEqual(payload.meta["code"], "000001")
        self.assertEqual(payload.latest_quote["name"], "平安银行")
        self.assertEqual(payload.current_metrics["close"], 106.0)

    def test_shared_fund_nav_history_builds_defined_history_observation(self) -> None:
        """shared fund nav history 应走明确的净值序列 observation 主链。"""
        frame = pd.DataFrame(
            [
                {"date": "2026-05-26", "symbol": "161725", "unit_nav": 1.001, "accumulated_nav": 2.001, "change_pct": 0.1},
                {"date": "2026-05-27", "symbol": "161725", "unit_nav": 1.002, "accumulated_nav": 2.003, "change_pct": 0.2},
            ]
        )
        payload = build_observation_output(build_shared_fund_nav_history_request(trace_window=4), frame)

        print_observation("shared fund nav history payload", payload)
        self.assertIsInstance(payload, ObservationPayload)
        self.assertEqual(payload.meta["module"], "shared")
        self.assertEqual(payload.meta["function"], "fund.nav.history")
        self.assertEqual(payload.meta["code"], "161725")
        self.assertEqual(payload.latest_quote["close"], 1.002)
        self.assertIn("close", payload.current_metrics)
        self.assertFalse(payload.sections)

    def test_shared_fund_nav_history_batch_builds_multi_source_payloads(self) -> None:
        frame_map = {
            "161725": pd.DataFrame(
                [
                    {"date": "2026-05-26", "symbol": "161725", "unit_nav": 1.001},
                    {"date": "2026-05-27", "symbol": "161725", "unit_nav": 1.002},
                ]
            ),
            "110022": pd.DataFrame(
                [
                    {"date": "2026-05-26", "symbol": "110022", "unit_nav": 2.001},
                    {"date": "2026-05-27", "symbol": "110022", "unit_nav": 2.003},
                ]
            ),
        }
        payloads = build_observation_output(build_shared_fund_nav_history_batch_request(trace_window=4), frame_map)

        print_observation("shared fund nav history-batch payloads", payloads)
        self.assertIsInstance(payloads, dict)
        self.assertEqual(sorted(payloads), ["110022", "161725"])
        self.assertTrue(all(isinstance(item, ObservationPayload) for item in payloads.values()))
        self.assertEqual(payloads["161725"].meta["function"], "fund.nav.history-batch")

    def test_shared_stock_live_can_build_multi_source_observation_with_limit(self) -> None:
        """shared stock live 应能生成受 limit 控制的多 source observation。"""
        frame = pd.DataFrame(
            [
                {"symbol": "000001", "name": "平安银行", "close": 10.1, "open": 10.0, "high": 10.2, "low": 9.9},
                {"symbol": "000002", "name": "万科A", "close": 8.8, "open": 8.7, "high": 8.9, "low": 8.6},
                {"symbol": "000004", "name": "国华网安", "close": 12.3, "open": 12.1, "high": 12.5, "low": 12.0},
            ]
        )
        history_frame = build_history_frame().rename(
            columns={
                "股票代码": "symbol",
                "股票名称": "name",
                "日期": "date",
                "收盘": "close",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
            }
        )

        def build_history_result(symbol: str):
            rows = history_frame.copy()
            rows["symbol"] = symbol
            return type("MockStandardResult", (), {"data": rows.to_dict(orient="records")})()

        with patch("efinance_cli.facade.CommandFacade.invoke") as mock_invoke:
            mock_invoke.side_effect = lambda _definition, _backend, request_data: build_history_result(
                request_data["stock_codes"][0]
            )
            payloads = build_observation_output(
                build_shared_stock_live_request(trace_window=4, limit=2),
                frame,
            )

        print_observation("shared stock live payloads", payloads)
        self.assertIsInstance(payloads, dict)
        self.assertEqual(sorted(payloads), ["000001", "000002"])
        self.assertTrue(all(isinstance(item, ObservationPayload) for item in payloads.values()))
        self.assertEqual(payloads["000001"].meta["function"], "stock.price.live")
        self.assertEqual(payloads["000001"].latest_quote["code"], "000001")

    def test_shared_stock_live_observation_normalizes_provider_alias_rows(self) -> None:
        """shared stock live 应优先通过契约层兼容 provider 实时行别名。"""
        frame = pd.DataFrame(
            [
                {"代码": "000001", "名称": "平安银行", "最新价": 10.1, "今开": 10.0, "最高": 10.2, "最低": 9.9},
            ]
        )
        history_frame = build_history_frame().rename(
            columns={
                "股票代码": "symbol",
                "股票名称": "name",
                "日期": "date",
                "收盘": "close",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
            }
        )

        with patch("efinance_cli.facade.CommandFacade.invoke") as mock_invoke:
            mock_invoke.side_effect = lambda _definition, _backend, request_data: type(
                "MockStandardResult",
                (),
                {
                    "data": history_frame.assign(
                        symbol=request_data["stock_codes"][0],
                    ).to_dict(orient="records")
                },
            )()
            payloads = build_observation_output(build_shared_stock_live_request(trace_window=4, limit=1), frame)

        print_observation("shared stock live alias payloads", payloads)
        self.assertIsInstance(payloads, dict)
        self.assertEqual(list(payloads), ["000001"])
        self.assertEqual(payloads["000001"].meta["function"], "stock.price.live")


if __name__ == "__main__":
    unittest.main()
