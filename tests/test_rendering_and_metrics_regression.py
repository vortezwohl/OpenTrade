"""渲染层与量化指标回归测试。

该文件专门覆盖两类风险：

- 输出格式层风险：表格、JSON、CSV、TSV、长文本和宽列展示是否稳定；
- 指标计算层风险：关键量化指标是否能在可手算样本上给出一致结果。
"""

from __future__ import annotations

import json
import unittest

import pandas as pd

from efinance_cli import indicators
from efinance_cli.models import (
    ObservationEvent,
    ObservationPayload,
    ObservationSection,
    ObservationTraceGroup,
    OutputOptions,
)
from efinance_cli.rendering import render_csv, render_json, render_table, render_value
from tests.cli_regression_support import print_observation


def build_wide_frame() -> pd.DataFrame:
    """构造包含长文本与宽列名的表格样本。"""

    return pd.DataFrame(
        [
            {
                "证券代码": "000001",
                "证券名称": "平安银行",
                "超长说明列": "这是一个用于验证表格列宽裁剪与完整输出切换行为的长文本字段",
                "特别宽的列名用于验证输出宽度弹性是否足够": "宽列值-1",
            },
            {
                "证券代码": "600519",
                "证券名称": "贵州茅台",
                "超长说明列": "第二行同样保留较长内容，防止只对单行场景表现正常",
                "特别宽的列名用于验证输出宽度弹性是否足够": "宽列值-2",
            },
        ]
    )


def build_observation_payload() -> ObservationPayload:
    """构造稳定的 observation payload 样本。"""

    return ObservationPayload(
        meta={
            "module": "common",
            "function": "get_latest_quote",
            "view": "observation",
            "indicator_level": "full",
            "trace_window": 8,
            "code": "105.AAPL",
            "name": "Apple Inc.",
            "as_of": "2026-05-28 15:00:00",
        },
        latest_quote={
            "code": "105.AAPL",
            "name": "Apple Inc.",
            "close": 201.23,
            "change_pct": 1.28,
        },
        current_metrics={
            "close": 201.23,
            "ma5": 199.81,
            "ma10": 198.57,
            "macd_dif": 1.21,
            "macd_dea": 1.18,
            "rsi14": 58.42,
        },
        trace_points=[
            ObservationTraceGroup(
                name="price_ma",
                points=[
                    {"bar_offset": -3, "close": 198.11, "ma5": 197.82, "ma10": 197.44},
                    {"bar_offset": -2, "close": 199.32, "ma5": 198.21, "ma10": 197.91},
                    {"bar_offset": -1, "close": 200.45, "ma5": 199.02, "ma10": 198.20},
                    {"bar_offset": 0, "close": 201.23, "ma5": 199.81, "ma10": 198.57},
                ],
            ),
        ],
        recent_events=[
            ObservationEvent(
                bars_ago=-1,
                event_key="macd_dif_crossed_above_macd_dea",
                subject_a="macd_dif",
                relation="crossed_above",
                subject_b="macd_dea",
                prev_a=1.12,
                prev_b=1.15,
                curr_a=1.21,
                curr_b=1.18,
                description="macd_dif moved from below to above macd_dea",
            ),
            ObservationEvent(
                bars_ago=-3,
                event_key="ma5_crossed_above_ma10",
                subject_a="ma5",
                relation="crossed_above",
                subject_b="ma10",
                prev_a=195.2,
                prev_b=195.4,
                curr_a=195.8,
                curr_b=195.7,
                description="ma5 moved from below to above ma10",
            ),
        ],
        sections=[],
    )


def build_observation_payload_mapping() -> dict[str, ObservationPayload]:
    """构造稳定的多 source observation payload 样本。"""

    left = build_observation_payload()
    right = build_observation_payload()
    right.meta = {**right.meta, "code": "105.MSFT", "name": "Microsoft"}
    right.latest_quote = {**right.latest_quote, "code": "105.MSFT", "name": "Microsoft", "close": 421.5}
    return {
        "105.AAPL": left,
        "105.MSFT": right,
    }


class RenderingAndMetricsRegressionTest(unittest.TestCase):
    """覆盖渲染与指标计算的关键回归场景。"""

    def test_table_rendering_handles_wide_columns(self) -> None:
        """默认表格输出应能稳定展示宽列，不出现异常。"""

        frame = build_wide_frame()
        text = render_table(frame, OutputOptions())
        print_observation("默认表格渲染", text)
        self.assertIn("证券代码", text)
        self.assertIn("平安银行", text)
        self.assertGreaterEqual(len(text.splitlines()), 3)

    def test_full_table_rendering_preserves_long_text(self) -> None:
        """开启 full 后不应截断长文本。"""

        frame = build_wide_frame()
        text = render_table(frame, OutputOptions(full=True))
        print_observation("full 表格渲染", text)
        self.assertIn("用于验证表格列宽裁剪与完整输出切换行为的长文本字段", text)

    def test_transpose_and_no_index_rendering(self) -> None:
        """转置与隐藏索引应共同生效。"""

        frame = build_wide_frame()[["证券代码", "证券名称"]]
        text = render_table(frame, OutputOptions(transpose=True, no_index=True))
        print_observation("转置且隐藏索引渲染", text)
        self.assertIn("000001", text)
        self.assertIn("600519", text)
        self.assertNotIn("证券代码", text.splitlines()[0])

    def test_json_rendering_keeps_chinese_and_structure(self) -> None:
        """JSON 输出应保留中文并具备可解析结构。"""

        frame = build_wide_frame()
        text = render_json(frame)
        print_observation("JSON 渲染", text)
        payload = json.loads(text)
        self.assertEqual(payload[0]["证券代码"], "000001")
        self.assertEqual(payload[1]["证券名称"], "贵州茅台")

    def test_csv_and_tsv_rendering_are_structurally_correct(self) -> None:
        """CSV 与 TSV 输出应包含正确分隔符和表头。"""

        frame = build_wide_frame()[["证券代码", "证券名称"]]
        csv_text = render_csv(frame, OutputOptions(no_index=True))
        tsv_text = render_csv(frame, OutputOptions(no_index=True), sep="\t")
        print_observation("CSV 渲染", csv_text)
        print_observation("TSV 渲染", tsv_text)

        self.assertTrue(csv_text.startswith("证券代码,证券名称"))
        self.assertIn("000001,平安银行", csv_text)
        self.assertTrue(tsv_text.startswith("证券代码\t证券名称"))
        self.assertIn("600519\t贵州茅台", tsv_text)

    def test_csv_and_tsv_default_output_do_not_leak_dataframe_index(self) -> None:
        """CSV 与 TSV 默认应直接导出数据列，避免空索引列破坏可读性。"""

        frame = build_wide_frame()[["证券代码", "证券名称"]]
        csv_text = render_csv(frame, OutputOptions(format_name="csv"))
        tsv_text = render_csv(frame, OutputOptions(format_name="tsv"), sep="\t")
        print_observation("CSV 默认导出", csv_text)
        print_observation("TSV 默认导出", tsv_text)

        self.assertTrue(csv_text.startswith("证券代码,证券名称"))
        self.assertFalse(csv_text.startswith(","))
        self.assertTrue(tsv_text.startswith("证券代码\t证券名称"))
        self.assertFalse(tsv_text.startswith("\t"))

    def test_limit_option_restricts_rendered_rows(self) -> None:
        """表格模式下的行数裁剪应只保留前 N 行。"""

        frame = build_wide_frame()
        text = render_value(frame, OutputOptions(format_name="table", limit=1))
        print_observation("limit=1 渲染", text)
        self.assertIn("平安银行", text)
        self.assertNotIn("贵州茅台", text)

    def test_mapping_rendering_keeps_section_boundaries(self) -> None:
        """字典渲染应保留分节边界，避免多块结果混成一团。"""

        frame = build_wide_frame()[["证券代码"]]
        text = render_table({"第一组": frame.head(1), "第二组": frame.tail(1)}, OutputOptions())
        print_observation("字典分段渲染", text)
        self.assertIn("== 第一组 ==", text)
        self.assertIn("== 第二组 ==", text)

    def test_observation_table_uses_boxed_vertical_layout(self) -> None:
        """observation table 应使用规整 boxed section，并保留完整 section 信息。"""

        payload = build_observation_payload()
        text = render_table(payload, OutputOptions())
        print_observation("observation table 渲染", text)

        self.assertIn("+", text)
        self.assertIn("| meta", text)
        self.assertIn("| current_metrics", text)
        self.assertIn("| trace_points.price_ma", text)
        self.assertIn("| recent_events", text)
        self.assertIn("[1] bars_ago: -1", text)
        self.assertIn("event_key: macd_dif_crossed_above_macd_dea", text)

        for line in text.splitlines():
            if line.startswith("|"):
                self.assertTrue(line.endswith("|"), msg=line)

    def test_observation_json_and_long_form_csv_keep_same_signal_information(self) -> None:
        """observation 的 JSON 与 CSV/TSV 应保留相同核心 section 信息。"""

        payload = build_observation_payload()
        json_text = render_json(payload)
        csv_text = render_csv(payload, OutputOptions(no_index=True))
        tsv_text = render_csv(payload, OutputOptions(no_index=True), sep="\t")
        print_observation("observation JSON 渲染", json_text)
        print_observation("observation CSV 渲染", csv_text)
        print_observation("observation TSV 渲染", tsv_text)

        data = json.loads(json_text)
        self.assertIn("trace_points", data)
        self.assertIn("recent_events", data)
        self.assertEqual(data["meta"]["trace_window"], 8)

        self.assertIn("section,item_type,item_id,group,bar_offset,event_index,event_key,relation,bars_ago,field,value", csv_text)
        self.assertIn("trace_points,trace_point,price_ma,price_ma,-1", csv_text)
        self.assertIn("recent_events,event,event_1", csv_text)
        self.assertIn("macd_dif_crossed_above_macd_dea", csv_text)
        self.assertIn("section\titem_type\titem_id\tgroup\tbar_offset", tsv_text)

    def test_multi_source_observation_table_and_csv_keep_source_boundaries(self) -> None:
        """多 source observation 应保留 source 分组和 `__source__`。"""

        payloads = build_observation_payload_mapping()
        table_text = render_table(payloads, OutputOptions())
        csv_text = render_csv(payloads, OutputOptions(no_index=True))
        print_observation("multi-source observation table", table_text)
        print_observation("multi-source observation csv", csv_text)

        self.assertIn("| source.105.AAPL", table_text)
        self.assertIn("| source.105.MSFT", table_text)
        self.assertIn("| recent_events", table_text)
        self.assertIn("__source__", csv_text)
        self.assertIn("105.AAPL,meta,field,module", csv_text)
        self.assertIn("105.MSFT,meta,field,module", csv_text)

    def test_generic_observation_sections_render_across_formats(self) -> None:
        """通用 observation sections 应在四种格式下保持可读与可消费。"""

        payload = ObservationPayload(
            meta={
                "module": "stock",
                "function": "get_members",
                "view": "observation",
                "result_type": "DataFrame",
            },
            latest_quote={},
            current_metrics={},
            trace_points=[],
            recent_events=[],
            sections=[
                ObservationSection(
                    name="result",
                    rows=[
                        {"code": "AAPL", "name": "Apple Inc.", "value": 1},
                        {"code": "MSFT", "name": "Microsoft", "value": 2},
                    ],
                    render_hint="records",
                )
            ],
        )
        table_text = render_table(payload, OutputOptions())
        json_text = render_json(payload)
        csv_text = render_csv(payload, OutputOptions(no_index=True))
        tsv_text = render_csv(payload, OutputOptions(no_index=True), sep="\t")
        print_observation("generic observation table", table_text)
        print_observation("generic observation json", json_text)
        print_observation("generic observation csv", csv_text)
        print_observation("generic observation tsv", tsv_text)

        self.assertIn("| result[1]", table_text)
        self.assertIn("| result[2]", table_text)
        self.assertIn("Apple Inc.", table_text)
        self.assertIn('"sections"', json_text)
        self.assertIn('"name": "result"', json_text)
        self.assertIn("result,section_row,result_1", csv_text)
        self.assertIn("Apple Inc.", csv_text)
        self.assertIn("result\tsection_row\tresult_1", tsv_text)

    def test_obv_matches_hand_calculated_values(self) -> None:
        """OBV 应与手工累加结果一致。"""

        close = pd.Series([10.0, 11.0, 10.5, 10.5, 12.0])
        volume = pd.Series([100, 120, 80, 50, 200])
        result = indicators.obv(close, volume)
        expected = pd.Series([0, 120, 40, 40, 240], dtype="float64")
        print_observation("OBV 实际结果", result.to_list())
        pd.testing.assert_series_equal(result.reset_index(drop=True), expected, check_names=False)

    def test_vwap_matches_cumulative_weighted_average(self) -> None:
        """VWAP 应符合成交量加权平均公式。"""

        high = pd.Series([11.0, 12.0, 13.0])
        low = pd.Series([9.0, 10.0, 11.0])
        close = pd.Series([10.0, 11.0, 12.0])
        volume = pd.Series([100, 200, 100])
        result = indicators.vwap(high, low, close, volume)
        expected = pd.Series([10.0, 10.6666666667, 11.0])
        print_observation("VWAP 实际结果", result.round(6).to_list())
        pd.testing.assert_series_equal(
            result.round(6).reset_index(drop=True),
            expected.round(6),
            check_names=False,
        )

    def test_pivot_points_match_manual_formula(self) -> None:
        """Pivot Points 关键数值应与手工公式一致。"""

        high = pd.Series([10.0])
        low = pd.Series([8.0])
        close = pd.Series([9.0])
        result = indicators.pivot_points(high, low, close)
        row = result.iloc[0]
        print_observation("Pivot Points 实际结果", row.to_dict())

        self.assertEqual(row["pivot"], 9.0)
        self.assertEqual(row["r1"], 10.0)
        self.assertEqual(row["s1"], 8.0)
        self.assertEqual(row["r2"], 11.0)
        self.assertEqual(row["s2"], 7.0)
        self.assertEqual(row["r3"], 12.0)
        self.assertEqual(row["s3"], 6.0)

    def test_bias_matches_percentage_distance_from_moving_average(self) -> None:
        """BIAS 应等于价格偏离均线的百分比。"""

        values = pd.Series([10.0, 11.0, 12.0])
        result = indicators.bias(values, period=3)
        expected_last = (12.0 - 11.0) / 11.0 * 100
        print_observation("BIAS 实际结果", result.to_list())
        self.assertAlmostEqual(result.iloc[-1], expected_last)

    def test_output_width_stress_does_not_raise(self) -> None:
        """长文本宽列表格至少应稳定返回字符串，不因宽度问题崩溃。"""

        frame = pd.DataFrame(
            {
                "列一": ["X" * 200],
                "列二": ["Y" * 200],
                "列三": ["Z" * 200],
            }
        )
        text = render_table(frame, OutputOptions())
        print_observation("宽度压力渲染", text)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)


if __name__ == "__main__":
    unittest.main()
