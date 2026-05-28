"""CLI 命令面与参数行为回归测试。

该测试文件通过对执行层和部分外部依赖做打桩，验证：

- 全部叶子命令都能构建并执行到调度层；
- 动态反射出来的参数能被 Click 正确解析并透传；
- 顶层 `search` 和 `watch` 的包装逻辑稳定可用；
- 统一运行时参数在修复后不再出现静默改写。
"""

from __future__ import annotations

import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import click
import pandas as pd
from click.testing import CliRunner

from efinance_cli.commands import create_root_command
from efinance_cli.models import InvocationResult
from efinance_cli.registry import build_command_specs
from tests.cli_regression_support import (
    RUNTIME_OUTPUT_OPTION_NAMES,
    RUNTIME_WATCH_OPTION_NAMES,
    build_option_cases,
    build_required_tokens,
    build_search_records,
    collect_leaf_commands,
    count_all_parameters,
    print_observation,
)


class CliFullRegressionTest(unittest.TestCase):
    """覆盖全部 CLI 命令与参数的回归测试。"""

    def setUp(self) -> None:
        """构建测试所需的命令树与运行器。"""

        self.runner = CliRunner()
        self.cli = create_root_command()
        self.leaf_commands = collect_leaf_commands(self.cli)

    def test_all_leaf_commands_execute_without_unhandled_exception(self) -> None:
        """全部叶子命令在最小参数下都应能执行到调度层。"""

        captured_requests = []

        def fake_run(executor_self, request) -> None:
            captured_requests.append(request)
            click.echo(f"EXECUTED:{request.spec.module_name}.{request.spec.function_name}")

        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            for leaf in self.leaf_commands:
                if leaf.path[0] in {"search", "watch"}:
                    continue
                result = self.runner.invoke(self.cli, build_required_tokens(leaf))
                print_observation(f"{leaf.dotted_path} CLI 输出", result.output)
                self.assertEqual(
                    result.exit_code,
                    0,
                    msg=f"{leaf.dotted_path} 执行失败:\n{result.output}",
                )
                self.assertIn("EXECUTED:", result.output, msg=leaf.dotted_path)

        expected = len([leaf for leaf in self.leaf_commands if leaf.path[0] not in {"search", "watch"}])
        self.assertEqual(len(captured_requests), expected)

    def test_all_options_can_be_parsed_and_forwarded(self) -> None:
        """全部选项参数都应能被解析，并在需要时透传到请求对象。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            for leaf in self.leaf_commands:
                if leaf.path[0] in {"search", "watch"}:
                    continue
                for parameter in leaf.command.params:
                    if not isinstance(parameter, click.Option):
                        continue
                    for tokens, expected_value in build_option_cases(parameter, base_dir):
                        captured = {}

                        def fake_run(executor_self, request) -> None:
                            captured["request"] = request
                            click.echo("OK")

                        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
                            argv = build_required_tokens(leaf) + tokens
                            result = self.runner.invoke(self.cli, argv)
                        print_observation(f"{leaf.dotted_path} 参数 {tokens} CLI 输出", result.output)

                        self.assertEqual(
                            result.exit_code,
                            0,
                            msg=f"{leaf.dotted_path} 参数 {tokens} 解析失败:\n{result.output}",
                        )
                        request = captured["request"]
                        option_name = parameter.name

                        if option_name in RUNTIME_OUTPUT_OPTION_NAMES:
                            actual = getattr(request.output, option_name)
                        elif option_name in RUNTIME_WATCH_OPTION_NAMES:
                            if option_name == "watch":
                                mapped_name = "enabled"
                            elif option_name in {"count_refresh", "count_refresh_alias"}:
                                mapped_name = "count"
                            else:
                                mapped_name = option_name
                            actual = getattr(request.watch, mapped_name)
                        else:
                            actual = request.kwargs[option_name]

                        print_observation(
                            f"{leaf.dotted_path} 参数 {tokens} 实际值",
                            {"actual": actual, "expected": expected_value},
                        )
                        if option_name == "output_path":
                            self.assertEqual(Path(actual), Path(expected_value))
                        else:
                            self.assertEqual(
                                actual,
                                expected_value,
                                msg=f"{leaf.dotted_path} 参数 {tokens} 实际值不符",
                            )

    def test_all_leaf_commands_support_four_output_formats(self) -> None:
        """全部叶子命令都应能稳定走通 table/json/csv/tsv 四种输出格式。"""

        rendered_cases: list[tuple[str, str, str]] = []

        def fake_run(executor_self, request) -> None:
            rendered_cases.append(
                (
                    f"{request.spec.module_name}.{request.spec.function_name}",
                    request.output.format_name,
                    request.output.view_mode,
                )
            )
            click.echo(
                f"FORMAT:{request.spec.module_name}.{request.spec.function_name}:{request.output.format_name}:{request.output.view_mode}"
            )

        formats = ("table", "json", "csv", "tsv")
        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            for leaf in self.leaf_commands:
                if leaf.path[0] in {"search", "watch"}:
                    continue
                for format_name in formats:
                    argv = build_required_tokens(leaf) + ["--format", format_name]
                    result = self.runner.invoke(self.cli, argv)
                    print_observation(f"{leaf.dotted_path} format={format_name} 输出", result.output)
                    self.assertEqual(
                        result.exit_code,
                        0,
                        msg=f"{leaf.dotted_path} format={format_name} 执行失败:\n{result.output}",
                    )
                    self.assertIn(
                        f"FORMAT:{leaf.path[0]}.{leaf.command.name.replace('-', '_')}:{format_name}:observation",
                        result.output,
                    )

        expected = len([leaf for leaf in self.leaf_commands if leaf.path[0] not in {"search", "watch"}]) * len(formats)
        self.assertEqual(len(rendered_cases), expected)

    def test_watch_wrapper_forwards_refresh_flags(self) -> None:
        """顶层 watch 包装命令应向子命令转发刷新参数。"""

        forwarded = {}

        def fake_main(*args, **kwargs) -> None:
            forwarded["args"] = list(kwargs["args"])
            forwarded["prog_name"] = kwargs["prog_name"]
            forwarded["standalone_mode"] = kwargs.get("standalone_mode")

        watch_command = self.cli.commands["watch"]
        watch_context = click.Context(
            watch_command,
            info_name="watch",
            parent=click.Context(self.cli, info_name="cli"),
        )
        watch_context.args = ["common", "get-latest-quote", "105.AAPL", "--format", "json"]

        with patch.object(self.cli, "main", new=fake_main):
            with watch_context:
                watch_command.callback(  # type: ignore[misc]
                    interval=0.5,
                    count=2,
                    clear_screen=False,
                )

        print_observation("watch 包装转发参数", forwarded)
        self.assertEqual(
            forwarded["args"],
            [
                "common",
                "get-latest-quote",
                "105.AAPL",
                "--format",
                "json",
                "--watch",
                "--interval",
                "0.5",
                "--count",
                "2",
                "--no-clear",
            ],
        )
        self.assertFalse(forwarded["standalone_mode"])

    def test_search_command_works_with_mocked_search_backend(self) -> None:
        """顶层 search 在替换后的可调用对象场景下也应能正常工作。"""

        records = build_search_records()
        with patch("efinance.utils.search_quote", return_value=records):
            result = self.runner.invoke(self.cli, ["search", "AAPL"])

        print_observation("search 默认输出", result.output)
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Apple Inc.", result.output)
        self.assertIn("105.AAPL", result.output)

    def test_search_rendering_pipeline_behaves_as_expected(self) -> None:
        """search 的输出控制参数应能正常工作。"""

        records = build_search_records()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "search-output.json"
            with patch("efinance.utils.search_quote", return_value=records):
                table_result = self.runner.invoke(self.cli, ["search", "AAPL"])
                json_result = self.runner.invoke(self.cli, ["search", "AAPL", "--format", "json"])
                limited_result = self.runner.invoke(
                    self.cli,
                    ["search", "AAPL", "--format", "table", "--limit", "1"],
                )
                output_result = self.runner.invoke(
                    self.cli,
                    ["search", "AAPL", "--format", "json", "--output", str(output_path)],
                )
                output_exists = output_path.exists()
                output_content = output_path.read_text(encoding="utf-8") if output_exists else ""

        print_observation("search 表格输出", table_result.output)
        print_observation("search JSON 输出", json_result.output)
        print_observation("search limit=1 输出", limited_result.output)
        print_observation("search 输出文件内容", output_content)
        self.assertEqual(table_result.exit_code, 0, msg=table_result.output)
        self.assertIn("Apple Inc.", table_result.output)
        self.assertIn("105.AAPL", table_result.output)

        self.assertEqual(json_result.exit_code, 0, msg=json_result.output)
        self.assertIn('"code": "AAPL"', json_result.output)
        self.assertIn('"quote_id": "105.AAPL"', json_result.output)

        self.assertEqual(limited_result.exit_code, 0, msg=limited_result.output)
        self.assertIn("Apple Inc.", limited_result.output)
        self.assertNotIn("Microsoft", limited_result.output)

        self.assertEqual(output_result.exit_code, 0, msg=output_result.output)
        self.assertTrue(output_exists)
        self.assertIn('"code": "AAPL"', output_content)

    def test_search_watch_mode_uses_executor(self) -> None:
        """search 的 watch 模式应切换到统一执行器路径。"""

        captured = {}
        records = build_search_records()

        def fake_run(executor_self, request) -> None:
            captured["request"] = request
            click.echo("WATCHING")

        with patch("efinance.utils.search_quote", return_value=records), patch(
            "efinance_cli.executor.CommandExecutor.run",
            new=fake_run,
        ):
            result = self.runner.invoke(
                self.cli,
                ["search", "AAPL", "--watch", "--count", "2", "--interval", "0.1"],
            )

        print_observation("search watch 输出", result.output)
        print_observation(
            "search watch 请求参数",
            {
                "enabled": captured["request"].watch.enabled,
                "count": captured["request"].watch.count,
                "interval": captured["request"].watch.interval,
            },
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("WATCHING", result.output)
        self.assertTrue(captured["request"].watch.enabled)
        self.assertEqual(captured["request"].watch.count, 2)
        self.assertAlmostEqual(captured["request"].watch.interval, 0.1)
        self.assertEqual(captured["request"].output.indicator_level, "advanced")

    def test_utils_search_quote_result_count_routes_to_business_parameter_without_runtime_warning(self) -> None:
        """utils search-quote 应把业务候选数量暴露为 result-count，而不是复用运行时 count。"""

        captured = {}

        def fake_run(executor_self, request) -> None:
            captured["request"] = request
            click.echo("OK")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
                result = self.runner.invoke(
                    self.cli,
                    ["utils", "search-quote", "AAPL", "--result-count", "1", "--format", "json"],
                )

        print_observation("utils search-quote result-count 输出", result.output)
        print_observation(
            "utils search-quote 路由结果",
            {
                "business_result_count": captured["request"].kwargs["result_count"],
                "watch_count": captured["request"].watch.count,
                "warnings": [str(item.message) for item in caught],
            },
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertEqual(captured["request"].kwargs["result_count"], 1)
        self.assertIsNone(captured["request"].watch.count)
        self.assertFalse(
            any("parameter --count is used more than once" in str(item.message).lower() for item in caught),
            msg=[str(item.message) for item in caught],
        )

    def test_utils_search_quote_result_count_is_normalized_before_callback(self) -> None:
        """utils search-quote 的 result-count 在执行前应被归一化为整数。"""

        with patch("efinance.utils.search_quote", return_value=build_search_records()) as mock_search:
            result = self.runner.invoke(
                self.cli,
                ["utils", "search-quote", "AAPL", "--result-count", "1", "--format", "json"],
            )

        print_observation("utils search-quote invoke 输出", result.output)
        print_observation("utils search-quote invoke kwargs", mock_search.call_args.kwargs)
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertEqual(mock_search.call_args.kwargs["count"], 1)

    def test_transpose_and_no_index_are_forwarded_to_search_emit(self) -> None:
        """search 的输出控制参数应透传给渲染层。"""

        captured = {}
        records = build_search_records()

        def fake_emit(executor_self, request, result: InvocationResult) -> None:
            captured["request"] = request
            captured["result"] = result
            click.echo("EMITTED")

        with patch("efinance.utils.search_quote", return_value=records), patch(
            "efinance_cli.executor.CommandExecutor._emit",
            new=fake_emit,
        ):
            result = self.runner.invoke(
                self.cli,
                ["search", "AAPL", "--transpose", "--no-index", "--full"],
            )

        print_observation("search emit 输出", result.output)
        print_observation(
            "search emit 输出选项",
            {
                "transpose": captured["request"].output.transpose,
                "no_index": captured["request"].output.no_index,
                "full": captured["request"].output.full,
            },
        )
        print_observation(
            "search emit DataFrame",
            captured["result"].value.to_string(index=False),
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("EMITTED", result.output)
        self.assertTrue(captured["request"].output.transpose)
        self.assertTrue(captured["request"].output.no_index)
        self.assertTrue(captured["request"].output.full)
        self.assertIsInstance(captured["result"].value, pd.DataFrame)

    def test_utils_command_specs_survive_mocked_callables(self) -> None:
        """utils 模块命令规格在 mock / wrapper 场景下不应丢失。"""

        records = build_search_records()
        with patch("efinance.utils.search_quote", return_value=records):
            function_names = {spec.function_name for spec in build_command_specs("utils")}

        print_observation("utils 命令规格函数名", sorted(function_names))
        self.assertIn("search_quote", function_names)

    def test_command_and_parameter_inventory_is_nontrivial(self) -> None:
        """保护命令树规模，避免命令注册意外塌缩。"""

        print_observation(
            "命令与参数规模",
            {
                "leaf_commands": len(self.leaf_commands),
                "parameters": count_all_parameters(self.leaf_commands),
            },
        )
        self.assertGreaterEqual(len(self.leaf_commands), 35)
        self.assertGreaterEqual(count_all_parameters(self.leaf_commands), 400)

    def test_watch_without_subcommand_raises_click_exception(self) -> None:
        """watch 缺少子命令时应返回可读错误。"""

        result = self.runner.invoke(self.cli, ["watch"])
        print_observation("watch 缺少子命令输出", result.output)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("watch must be followed by a full subcommand", result.output)

    def test_unsupported_market_name_returns_readable_error(self) -> None:
        """search 的非法 market 参数应返回可读错误。"""

        result = self.runner.invoke(self.cli, ["search", "AAPL", "--market", "UNKNOWN"])
        print_observation("search 非法 market 输出", result.output)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Unknown market enum", result.output)


if __name__ == "__main__":
    unittest.main()
