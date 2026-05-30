"""结构化 observation 输出的组装与端到端烟雾测试。

该文件覆盖：

- `trace_window` 默认值与用户覆盖；
- 多指标 recent event detection 的基础契约；
- 支持命令在 observation 视图下的最小 CLI 输出链路。
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd
from click.testing import CliRunner

from efinance_cli.commands import create_root_command
from efinance_cli.models import (
    BackendName,
    CommandSpec,
    BackendSelection,
    CommandDefinition,
    InvocationRequest,
    InvocationResult,
    ObservationPayload,
    OutputOptions,
)
from efinance_cli.command_catalog import get_shared_command_definition
from efinance_cli.observation import (
    OBSERVATION_REALTIME_LIST_COMMANDS,
    build_observation_output,
    detect_recent_events,
)
from efinance_cli.enrichment.service import fetch_standard_history_for_request
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


def build_request(trace_window: int = 32) -> InvocationRequest:
    """构造 observation 组装请求。"""

    return InvocationRequest(
        spec=CommandSpec(
            module_name="common",
            function_name="get_quote_history",
            callback=lambda **_: None,
            help_text="test",
        ),
        kwargs={},
        output=OutputOptions(
            format_name="table",
            indicator_level="full",
            view_mode="observation",
            trace_window=trace_window,
        ),
    )


def build_single_row_request(function_name: str) -> InvocationRequest:
    """构造 single-row observation 组装请求。"""

    return InvocationRequest(
        spec=CommandSpec(
            module_name="stock" if function_name != "get_base_info_common" else "common",
            function_name="get_base_info" if function_name == "get_base_info_common" else function_name,
            callback=lambda **_: None,
            help_text="test",
        ),
        kwargs={"quote_id": "105.AAPL"} if function_name == "get_base_info_common" else {},
        output=OutputOptions(
            format_name="table",
            indicator_level="full",
            view_mode="observation",
            trace_window=4,
        ),
    )


def build_shared_equity_history_request(trace_window: int = 32) -> InvocationRequest:
    """构造共享权益历史 observation 组装请求。"""
    definition = get_shared_command_definition("equity.price.history")

    return InvocationRequest(
        spec=CommandSpec(
            module_name="shared",
            function_name="equity.price.history",
            callback=lambda **_: None,
            help_text="test",
        ),
        kwargs={
            "symbol": "000001",
            "market": "A_stock",
            "start_date": "20260501",
            "end_date": "20260528",
            "period": "daily",
            "adjust": "qfq",
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


class ObservationSmokeTest(unittest.TestCase):
    """覆盖 observation 结构化输出的关键烟雾场景。"""

    def test_trace_window_defaults_to_32_and_accepts_user_override(self) -> None:
        """默认 trace window 为 32，用户传值时应按请求裁剪。"""

        frame = build_history_frame()
        default_payload = build_observation_output(build_request(), frame)
        override_payload = build_observation_output(build_request(trace_window=4), frame)
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
        """事件检测应覆盖线交叉、阈值穿越、band touch 与方向变化。"""

        frame = build_history_frame()
        series_map = {column: pd.to_numeric(frame[column], errors="coerce") for column in frame.columns if column not in {"股票代码", "股票名称", "日期"}}
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

    def test_supported_history_command_can_render_observation_table(self) -> None:
        """支持命令在 observation 模式下应输出 boxed table。"""

        frame = build_history_frame()
        payload = build_observation_output(build_request(trace_window=4), frame)

        def fake_invoke(executor_self, request):
            self.assertEqual(request.spec.module_name, "common")
            self.assertEqual(request.spec.function_name, "get_quote_history")
            self.assertEqual(request.output.view_mode, "observation")
            self.assertEqual(request.output.trace_window, 4)
            return InvocationResult(value=payload)

        with patch("efinance_cli.executor.CommandExecutor.invoke", new=fake_invoke):
            runner = CliRunner()
            cli = create_root_command()
            result = runner.invoke(
                cli,
                [
                    "quote",
                    "price",
                    "history",
                    "--symbols",
                    "105.AAPL",
                    "--start-date",
                    "20260501",
                    "--end-date",
                    "20260528",
                    "--view",
                    "observation",
                    "--trace-window",
                    "4",
                ],
            )

        print_observation("history observation CLI 输出", result.output)
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("| meta", result.output)
        self.assertIn("| trace_points.price_ma", result.output)
        self.assertIn("| recent_events", result.output)

    def test_shared_equity_history_can_build_observation_payload(self) -> None:
        """共享 equity history 结果应进入标准历史 observation 链。"""

        frame = build_history_frame().rename(columns={"股票代码": "symbol", "股票名称": "name", "日期": "date", "收盘": "close", "开盘": "open", "最高": "high", "最低": "low", "成交量": "volume"})
        frame["symbol"] = "000001"
        payload = build_observation_output(build_shared_equity_history_request(trace_window=4), frame)
        print_observation("shared equity history payload", payload)

        self.assertIsInstance(payload, ObservationPayload)
        self.assertEqual(payload.meta["module"], "shared")
        self.assertEqual(payload.meta["function"], "equity.price.history")
        self.assertEqual(payload.meta["trace_window"], 4)
        self.assertEqual(payload.meta["row_count"], 4)
        self.assertEqual(payload.meta["code"], "000001")
        self.assertEqual(payload.latest_quote["close"], 106.0)
        self.assertTrue(payload.trace_points)
        self.assertTrue(payload.recent_events)

    def test_shared_history_lookup_uses_standard_supplement_interface(self) -> None:
        """共享命令的历史回补应优先走标准补充接口，而不是旧 provider 直连。"""

        request = build_shared_equity_history_request(trace_window=4)
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

        standard_result = type(
            "MockStandardResult",
            (),
            {"data": standard_rows},
        )()
        with patch(
            "efinance_cli.facade.CommandFacade.invoke",
            return_value=standard_result,
        ) as mock_invoke:
            frame = fetch_standard_history_for_request(request, "000001", "basic")

        print_observation("shared history lookup frame", frame.to_dict(orient="records") if frame is not None else None)
        self.assertIsInstance(frame, pd.DataFrame)
        self.assertEqual(list(frame["symbol"]), ["000001", "000001"])
        mock_invoke.assert_called_once()

    def test_supported_latest_command_can_render_observation_json(self) -> None:
        """最新行情 observation 模式应产出完整 JSON section。"""

        history_frame = build_history_frame()
        payload = build_observation_output(build_request(trace_window=4), history_frame)

        def fake_invoke(executor_self, request):
            self.assertEqual(request.spec.module_name, "common")
            self.assertEqual(request.spec.function_name, "get_latest_quote")
            self.assertEqual(request.output.view_mode, "observation")
            self.assertEqual(request.output.trace_window, 4)
            return InvocationResult(value=payload)

        with patch("efinance_cli.executor.CommandExecutor.invoke", new=fake_invoke):
            runner = CliRunner()
            cli = create_root_command()
            result = runner.invoke(
                cli,
                [
                    "quote",
                    "price",
                    "latest",
                    "--quote-ids",
                    "105.AAPL",
                    "--view",
                    "observation",
                    "--format",
                    "json",
                    "--trace-window",
                    "4",
                ],
            )

        print_observation("latest observation JSON 输出", result.output)
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn('"meta"', result.output)
        self.assertIn('"latest_quote"', result.output)
        self.assertIn('"trace_points"', result.output)
        self.assertIn('"recent_events"', result.output)

    def test_fund_history_multi_can_build_multi_source_observation(self) -> None:
        """fund get-quote-history-multi 应输出 source -> payload 映射。"""

        request = InvocationRequest(
            spec=CommandSpec(
                module_name="fund",
                function_name="get_quote_history_multi",
                callback=lambda **_: None,
                help_text="test",
            ),
            kwargs={},
            output=OutputOptions(
                format_name="table",
                indicator_level="full",
                view_mode="observation",
                trace_window=4,
            ),
        )
        value = {
            "161725": build_history_frame().rename(columns={"股票代码": "基金代码", "股票名称": "基金名称", "收盘": "单位净值"}),
            "005827": build_history_frame().rename(columns={"股票代码": "基金代码", "股票名称": "基金名称", "收盘": "单位净值"}),
        }

        payloads = build_observation_output(request, value)
        print_observation("fund history multi payloads", payloads)
        self.assertIsInstance(payloads, dict)
        self.assertEqual(set(payloads.keys()), {"161725", "005827"})
        self.assertTrue(all(isinstance(item, ObservationPayload) for item in payloads.values()))

    def test_single_row_snapshot_and_base_info_can_build_observation(self) -> None:
        """snapshot 与 base_info 应能走 single-row observation 组装。"""

        snapshot_row = pd.Series(
            {
                "代码": "AAPL",
                "名称": "Apple Inc.",
                "时间": "2026-05-28 15:00:00",
                "最新价": 106.0,
                "今开": 105.0,
                "最高": 107.0,
                "最低": 104.0,
                "成交量": 1800,
                "成交额": 190000.0,
                "涨跌幅": 1.2,
                "ma5": 103.0,
                "macd_dif": 0.36,
            }
        )
        stock_base_info_row = pd.Series(
            {
                "股票代码": "AAPL",
                "股票名称": "Apple Inc.",
                "市盈率(动)": 25.0,
            }
        )
        common_base_info_row = pd.Series(
            {
                "代码": "AAPL",
                "名称": "Apple Inc.",
                "行情ID": "105.AAPL",
            }
        )

        with patch("efinance_cli.observation.fetch_history_for_code", return_value=build_history_frame()), patch(
            "efinance_cli.observation.enrich_history_frame",
            side_effect=lambda frame, level: frame,
        ):
            snapshot_payload = build_observation_output(build_single_row_request("get_quote_snapshot"), snapshot_row)
            stock_base_payload = build_observation_output(build_single_row_request("get_base_info"), stock_base_info_row)
            common_base_payload = build_observation_output(build_single_row_request("get_base_info_common"), common_base_info_row)

        print_observation("snapshot payload", snapshot_payload)
        print_observation("stock base payload", stock_base_payload)
        print_observation("common base payload", common_base_payload)

        self.assertIsInstance(snapshot_payload, ObservationPayload)
        self.assertEqual(snapshot_payload.latest_quote["close"], 106.0)
        self.assertIsInstance(stock_base_payload, ObservationPayload)
        self.assertEqual(stock_base_payload.meta["code"], "AAPL")
        self.assertIsInstance(common_base_payload, ObservationPayload)
        self.assertEqual(common_base_payload.meta["code"], "105.AAPL")

    def test_realtime_list_can_build_multi_source_observation_with_default_limit(self) -> None:
        """realtime-list 应输出多 source observation，并受默认处理上限约束。"""

        self.assertIn(("stock", "get_realtime_quotes"), OBSERVATION_REALTIME_LIST_COMMANDS)
        request = InvocationRequest(
            spec=CommandSpec(
                module_name="stock",
                function_name="get_realtime_quotes",
                callback=lambda **_: None,
                help_text="test",
            ),
            kwargs={},
            output=OutputOptions(
                format_name="table",
                indicator_level="full",
                view_mode="observation",
                trace_window=4,
                limit=2,
            ),
        )
        frame = pd.DataFrame(
            [
                {"股票代码": "AAPL", "股票名称": "Apple Inc.", "最新价": 106.0, "行情ID": "105.AAPL"},
                {"股票代码": "MSFT", "股票名称": "Microsoft", "最新价": 421.0, "行情ID": "105.MSFT"},
                {"股票代码": "NVDA", "股票名称": "NVIDIA", "最新价": 980.0, "行情ID": "105.NVDA"},
            ]
        )

        def fake_fetch(module_name, code, level):
            sample = build_history_frame().copy()
            sample["股票代码"] = code.split(".")[-1] if "." in code else code
            sample["股票名称"] = code
            return sample

        with patch("efinance_cli.observation.fetch_history_for_code", side_effect=fake_fetch), patch(
            "efinance_cli.observation.enrich_history_frame",
            side_effect=lambda history, level: history,
        ):
            payloads = build_observation_output(request, frame)

        print_observation("realtime list payloads", payloads)
        self.assertIsInstance(payloads, dict)
        self.assertEqual(len(payloads), 2)
        self.assertEqual(set(payloads.keys()), {"AAPL", "MSFT"})

    def test_fund_history_multi_cli_can_render_multi_source_observation_formats(self) -> None:
        """fund get-quote-history-multi 应在多种格式下输出 multi-source observation。"""

        payloads = {
            "161725": build_observation_output(build_request(trace_window=4), build_history_frame()),
            "005827": build_observation_output(build_request(trace_window=4), build_history_frame()),
        }

        def fake_invoke(executor_self, request):
            self.assertEqual(request.spec.module_name, "fund")
            self.assertEqual(request.spec.function_name, "get_quote_history_multi")
            self.assertEqual(request.output.view_mode, "observation")
            return InvocationResult(value=payloads)

        with patch("efinance_cli.executor.CommandExecutor.invoke", new=fake_invoke):
            runner = CliRunner()
            cli = create_root_command()
            table_result = runner.invoke(
                cli,
                [
                    "fund",
                    "nav",
                    "history-batch",
                    "--symbols",
                    "161725",
                    "--symbols",
                    "005827",
                    "--view",
                    "observation",
                ],
            )
            json_result = runner.invoke(
                cli,
                [
                    "fund",
                    "nav",
                    "history-batch",
                    "--symbols",
                    "161725",
                    "--symbols",
                    "005827",
                    "--view",
                    "observation",
                    "--format",
                    "json",
                ],
            )
            csv_result = runner.invoke(
                cli,
                [
                    "fund",
                    "nav",
                    "history-batch",
                    "--symbols",
                    "161725",
                    "--symbols",
                    "005827",
                    "--view",
                    "observation",
                    "--format",
                    "csv",
                ],
            )
            tsv_result = runner.invoke(
                cli,
                [
                    "fund",
                    "nav",
                    "history-batch",
                    "--symbols",
                    "161725",
                    "--symbols",
                    "005827",
                    "--view",
                    "observation",
                    "--format",
                    "tsv",
                ],
            )

        print_observation("fund multi table", table_result.output)
        print_observation("fund multi json", json_result.output)
        print_observation("fund multi csv", csv_result.output)
        print_observation("fund multi tsv", tsv_result.output)

        self.assertEqual(table_result.exit_code, 0, msg=table_result.output)
        self.assertIn("| source.161725 |", table_result.output)
        self.assertIn("| source.005827 |", table_result.output)
        self.assertIn("| meta", table_result.output)
        self.assertNotIn("|               |\n+---------------+", table_result.output)

        self.assertEqual(json_result.exit_code, 0, msg=json_result.output)
        self.assertIn('"161725"', json_result.output)
        self.assertIn('"005827"', json_result.output)

        self.assertEqual(csv_result.exit_code, 0, msg=csv_result.output)
        self.assertIn("__source__", csv_result.output)
        self.assertIn("161725", csv_result.output)
        self.assertIn("005827", csv_result.output)

        self.assertEqual(tsv_result.exit_code, 0, msg=tsv_result.output)
        self.assertIn("__source__", tsv_result.output)

    def test_generic_dataframe_command_defaults_to_observation_sections(self) -> None:
        """未纳入行情契约的普通命令也应默认输出 observation sections。"""

        frame = pd.DataFrame(
            [
                {"code": "AAPL", "name": "Apple Inc.", "value": 1},
                {"code": "MSFT", "name": "Microsoft", "value": 2},
            ]
        )

        def fake_invoke(executor_self, request):
            self.assertEqual(request.spec.module_name, "stock")
            self.assertEqual(request.spec.function_name, "get_members")
            self.assertEqual(request.output.view_mode, "observation")
            return InvocationResult(value=build_observation_output(request, frame))

        with patch("efinance_cli.executor.CommandExecutor.invoke", new=fake_invoke):
            runner = CliRunner()
            cli = create_root_command()
            result = runner.invoke(cli, ["stock", "constituents", "--symbol", "000300"])

        print_observation("generic observation CLI 输出", result.output)
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("| meta", result.output)
        self.assertIn("| result", result.output)
        self.assertIn("Apple Inc.", result.output)

    def test_generic_command_can_explicitly_fallback_to_raw_view(self) -> None:
        """用户显式请求 raw 时，应保留原始 DataFrame 风格输出。"""

        frame = pd.DataFrame(
            [
                {"code": "AAPL", "name": "Apple Inc.", "value": 1},
                {"code": "MSFT", "name": "Microsoft", "value": 2},
            ]
        )

        def fake_invoke(executor_self, request):
            self.assertEqual(request.output.view_mode, "raw")
            return InvocationResult(value=frame)

        with patch("efinance_cli.executor.CommandExecutor.invoke", new=fake_invoke):
            runner = CliRunner()
            cli = create_root_command()
            result = runner.invoke(
                cli,
                ["stock", "constituents", "--symbol", "000300", "--view", "raw"],
            )

        print_observation("generic raw CLI 输出", result.output)
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertNotIn("| meta", result.output)
        self.assertIn("Apple Inc.", result.output)


if __name__ == "__main__":
    unittest.main()
