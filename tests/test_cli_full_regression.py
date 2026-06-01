from __future__ import annotations

import unittest
from unittest.mock import patch

import click
from click.testing import CliRunner

from efinance_cli.backends.base import BackendProvider, CapabilityHandler
from efinance_cli.backends.factory import list_provider_extension_commands
from efinance_cli.command_catalog import get_shared_command_definition
from efinance_cli.command_catalog import SHARED_COMMANDS
from efinance_cli.commands import create_root_command
from efinance_cli.executor import CommandExecutor
from efinance_cli.facade import AutoBackendExecutionError
from efinance_cli.models import BackendName, BackendSelection, CommandSpec, InvocationRequest, OutputOptions, StandardResult, WatchOptions


def collect_leaf_paths(command: click.Command, prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    if isinstance(command, click.Group):
        paths: list[tuple[str, ...]] = []
        for name, child in command.commands.items():
            paths.extend(collect_leaf_paths(child, prefix + (name,)))
        return paths
    return [prefix]


class CliFullRegressionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()
        self.cli = create_root_command()

    def test_root_help_exposes_new_taxonomy(self) -> None:
        result = self.runner.invoke(self.cli, ["--help"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        for token in ("stock", "fund", "bond", "futures", "quote", "market", "resolve", "search", "watch"):
            self.assertIn(token, result.output)
        for token in ("equity", "akshare", "instrument"):
            self.assertNotIn(token, result.output)

    def test_leaf_inventory_matches_catalog_plus_extension_and_watch(self) -> None:
        actual = sorted(" ".join(path) for path in collect_leaf_paths(self.cli))
        expected = sorted(
            {
                "watch",
                *(
                    " ".join(command.cli_path)
                    for command in SHARED_COMMANDS
                    if command.command_key != "instrument.search"
                ),
                *(" ".join(command.cli_path) for command in list_provider_extension_commands()),
            }
        )
        self.assertEqual(actual, expected)
        self.assertGreater(len(actual), 40)

    def test_default_search_routes_to_instrument_search(self) -> None:
        captured: list[dict[str, object]] = []

        def fake_run(self, request):  # noqa: ANN001
            captured.append(
                {
                    "path": request.spec.cli_path,
                    "command_key": request.command_definition.command_key,
                    "kwargs": dict(request.kwargs),
                    "backend": request.backend_selection.resolved.value,
                    "candidate_chain": tuple(item.value for item in request.backend_selection.candidate_chain),
                }
            )

        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            result = self.runner.invoke(self.cli, ["search", "--query", "AAPL"])

        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertEqual(captured[0]["path"], ("search",))
        self.assertEqual(captured[0]["command_key"], "instrument.search")
        self.assertEqual(captured[0]["kwargs"]["keyword"], "AAPL")
        self.assertEqual(captured[0]["backend"], "auto")
        self.assertEqual(captured[0]["candidate_chain"], ("akshare", "yfinance", "efinance"))

    def test_representative_commands_route_through_executor(self) -> None:
        captured: list[dict[str, object]] = []
        commands = [
            (["stock", "price", "history", "--symbols", "000001"], "stock.price.history", "auto"),
            (["stock", "price", "history", "--symbols", "AAPL", "--backend", "yfinance"], "stock.price.history", "yfinance"),
            (["fund", "nav", "history", "--symbol", "161725"], "fund.nav.history", "auto"),
            (["fund", "nav", "history-batch", "--symbols", "161725", "--symbols", "110022"], "fund.nav.history-batch", "efinance"),
            (["bond", "catalog"], "bond.catalog", "efinance"),
            (["futures", "price", "live"], "futures.price.live", "efinance"),
            (["quote", "price", "latest", "--quote-ids", "1.000001"], "quote.price.latest", "auto"),
            (["quote", "price", "latest", "--quote-ids", "AAPL", "--backend", "yfinance"], "quote.price.latest", "yfinance"),
            (["quote", "news", "--quote-id", "AAPL", "--result-count", "3"], "yfinance.quote.news", "yfinance"),
            (["market", "price", "live", "--market", "m:105+t:3"], "market.price.live", "efinance"),
            (["resolve", "quote-id", "--symbol", "000001"], "resolve.quote-id", "efinance"),
            (["search", "local", "--query", "AAPL"], "search.local", "efinance"),
        ]

        def fake_run(self, request):  # noqa: ANN001
            captured.append(
                {
                    "path": request.spec.cli_path,
                    "command_key": request.command_definition.command_key,
                    "backend": request.backend_selection.resolved.value,
                    "kwargs": dict(request.kwargs),
                }
            )

        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            for args, _, _ in commands:
                result = self.runner.invoke(self.cli, args)
                self.assertEqual(result.exit_code, 0, msg=f"{args}: {result.output}")

        self.assertEqual(len(captured), len(commands))
        for item, (_, command_key, backend) in zip(captured, commands, strict=False):
            self.assertEqual(item["command_key"], command_key)
            self.assertEqual(item["backend"], backend)

    def test_provider_extension_routes_to_default_backend(self) -> None:
        captured: list[dict[str, object]] = []

        def fake_run(self, request):  # noqa: ANN001
            captured.append(
                {
                    "path": request.spec.cli_path,
                    "command_key": request.command_definition.command_key,
                    "backend": request.backend_selection.resolved.value,
                }
            )

        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            result = self.runner.invoke(self.cli, ["stock", "industry", "boards"])

        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertEqual(captured[0]["path"], ("stock", "industry", "boards"))
        self.assertEqual(captured[0]["command_key"], "akshare.industry.boards")
        self.assertEqual(captured[0]["backend"], "akshare")

    def test_provider_extension_auto_adapts_to_owner_backend(self) -> None:
        captured: list[dict[str, object]] = []

        def fake_run(self, request):  # noqa: ANN001
            captured.append(
                {
                    "backend": request.backend_selection.resolved.value,
                    "source": request.backend_selection.source,
                }
            )

        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            result = self.runner.invoke(
                self.cli,
                ["quote", "news", "--quote-id", "AAPL", "--backend", "auto"],
            )

        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertEqual(captured[0]["backend"], "yfinance")
        self.assertEqual(captured[0]["source"], "auto-adapted")

    def test_provider_extension_rejects_wrong_backend(self) -> None:
        result = self.runner.invoke(
            self.cli,
            ["stock", "industry", "boards", "--backend", "efinance"],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("仅支持 backend: akshare", result.output)
        self.assertIn("默认会路由到 'akshare'", result.output)

    def test_yfinance_extension_rejects_wrong_backend(self) -> None:
        result = self.runner.invoke(
            self.cli,
            ["quote", "news", "--quote-id", "AAPL", "--backend", "efinance"],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("仅支持 backend: yfinance", result.output)

    def test_yfinance_extension_help_uses_result_count_option(self) -> None:
        result = self.runner.invoke(self.cli, ["quote", "news", "--help"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("--result-count", result.output)
        self.assertEqual(result.output.count("--count INTEGER"), 1)

    def test_help_mentions_yfinance_semantics_for_supported_shared_command(self) -> None:
        result = self.runner.invoke(self.cli, ["quote", "price", "latest", "--help"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("支持后端: efinance, yfinance", result.output)
        self.assertIn("Yahoo ticker / symbol", result.output)

    def test_watch_wrapper_keeps_provider_extension_default_routing(self) -> None:
        captured: list[dict[str, object]] = []

        def fake_run(self, request):  # noqa: ANN001
            captured.append(
                {
                    "path": request.spec.cli_path,
                    "command_key": request.command_definition.command_key,
                    "backend": request.backend_selection.resolved.value,
                    "candidate_chain": tuple(item.value for item in request.backend_selection.candidate_chain),
                    "watch_enabled": request.watch.enabled,
                    "interval": request.watch.interval,
                    "count": request.watch.count,
                }
            )

        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            result = self.runner.invoke(
                self.cli,
                ["watch", "--interval", "3", "--count", "2", "stock", "industry", "boards"],
            )

        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertEqual(captured[0]["path"], ("stock", "industry", "boards"))
        self.assertEqual(captured[0]["command_key"], "akshare.industry.boards")
        self.assertEqual(captured[0]["backend"], "akshare")
        self.assertEqual(captured[0]["candidate_chain"], ())
        self.assertEqual(captured[0]["watch_enabled"], True)
        self.assertEqual(captured[0]["interval"], 3.0)
        self.assertEqual(captured[0]["count"], 2)

    def test_watch_wrapper_keeps_auto_candidate_chain_for_shared_command(self) -> None:
        captured: list[dict[str, object]] = []

        def fake_run(self, request):  # noqa: ANN001
            captured.append(
                {
                    "backend": request.backend_selection.resolved.value,
                    "candidate_chain": tuple(item.value for item in request.backend_selection.candidate_chain),
                    "watch_enabled": request.watch.enabled,
                }
            )

        with patch("efinance_cli.executor.CommandExecutor.run", new=fake_run):
            result = self.runner.invoke(
                self.cli,
                ["watch", "--interval", "3", "--count", "2", "stock", "price", "history", "--symbols", "000001"],
            )

        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertEqual(captured[0]["backend"], "auto")
        self.assertEqual(captured[0]["candidate_chain"], ("akshare", "yfinance", "efinance"))
        self.assertEqual(captured[0]["watch_enabled"], True)

    def test_cli_reports_auto_failover_aggregation(self) -> None:
        definition = get_shared_command_definition("stock.price.history")

        class RuntimeFailHandler(CapabilityHandler):
            def __init__(self, message: str) -> None:
                self.message = message

            def execute(self, request_data: dict[str, object]) -> StandardResult:
                raise RuntimeError(self.message)

        providers = {
            BackendName.AKSHARE: BackendProvider(BackendName.AKSHARE, {"stock.price.history": RuntimeFailHandler("akshare failed")}),
            BackendName.YFINANCE: BackendProvider(BackendName.YFINANCE, {"stock.price.history": RuntimeFailHandler("yfinance failed")}),
            BackendName.EFINANCE: BackendProvider(BackendName.EFINANCE, {"stock.price.history": RuntimeFailHandler("efinance failed")}),
        }
        backend = BackendSelection(
            requested=None,
            resolved=BackendName.AUTO,
            source="default",
            candidate_chain=(BackendName.AKSHARE, BackendName.YFINANCE, BackendName.EFINANCE),
        )

        with patch("efinance_cli.facade.get_backend_provider", side_effect=lambda name: providers[name]):
            with self.assertRaises(AutoBackendExecutionError) as context:
                from efinance_cli.facade import CommandFacade

                CommandFacade().invoke(definition, backend, {"stock_codes": ["000001"]})

        message = str(context.exception)
        self.assertIn("akshare failed", message)
        self.assertIn("yfinance failed", message)
        self.assertIn("efinance failed", message)

    def test_watch_mode_retries_same_auto_chain_each_iteration(self) -> None:
        request = InvocationRequest(
            spec=CommandSpec(
                module_name="shared",
                function_name="stock.price.history",
                callback=lambda **_: None,
                help_text="test",
                cli_path=("stock", "price", "history"),
                allow_watch=True,
            ),
            kwargs={"stock_codes": ["000001"]},
            output=OutputOptions(format_name="json", view_mode="raw"),
            watch=WatchOptions(enabled=True, interval=0.0, count=2, clear_screen=False),
            command_definition=get_shared_command_definition("stock.price.history"),
            backend_selection=BackendSelection(
                requested=None,
                resolved=BackendName.AUTO,
                source="default",
                candidate_chain=(BackendName.AKSHARE, BackendName.YFINANCE, BackendName.EFINANCE),
            ),
        )
        observed: list[tuple[str, tuple[str, ...], str | None]] = []

        def fake_invoke(self, runtime_request):  # noqa: ANN001
            observed.append(
                (
                    runtime_request.backend_selection.resolved.value,
                    tuple(item.value for item in runtime_request.backend_selection.candidate_chain),
                    (
                        runtime_request.backend_selection.final_backend.value
                        if runtime_request.backend_selection.final_backend is not None
                        else None
                    ),
                )
            )
            runtime_request.backend_selection.final_backend = BackendName.YFINANCE
            return type("MockResult", (), {"value": {"iteration": len(observed)}})()

        with patch.object(CommandExecutor, "invoke", new=fake_invoke):
            with patch("click.echo"):
                executor = CommandExecutor()
                executor.run(request)

        self.assertEqual(len(observed), 2)
        self.assertEqual(observed[0], ("auto", ("akshare", "yfinance", "efinance"), None))
        self.assertEqual(observed[1], ("auto", ("akshare", "yfinance", "efinance"), None))

    def test_required_schema_fields_fail_readably(self) -> None:
        result = self.runner.invoke(self.cli, ["stock", "price", "history"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Missing option '--symbols'", result.output)

        result = self.runner.invoke(self.cli, ["fund", "nav", "history"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Missing required option '--symbol'", result.output)


if __name__ == "__main__":
    unittest.main()
