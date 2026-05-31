"""shared / provider-extension CLI 的端到端回归测试。

该文件只覆盖当前真实支持的命令树，不再为已经下线的 legacy 函数驱动命令保留回归。
测试重点是：

- 根命令与全部叶子命令的帮助页稳定可达；
- request schema 可以驱动参数解析与最小调用；
- 统一运行时参数会稳定透传给执行器；
- 顶层 `search` / `watch` 包装继续复用 shared 命令链；
- provider-extension 命令仍走统一执行骨架。
"""

from __future__ import annotations

import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import click
from click.testing import CliRunner

from efinance_cli.command_catalog import SHARED_COMMANDS
from efinance_cli.commands import create_root_command
from tests.cli_regression_support import (
    RUNTIME_EXECUTION_OPTION_NAMES,
    RUNTIME_OUTPUT_OPTION_NAMES,
    RUNTIME_WATCH_OPTION_NAMES,
    build_all_optional_option_tokens,
    build_option_cases,
    build_required_tokens,
    collect_leaf_commands,
    count_all_parameters,
    print_observation,
)


class CliFullRegressionTest(unittest.TestCase):
    """覆盖当前 shared / provider-extension CLI 的关键回归场景。"""

    def setUp(self) -> None:
        """构建测试所需的真实命令树。"""
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
                self.assertIn("search", result.output)
                self.assertIn("equity", result.output)
                self.assertIn("fund", result.output)
                self.assertIn("instrument", result.output)
                self.assertIn("akshare", result.output)
                self.assertNotIn("stock", result.output)
                self.assertNotIn("bond", result.output)
                self.assertNotIn("futures", result.output)
                self.assertNotIn("quote", result.output)
                self.assertNotIn("market", result.output)
                self.assertNotIn("resolve", result.output)
                continue

            if path == ("watch",):
                self.assertIn("--interval", result.output)
                self.assertIn("--clear / --no-clear", result.output)
                continue

            if path == ("search",):
                self.assertIn("--query", result.output)
                self.assertIn("--format", result.output)
                continue

            leaf_match = next((leaf for leaf in self.leaf_commands if leaf.path == path), None)
            if leaf_match is not None:
                self.assertIn("--format", result.output)
                self.assertIn("--indicator-level", result.output)
                self.assertIn("--watch", result.output)

    def test_command_tree_matches_shared_and_extension_inventory(self) -> None:
        """命令树应只暴露当前支持的 shared 与 provider-extension 叶子命令。"""
        paths = [" ".join(leaf.path) for leaf in self.leaf_commands]
        print_observation("leaf command inventory", paths)
        self.assertEqual(
            paths,
            [
                "watch",
                "equity price history",
                "equity price live",
                "equity profile",
                "fund nav history",
                "instrument search",
                "akshare industry boards",
            ],
        )
        self.assertEqual(len(self.leaf_commands), 7)

    def test_runtime_option_bundle_can_be_combined_on_all_routed_leaf_commands(self) -> None:
        """常用运行时参数组合在 routed 叶子命令上都应能同时解析。"""
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
                    if leaf.path == ("watch",):
                        continue
                    argv = build_required_tokens(leaf) + runtime_bundle
                    result = self.runner.invoke(self.cli, argv)
                    print_observation(f"{leaf.dotted_path} runtime bundle 输出", result.output)
                    self.assertEqual(result.exit_code, 0, msg=result.output)
                    self.assertIn("BUNDLE_OK", result.output)

            expected = len([leaf for leaf in self.leaf_commands if leaf.path != ("watch",)])
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

    def test_all_routed_leaf_commands_execute_without_unhandled_exception(self) -> None:
        """全部 routed 叶子命令在最小参数下都应执行到调度层。"""
        captured_requests = []

        def fake_run(executor_self, request) -> None:
            captured_requests.append(request)
            click.echo(f"EXECUTED:{request.spec.module_name}.{request.spec.function_name}")

        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            for leaf in self.leaf_commands:
                if leaf.path == ("watch",):
                    continue
                result = self.runner.invoke(self.cli, build_required_tokens(leaf))
                print_observation(f"{leaf.dotted_path} CLI 输出", result.output)
                self.assertEqual(result.exit_code, 0, msg=result.output)
                self.assertIn("EXECUTED:", result.output, msg=leaf.dotted_path)

        expected = len([leaf for leaf in self.leaf_commands if leaf.path != ("watch",)])
        self.assertEqual(len(captured_requests), expected)

    def test_all_options_can_be_parsed_and_forwarded(self) -> None:
        """全部选项参数都应能被解析，并在需要时透传到请求对象。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            for leaf in self.leaf_commands:
                if leaf.path == ("watch",):
                    continue
                for parameter in leaf.command.params:
                    if not isinstance(parameter, click.Option):
                        continue
                    if leaf.path == ("akshare", "industry", "boards") and parameter.name == "backend_name":
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
                        self.assertEqual(result.exit_code, 0, msg=result.output)

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
                            self.assertEqual(actual, expected_value)

    def test_all_routed_leaf_commands_support_four_output_formats(self) -> None:
        """全部 routed 叶子命令都应稳定走通四种输出格式。"""
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
                if leaf.path == ("watch",):
                    continue
                for format_name in formats:
                    argv = build_required_tokens(leaf) + ["--format", format_name]
                    result = self.runner.invoke(self.cli, argv)
                    print_observation(f"{leaf.dotted_path} format={format_name} 输出", result.output)
                    self.assertEqual(result.exit_code, 0, msg=result.output)
                    self.assertIn(
                        f"FORMAT:{rendered_cases[-1][0]}:{format_name}:observation",
                        result.output,
                    )

        expected = len([leaf for leaf in self.leaf_commands if leaf.path != ("watch",)]) * len(formats)
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
            "search",
            "--query",
            "AAPL",
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
                "search",
                "--query",
                "AAPL",
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

    def test_search_command_routes_to_shared_executor(self) -> None:
        """顶层 search 应路由到 shared instrument.search。"""
        captured = {}

        def fake_run(executor_self, request) -> None:
            captured["request"] = request
            click.echo("SEARCH_OK")

        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            result = self.runner.invoke(self.cli, ["search", "--query", "AAPL", "--backend", "akshare"])

        print_observation("search routed output", result.output)
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("SEARCH_OK", result.output)
        self.assertEqual(
            (captured["request"].spec.module_name, captured["request"].spec.function_name),
            ("shared", "instrument.search"),
        )
        self.assertEqual(captured["request"].command_definition.command_key, "instrument.search")
        self.assertEqual(captured["request"].backend_selection.resolved.value, "akshare")

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

        print_observation("watch shared command output", result.output)
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

        print_observation("search result-count output", result.output)
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertEqual(
            (captured["request"].spec.module_name, captured["request"].spec.function_name),
            ("shared", "instrument.search"),
        )
        self.assertIsNone(captured["request"].watch.count)
        self.assertFalse(
            any("parameter --count is used more than once" in str(item.message).lower() for item in caught),
        )

    def test_transpose_and_no_index_are_forwarded_to_search_executor(self) -> None:
        """search 的输出控制参数应透传给统一执行链。"""
        captured = {}

        def fake_run(executor_self, request) -> None:
            captured["request"] = request
            click.echo("RUN")

        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            result = self.runner.invoke(
                self.cli,
                ["search", "--query", "AAPL", "--transpose", "--no-index", "--full"],
            )

        print_observation("search run output", result.output)
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("RUN", result.output)
        self.assertTrue(captured["request"].output.transpose)
        self.assertTrue(captured["request"].output.no_index)
        self.assertTrue(captured["request"].output.full)
        self.assertEqual(captured["request"].output.view_mode, "observation")

    def test_command_and_parameter_inventory_is_nontrivial(self) -> None:
        """保护当前命令树规模，避免 shared / extension 注册意外塌缩。"""
        print_observation(
            "command inventory",
            {
                "leaf_commands": len(self.leaf_commands),
                "parameters": count_all_parameters(self.leaf_commands),
            },
        )
        self.assertEqual(len(self.leaf_commands), 7)
        self.assertGreaterEqual(count_all_parameters(self.leaf_commands), 60)

    def test_shared_command_catalog_help_pages_render_successfully(self) -> None:
        """shared 命令目录中的帮助页应直接反映 schema 与 backend 语义。"""
        for definition in SHARED_COMMANDS:
            result = self.runner.invoke(self.cli, [*definition.cli_path, "--help"])
            output = result.output.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
            print_observation(f"{' '.join(definition.cli_path)} --help", output)
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertIn(f"命令键: {definition.command_key}", output)
            self.assertIn(f"能力标识: {definition.capability}", output)
            self.assertIn("支持后端:", output)
            self.assertIn("--backend", output)
            for field in definition.request_schema.fields:
                self.assertIn(f"--{field.cli_name}", output)

    def test_shared_command_catalog_schema_drives_minimal_invocation(self) -> None:
        """shared 命令目录应能独立作为 CLI 回归输入源。"""
        captured_requests = []

        def fake_run(executor_self, request) -> None:
            captured_requests.append(request)
            click.echo(f"SHARED_OK:{request.command_definition.command_key}")

        invocations = [
            ("instrument.search", ["search", "--query", "AAPL", "--backend", "akshare"]),
            (
                "equity.price.history",
                [
                    "equity",
                    "price",
                    "history",
                    "--symbol",
                    "000001",
                    "--start-date",
                    "20260501",
                    "--end-date",
                    "20260528",
                    "--period",
                    "daily",
                    "--adjust",
                    "qfq",
                    "--backend",
                    "efinance",
                ],
            ),
            ("equity.profile", ["equity", "profile", "--symbol", "000001", "--backend", "akshare"]),
            ("fund.nav.history", ["fund", "nav", "history", "--symbol", "161725", "--backend", "efinance"]),
            (
                "equity.price.live",
                [
                    "equity",
                    "price",
                    "live",
                    "--market",
                    "A_stock",
                    "--record-limit",
                    "2",
                    "--backend",
                    "akshare",
                ],
            ),
        ]

        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            for command_key, argv in invocations:
                result = self.runner.invoke(self.cli, argv)
                print_observation(f"{command_key} minimal invocation", result.output)
                self.assertEqual(result.exit_code, 0, msg=result.output)
                self.assertIn(f"SHARED_OK:{command_key}", result.output)

        self.assertEqual(
            [request.command_definition.command_key for request in captured_requests],
            [item[0] for item in invocations],
        )
        self.assertTrue(all(request.spec.module_name == "shared" for request in captured_requests))
        self.assertTrue(all(request.command_definition is not None for request in captured_requests))

    def test_shared_command_catalog_rejects_missing_required_schema_fields(self) -> None:
        """shared 命令的必填参数应按 request schema 直接失败。"""
        cases = [
            ("search", ["search"], "Missing option '--query'"),
            ("equity.price.history", ["equity", "price", "history"], "Missing required option '--symbol'"),
            ("equity.profile", ["equity", "profile"], "Missing required option '--symbol'"),
            ("fund.nav.history", ["fund", "nav", "history"], "Missing required option '--symbol'"),
        ]

        for title, argv, expected in cases:
            result = self.runner.invoke(self.cli, argv)
            print_observation(f"{title} missing required field", result.output)
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn(expected, result.output)

    def test_watch_without_subcommand_raises_click_exception(self) -> None:
        """watch 缺少子命令时应返回可读错误。"""
        result = self.runner.invoke(self.cli, ["watch"])
        print_observation("watch missing subcommand output", result.output)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("watch must be followed by a full subcommand", result.output)

    def test_unsupported_market_name_returns_readable_error(self) -> None:
        """search 的非法 market 参数应返回可读错误。"""
        result = self.runner.invoke(self.cli, ["search", "--query", "AAPL", "--market", "UNKNOWN"])
        print_observation("search illegal market output", result.output)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Unknown market enum", result.output)

    def test_all_routed_leaf_commands_accept_maximal_sample_invocation(self) -> None:
        """每个 routed 叶子命令在“必填参数 + 全部可选参数样例值”下都应可执行。"""
        captured_requests = []

        def fake_run(executor_self, request) -> None:
            captured_requests.append(request)
            click.echo(f"MAXIMAL:{request.spec.module_name}.{request.spec.function_name}")

        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
                for leaf in self.leaf_commands:
                    if leaf.path == ("watch",):
                        continue
                    optional_tokens = build_all_optional_option_tokens(leaf, base_dir)
                    if leaf.path == ("akshare", "industry", "boards"):
                        filtered_tokens: list[str] = []
                        skip_next = False
                        for token in optional_tokens:
                            if skip_next:
                                skip_next = False
                                continue
                            if token == "--backend":
                                skip_next = True
                                continue
                            filtered_tokens.append(token)
                        optional_tokens = filtered_tokens
                    argv = build_required_tokens(leaf) + optional_tokens
                    result = self.runner.invoke(self.cli, argv)
                    print_observation(f"{leaf.dotted_path} maximal sample output", result.output)
                    self.assertEqual(result.exit_code, 0, msg=result.output)
                    self.assertIn("MAXIMAL:", result.output)

        expected = len([leaf for leaf in self.leaf_commands if leaf.path != ("watch",)])
        self.assertEqual(len(captured_requests), expected)

    def test_equity_history_shared_command_routes_through_executor(self) -> None:
        """shared equity history 命令应构造 shared 请求并透传 backend。"""
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

        print_observation("equity history shared output", result.output)
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("HISTORY_OK", result.output)
        self.assertEqual(
            (captured["request"].spec.module_name, captured["request"].spec.function_name),
            ("shared", "equity.price.history"),
        )
        self.assertEqual(captured["request"].command_definition.command_key, "equity.price.history")
        self.assertEqual(captured["request"].backend_selection.resolved.value, "akshare")
        self.assertEqual(captured["request"].kwargs["symbol"], "000001")

    def test_equity_profile_shared_command_routes_through_executor(self) -> None:
        """shared equity profile 命令应按 shared 请求透传到 backend。"""
        captured = {}

        def fake_run(executor_self, request) -> None:
            captured["request"] = request
            click.echo("PROFILE_OK")

        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            result = self.runner.invoke(
                self.cli,
                [
                    "equity",
                    "profile",
                    "--symbol",
                    "000001",
                    "--market",
                    "A_stock",
                    "--backend",
                    "efinance",
                ],
            )

        print_observation("equity profile shared output", result.output)
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("PROFILE_OK", result.output)
        self.assertEqual(
            (captured["request"].spec.module_name, captured["request"].spec.function_name),
            ("shared", "equity.profile"),
        )
        self.assertEqual(captured["request"].command_definition.command_key, "equity.profile")
        self.assertEqual(captured["request"].backend_selection.resolved.value, "efinance")
        self.assertEqual(captured["request"].kwargs["symbol"], "000001")

    def test_fund_root_is_shared_only(self) -> None:
        """fund 根组应只暴露 shared 命令，不再保留 legacy 子树。"""
        fund_result = self.runner.invoke(self.cli, ["fund", "--help"])
        nav_result = self.runner.invoke(self.cli, ["fund", "nav", "--help"])
        print_observation("fund root help", fund_result.output)
        print_observation("fund nav help", nav_result.output)
        self.assertEqual(fund_result.exit_code, 0, msg=fund_result.output)
        self.assertEqual(nav_result.exit_code, 0, msg=nav_result.output)
        self.assertIn("nav", fund_result.output)
        self.assertIn("history", nav_result.output)
        self.assertNotIn("history-batch", nav_result.output)

    def test_fund_nav_history_shared_command_routes_through_executor(self) -> None:
        """shared fund nav history 命令应按 shared 请求透传 backend。"""
        captured = {}

        def fake_run(executor_self, request) -> None:
            captured["request"] = request
            click.echo("FUND_HISTORY_OK")

        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            result = self.runner.invoke(
                self.cli,
                [
                    "fund",
                    "nav",
                    "history",
                    "--symbol",
                    "161725",
                    "--backend",
                    "akshare",
                ],
            )

        print_observation("fund nav history shared output", result.output)
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("FUND_HISTORY_OK", result.output)
        self.assertEqual(
            (captured["request"].spec.module_name, captured["request"].spec.function_name),
            ("shared", "fund.nav.history"),
        )
        self.assertEqual(captured["request"].command_definition.command_key, "fund.nav.history")
        self.assertEqual(captured["request"].backend_selection.resolved.value, "akshare")
        self.assertEqual(captured["request"].kwargs["symbol"], "161725")

    def test_equity_live_shared_command_routes_through_executor(self) -> None:
        """shared equity live 命令应按 shared 请求透传到 backend。"""
        captured = {}

        def fake_run(executor_self, request) -> None:
            captured["request"] = request
            click.echo("LIVE_OK")

        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            result = self.runner.invoke(
                self.cli,
                [
                    "equity",
                    "price",
                    "live",
                    "--market",
                    "A_stock",
                    "--record-limit",
                    "2",
                    "--backend",
                    "akshare",
                ],
            )

        print_observation("equity live shared output", result.output)
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("LIVE_OK", result.output)
        self.assertEqual(
            (captured["request"].spec.module_name, captured["request"].spec.function_name),
            ("shared", "equity.price.live"),
        )
        self.assertEqual(captured["request"].command_definition.command_key, "equity.price.live")
        self.assertEqual(captured["request"].backend_selection.resolved.value, "akshare")
        self.assertEqual(captured["request"].kwargs["market"], "A_stock")
        self.assertEqual(captured["request"].kwargs["record_limit"], 2)

    def test_akshare_extension_command_routes_through_executor(self) -> None:
        """akshare 扩展命令应走统一执行器并默认解析到 akshare backend。"""
        captured = {}

        def fake_run(executor_self, request) -> None:
            captured["request"] = request
            click.echo("EXT_OK")

        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            result = self.runner.invoke(
                self.cli,
                [
                    "akshare",
                    "industry",
                    "boards",
                ],
            )

        print_observation("akshare extension command output", result.output)
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("EXT_OK", result.output)
        self.assertEqual(
            (captured["request"].spec.module_name, captured["request"].spec.function_name),
            ("shared", "akshare.industry.boards"),
        )
        self.assertEqual(captured["request"].command_definition.command_key, "akshare.industry.boards")
        self.assertEqual(captured["request"].backend_selection.resolved.value, "akshare")
        self.assertEqual(captured["request"].backend_selection.source, "command-default")

    def test_akshare_extension_command_rejects_wrong_backend(self) -> None:
        """akshare 扩展命令在错误 backend 下应明确失败。"""
        result = self.runner.invoke(
            self.cli,
            [
                "akshare",
                "industry",
                "boards",
                "--backend",
                "efinance",
            ],
        )
        print_observation("akshare extension wrong backend output", result.output)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("does not support backend 'efinance'", result.output)


if __name__ == "__main__":
    unittest.main()
