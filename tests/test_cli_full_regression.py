"""CLI 命令面与参数行为回归测试。

该测试文件通过对执行层和部分外部依赖做打桩，验证：

- 全部叶子命令都能构建并执行到调度层；
- 动态反射出来的参数能被 Click 正确解析并透传；
- 顶层 `search` 和 `watch` 的包装逻辑稳定可用；
- 统一运行时参数在重构后不再出现静默改写。
"""

from __future__ import annotations

import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import click
from click.testing import CliRunner

from efinance_cli.commands import create_root_command
from efinance_cli.registry import build_command_specs
from tests.cli_regression_support import (
    RUNTIME_EXECUTION_OPTION_NAMES,
    RUNTIME_OUTPUT_OPTION_NAMES,
    RUNTIME_WATCH_OPTION_NAMES,
    build_all_optional_option_tokens,
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
        """构建测试所需的命令树。"""
        self.runner = CliRunner()
        self.cli = create_root_command()
        self.leaf_commands = collect_leaf_commands(self.cli)

    def test_all_command_help_pages_render_successfully(self) -> None:
        """根命令、分组命令和叶子命令的帮助页都应稳定可达。"""
        command_paths = [()]
        command_paths.extend((name,) for name in self.cli.commands)
        for leaf in self.leaf_commands:
            for depth in range(1, len(leaf.path) + 1):
                path = leaf.path[:depth]
                if path not in command_paths:
                    command_paths.append(path)

        for path in command_paths:
            result = self.runner.invoke(self.cli, [*path, "--help"])
            title = "root --help" if not path else f"{' '.join(path)} --help"
            print_observation(title, result.output)
            self.assertEqual(result.exit_code, 0, msg=f"{title} 执行失败:\n{result.output}")
            self.assertIn("--help", result.output, msg=title)

            if path == ():
                self.assertIn("Commands:", result.output)
                self.assertIn("stock", result.output)
                self.assertIn("search", result.output)
                continue

            if path == ("watch",):
                self.assertIn("--interval", result.output)
                self.assertIn("--clear / --no-clear", result.output)
                continue

            if path == ("search",):
                self.assertIn("--query", result.output)
                self.assertIn("--format", result.output)
                self.assertIn("local", result.output)
                continue

            if len(path) == len(next((leaf.path for leaf in self.leaf_commands if leaf.path == path), ())):
                self.assertIn("--format", result.output)
                self.assertIn("--indicator-level", result.output)
                self.assertIn("--watch", result.output)

    def test_runtime_option_bundle_can_be_combined_on_all_leaf_commands(self) -> None:
        """常用运行时参数组合在全部叶子命令上都应能同时解析。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "bundle-output.txt")
            captured_requests = []

            def fake_run(executor_self, request) -> None:
                captured_requests.append(request)
                click.echo("BUNDLE_OK")

            runtime_bundle = [
                "--format",
                "json",
                "--full",
                "--transpose",
                "--no-index",
                "--limit",
                "1",
                "--output",
                output_path,
                "--encoding",
                "utf-8",
                "--indicator-level",
                "full",
                "--view",
                "raw",
                "--trace-window",
                "8",
                "--watch",
                "--interval",
                "0.1",
                "--count",
                "1",
                "--no-clear",
            ]

            with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
                for leaf in self.leaf_commands:
                    if leaf.path[0] in {"search", "watch"}:
                        continue
                    argv = build_required_tokens(leaf) + runtime_bundle
                    result = self.runner.invoke(self.cli, argv)
                    print_observation(f"{leaf.dotted_path} runtime bundle 输出", result.output)
                    self.assertEqual(
                        result.exit_code,
                        0,
                        msg=f"{leaf.dotted_path} 运行时组合参数失败:\n{result.output}",
                    )
                    self.assertIn("BUNDLE_OK", result.output)

            expected = len(
                [leaf for leaf in self.leaf_commands if leaf.path[0] not in {"search", "watch"}]
            )
            self.assertEqual(len(captured_requests), expected)
            for request in captured_requests:
                self.assertEqual(request.output.format_name, "json")
                self.assertTrue(request.output.full)
                self.assertTrue(request.output.transpose)
                self.assertTrue(request.output.no_index)
                self.assertEqual(request.output.limit, 1)
                self.assertEqual(request.output.output_path, output_path)
                self.assertEqual(request.output.encoding, "utf-8")
                self.assertEqual(request.output.indicator_level, "full")
                self.assertEqual(request.output.view_mode, "raw")
                self.assertEqual(request.output.trace_window, 8)
                self.assertTrue(request.watch.enabled)
                self.assertEqual(request.watch.interval, 0.1)
                self.assertEqual(request.watch.count, 1)
                self.assertFalse(request.watch.clear_screen)

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

        expected = len(
            [leaf for leaf in self.leaf_commands if leaf.path[0] not in {"search", "watch"}]
        )
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
                            argv = build_required_tokens(
                                leaf,
                                exclude_option_names={parameter.name} if parameter.required else None,
                            ) + tokens
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
                            mapped_name = "enabled" if option_name == "watch" else option_name
                            actual = getattr(request.watch, mapped_name)
                        elif option_name in RUNTIME_EXECUTION_OPTION_NAMES:
                            actual = request.backend_selection.resolved.value
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
                        f"FORMAT:{rendered_cases[-1][0]}:{format_name}:observation",
                        result.output,
                    )

        expected = (
            len([leaf for leaf in self.leaf_commands if leaf.path[0] not in {"search", "watch"}])
            * len(formats)
        )
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
        watch_context.args = [
            "quote",
            "price",
            "latest",
            "--quote-ids",
            "105.AAPL",
            "--format",
            "json",
        ]

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
                "quote",
                "price",
                "latest",
                "--quote-ids",
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
            result = self.runner.invoke(self.cli, ["search", "--query", "AAPL"])

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
                table_result = self.runner.invoke(self.cli, ["search", "--query", "AAPL"])
                json_result = self.runner.invoke(
                    self.cli,
                    ["search", "--query", "AAPL", "--format", "json"],
                )
                raw_json_result = self.runner.invoke(
                    self.cli,
                    ["search", "--query", "AAPL", "--format", "json", "--view", "raw"],
                )
                limited_result = self.runner.invoke(
                    self.cli,
                    ["search", "--query", "AAPL", "--format", "table", "--limit", "1"],
                )
                output_result = self.runner.invoke(
                    self.cli,
                    ["search", "--query", "AAPL", "--format", "json", "--output", str(output_path)],
                )
                output_exists = output_path.exists()
                output_content = output_path.read_text(encoding="utf-8") if output_exists else ""

        print_observation("search 表格输出", table_result.output)
        print_observation("search JSON 输出", json_result.output)
        print_observation("search raw JSON 输出", raw_json_result.output)
        print_observation("search limit=1 输出", limited_result.output)
        print_observation("search 输出文件内容", output_content)

        self.assertEqual(table_result.exit_code, 0, msg=table_result.output)
        self.assertIn("| meta", table_result.output)
        self.assertIn("| result[1]", table_result.output)
        self.assertIn("Apple Inc.", table_result.output)
        self.assertIn("105.AAPL", table_result.output)

        self.assertEqual(json_result.exit_code, 0, msg=json_result.output)
        self.assertIn('"meta"', json_result.output)
        self.assertIn('"sections"', json_result.output)
        self.assertIn('"code": "AAPL"', json_result.output)
        self.assertIn('"quote_id": "105.AAPL"', json_result.output)

        self.assertEqual(raw_json_result.exit_code, 0, msg=raw_json_result.output)
        self.assertIn('"contract_name": "search-results"', raw_json_result.output)
        self.assertIn('"raw_payload"', raw_json_result.output)
        self.assertIn('"provider_fields"', raw_json_result.output)

        self.assertEqual(limited_result.exit_code, 0, msg=limited_result.output)
        self.assertIn("Apple Inc.", limited_result.output)
        self.assertNotIn("Microsoft", limited_result.output)

        self.assertEqual(output_result.exit_code, 0, msg=output_result.output)
        self.assertTrue(output_exists)
        self.assertIn('"sections"', output_content)
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
                ["search", "--query", "AAPL", "--watch", "--count", "2", "--interval", "0.1"],
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

    def test_watch_wrapper_reuses_shared_request_and_backend_resolution(self) -> None:
        """顶层 watch 包装 shared 命令时，应复用同一请求对象与 backend 解析路径。"""
        captured = {}

        def fake_run(executor_self, request) -> None:
            captured["request"] = request
            click.echo("WATCHED")

        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            result = self.runner.invoke(
                self.cli,
                [
                    "watch",
                    "--interval",
                    "0.1",
                    "--count",
                    "1",
                    "--no-clear",
                    "search",
                    "--query",
                    "AAPL",
                    "--backend",
                    "akshare",
                ],
            )

        print_observation("watch shared 命令输出", result.output)
        print_observation(
            "watch shared 请求参数",
            {
                "spec": (
                    captured["request"].spec.module_name,
                    captured["request"].spec.function_name,
                ),
                "command_key": captured["request"].command_definition.command_key,
                "backend": captured["request"].backend_selection.resolved.value,
                "watch_enabled": captured["request"].watch.enabled,
                "watch_count": captured["request"].watch.count,
                "watch_interval": captured["request"].watch.interval,
            },
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("WATCHED", result.output)
        self.assertEqual(
            (captured["request"].spec.module_name, captured["request"].spec.function_name),
            ("shared", "instrument.search"),
        )
        self.assertEqual(captured["request"].command_definition.command_key, "instrument.search")
        self.assertEqual(captured["request"].backend_selection.resolved.value, "akshare")
        self.assertTrue(captured["request"].watch.enabled)
        self.assertEqual(captured["request"].watch.count, 1)
        self.assertAlmostEqual(captured["request"].watch.interval, 0.1)

    def test_search_result_count_routes_to_business_parameter_without_runtime_warning(self) -> None:
        """顶层 search 应把业务候选数量暴露为 result-count。"""
        captured = {}

        def fake_run(executor_self, request) -> None:
            captured["request"] = request
            click.echo("OK")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
                result = self.runner.invoke(
                    self.cli,
                    [
                        "search",
                        "--query",
                        "AAPL",
                        "--result-count",
                        "1",
                        "--format",
                        "json",
                    ],
                )

        print_observation("search result-count 输出", result.output)
        print_observation(
            "search 路由结果",
            {
                "spec": (
                    captured["request"].spec.module_name,
                    captured["request"].spec.function_name,
                ),
                "watch_count": captured["request"].watch.count,
                "warnings": [str(item.message) for item in caught],
            },
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertEqual(
            (captured["request"].spec.module_name, captured["request"].spec.function_name),
            ("shared", "instrument.search"),
        )
        self.assertIsNone(captured["request"].watch.count)
        self.assertFalse(
            any("parameter --count is used more than once" in str(item.message).lower() for item in caught),
            msg=[str(item.message) for item in caught],
        )

    def test_search_result_count_is_normalized_before_callback(self) -> None:
        """顶层 search 的 result-count 在执行前应被归一化为整数。"""
        with patch("efinance.utils.search_quote", return_value=build_search_records()) as mock_search:
            result = self.runner.invoke(
                self.cli,
                [
                    "search",
                    "--query",
                    "AAPL",
                    "--result-count",
                    "1",
                    "--format",
                    "json",
                ],
            )

        print_observation("search invoke 输出", result.output)
        print_observation("search invoke kwargs", mock_search.call_args.kwargs)
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertEqual(mock_search.call_args.kwargs["count"], 1)

    def test_transpose_and_no_index_are_forwarded_to_search_executor(self) -> None:
        """search 的输出控制参数应透传给统一执行链。"""
        captured = {}
        records = build_search_records()

        def fake_run(executor_self, request) -> None:
            captured["request"] = request
            click.echo("RUN")

        with patch("efinance.utils.search_quote", return_value=records), patch(
            "efinance_cli.executor.CommandExecutor.run",
            new=fake_run,
        ):
            result = self.runner.invoke(
                self.cli,
                ["search", "--query", "AAPL", "--transpose", "--no-index", "--full"],
            )

        print_observation("search run 输出", result.output)
        print_observation(
            "search run 输出选项",
            {
                "transpose": captured["request"].output.transpose,
                "no_index": captured["request"].output.no_index,
                "full": captured["request"].output.full,
                "view_mode": captured["request"].output.view_mode,
            },
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("RUN", result.output)
        self.assertTrue(captured["request"].output.transpose)
        self.assertTrue(captured["request"].output.no_index)
        self.assertTrue(captured["request"].output.full)
        self.assertEqual(captured["request"].output.view_mode, "observation")

    def test_resolve_and_search_specs_survive_mocked_callables(self) -> None:
        """search / resolve 相关命令规格在 mock / wrapper 场景下不应丢失。"""
        records = build_search_records()
        with patch("efinance.utils.search_quote", return_value=records):
            function_names = {
                spec.function_name
                for spec in build_command_specs("utils")
                if spec.cli_path[0] in {"search", "resolve", "market"}
            }

        print_observation("search/resolve 命令规格函数名", sorted(function_names))
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
        result = self.runner.invoke(self.cli, ["search", "--query", "AAPL", "--market", "UNKNOWN"])
        print_observation("search 非法 market 输出", result.output)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Unknown market enum", result.output)


    def test_all_leaf_commands_accept_maximal_sample_invocation(self) -> None:
        """每个叶子命令在“必填参数 + 所有可选参数样例值”下都应可执行。"""

        captured_requests = []

        def fake_run(executor_self, request) -> None:
            captured_requests.append(request)
            click.echo(f"MAXIMAL:{request.spec.module_name}.{request.spec.function_name}")

        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
                for leaf in self.leaf_commands:
                    if leaf.path[0] in {"search", "watch"}:
                        continue
                    argv = build_required_tokens(leaf) + build_all_optional_option_tokens(leaf, base_dir)
                    result = self.runner.invoke(self.cli, argv)
                    print_observation(f"{leaf.dotted_path} maximal sample 输出", result.output)
                    self.assertEqual(
                        result.exit_code,
                        0,
                        msg=f"{leaf.dotted_path} maximal sample 执行失败:\n{result.output}",
                    )
                    self.assertIn("MAXIMAL:", result.output)

        expected = len(
            [leaf for leaf in self.leaf_commands if leaf.path[0] not in {"search", "watch"}]
        )
        self.assertEqual(len(captured_requests), expected)

    def test_search_accepts_maximal_sample_invocation(self) -> None:
        """顶层 search 在业务参数和运行时参数同时出现时应保持稳定。"""

        records = build_search_records()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "search-maximal.json"
            with patch("efinance.utils.search_quote", return_value=records):
                result = self.runner.invoke(
                    self.cli,
                    [
                        "search",
                        "--query",
                        "AAPL",
                        "--market",
                        "US_stock",
                        "--result-count",
                        "2",
                        "--use-local-cache",
                        "--format",
                        "json",
                        "--full",
                        "--transpose",
                        "--no-index",
                        "--limit",
                        "1",
                        "--output",
                        str(output_path),
                        "--encoding",
                        "utf-8",
                        "--indicator-level",
                        "full",
                        "--view",
                        "observation",
                        "--trace-window",
                        "8",
                        "--watch",
                        "--interval",
                        "0.1",
                        "--count",
                        "1",
                        "--no-clear",
                    ],
                )

        print_observation("search maximal sample 输出", result.output)
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn('"meta"', result.output)

    def test_equity_history_shared_command_routes_through_executor(self) -> None:
        """共享 equity price history 命令应构造 shared 请求并透传 backend。"""
        captured = {}

        def fake_run(executor_self, request) -> None:
            captured["request"] = request
            click.echo("HISTORY_OK")

        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            result = self.runner.invoke(
                self.cli,
                [
                    "equity",
                    "price",
                    "history",
                    "--symbol",
                    "000001",
                    "--market",
                    "A_stock",
                    "--start-date",
                    "20260501",
                    "--end-date",
                    "20260528",
                    "--period",
                    "daily",
                    "--adjust",
                    "qfq",
                    "--backend",
                    "akshare",
                ],
            )

        print_observation("equity history shared 输出", result.output)
        print_observation(
            "equity history shared 请求",
            {
                "spec": (
                    captured["request"].spec.module_name,
                    captured["request"].spec.function_name,
                ),
                "kwargs": captured["request"].kwargs,
                "backend": captured["request"].backend_selection.resolved.value,
            },
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("HISTORY_OK", result.output)
        self.assertEqual(
            (captured["request"].spec.module_name, captured["request"].spec.function_name),
            ("shared", "equity.price.history"),
        )
        self.assertEqual(captured["request"].command_definition.command_key, "equity.price.history")
        self.assertEqual(captured["request"].backend_selection.resolved.value, "akshare")
        self.assertEqual(captured["request"].kwargs["symbol"], "000001")


if __name__ == "__main__":
    unittest.main()
