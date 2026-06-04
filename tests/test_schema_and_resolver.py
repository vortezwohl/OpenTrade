"""request_schema 与 backend resolver 的回归测试。

这些用例验证 schema 到 Click 选项、normalized shared request 与 backend 解析行为。
"""

from __future__ import annotations

import unittest

import click

from opentrade.backends.auto_planner import plan_auto_backend_candidates
from opentrade.backends.resolver import resolve_backend_selection
from opentrade.command_catalog import REFERENCE_CATALOG_MODULE, get_shared_command_definition
from opentrade.models import BackendName, CommandDefinition, CommandKind, RequestSchema
from opentrade.request_schema import (
    build_click_option,
    build_click_options_for_schema,
    validate_request_data,
)
from tests.cli_regression_support import make_request_field, make_request_schema, print_observation


class SchemaAndResolverTest(unittest.TestCase):
    """覆盖 schema、Click 与路由解析的关键行为。"""

    def test_required_string_field_maps_to_required_option(self) -> None:
        field = make_request_field(
            name="keyword",
            cli_name="query",
            annotation=str,
            required=True,
            help_text="搜索关键词",
        )
        option = build_click_option(field)
        print_observation("required str option", {"name": option.name, "required": option.required})

        self.assertTrue(option.required)
        self.assertEqual(option.name, "keyword")
        self.assertIn("--query", option.opts)

    def test_optional_int_field_with_default(self) -> None:
        field = make_request_field(
            name="count",
            cli_name="result-count",
            annotation=int,
            required=False,
            default=5,
        )
        option = build_click_option(field)
        print_observation("optional int option", {"default": option.default, "required": option.required})

        self.assertFalse(option.required)
        self.assertEqual(option.default, 5)

    def test_bool_field_produces_flag(self) -> None:
        field = make_request_field(
            name="use_local_cache",
            cli_name="use-local-cache",
            annotation=bool,
            default=True,
        )
        option = build_click_option(field)
        print_observation("bool flag Option", {"is_flag": option.is_flag, "default": option.default})

        self.assertTrue(option.is_flag)
        self.assertIn("--no-use-local-cache", option.secondary_opts)

    def test_choice_field_produces_click_choice(self) -> None:
        field = make_request_field(
            name="format",
            cli_name="format",
            annotation=str,
            choices=("table", "json", "csv"),
        )
        option = build_click_option(field)
        print_observation("Choice Option", {"type": type(option.type).__name__, "choices": option.type.choices})

        self.assertIsInstance(option.type, click.Choice)
        self.assertEqual(set(option.type.choices), {"table", "json", "csv"})

    def test_multiple_field_produces_multiple_option(self) -> None:
        field = make_request_field(
            name="symbols",
            cli_name="symbols",
            annotation=str,
            required=True,
            multiple=True,
        )
        option = build_click_option(field)
        print_observation("multiple Option", {"multiple": option.multiple})

        self.assertTrue(option.multiple)

    def test_click_aliases_are_exposed_for_compatible_fields(self) -> None:
        definition = get_shared_command_definition("stock.profile")
        option = next(item for item in build_click_options_for_schema(definition.request_schema) if item.name == "symbol")
        self.assertIn("--symbol", option.opts)
        self.assertIn("--symbols", option.opts)

    def test_build_click_options_for_schema_returns_correct_count(self) -> None:
        schema = make_request_schema(
            fields=(
                make_request_field(name="a", cli_name="alpha", annotation=str, required=True),
                make_request_field(name="b", cli_name="beta", annotation=int, default=10),
            )
        )
        options = build_click_options_for_schema(schema)
        self.assertEqual(len(options), 2)

    def test_validate_request_data_normalizes_legacy_history_fields(self) -> None:
        definition = get_shared_command_definition("stock.price.history")
        normalized = validate_request_data(
            definition.request_schema,
            {
                "stock_codes": ["000001"],
                "beg": "2025-05-01",
                "end": "20250530",
                "klt": 101,
                "fqt": 1,
                "market_type": "A_stock",
                "suppress_error": False,
                "use_id_cache": True,
            },
        )
        print_observation("normalized history request", normalized)
        self.assertEqual(normalized["symbols"], ["000001"])
        self.assertEqual(normalized["start_date"], "20250501")
        self.assertEqual(normalized["end_date"], "20250530")
        self.assertEqual(normalized["market"], "A_stock")
        self.assertEqual(normalized["timeframe"], 101)
        self.assertEqual(normalized["adjustment"], 1)

    def test_market_validation_uses_semantic_type_not_field_name(self) -> None:
        definition = get_shared_command_definition("stock.price.history")
        with self.assertRaises(click.ClickException) as ctx:
            validate_request_data(
                definition.request_schema,
                {
                    "symbols": ["000001"],
                    "market": "bad-market",
                },
            )
        self.assertIn("Unknown market enum", str(ctx.exception))

    def test_compact_date_input_is_preserved(self) -> None:
        definition = get_shared_command_definition("stock.price.history")
        normalized = validate_request_data(
            definition.request_schema,
            {"symbols": ["000001"], "start_date": "20250331", "end_date": "20250530"},
        )
        self.assertEqual(normalized["start_date"], "20250331")
        self.assertEqual(normalized["end_date"], "20250530")

    def test_command_catalog_uses_repo_owned_metadata(self) -> None:
        self.assertEqual(REFERENCE_CATALOG_MODULE, "opentrade.const.command_catalog_data")
        self.assertIn("opentrade", REFERENCE_CATALOG_MODULE)
        self.assertNotIn(".skill", REFERENCE_CATALOG_MODULE)

    def test_explicit_efinance_resolves_correctly(self) -> None:
        definition = get_shared_command_definition("stock.price.live")
        selection = resolve_backend_selection(definition, "efinance")
        print_observation("显式 efinance", {
            "resolved": selection.resolved.value,
            "source": selection.source,
        })

        self.assertEqual(selection.resolved, BackendName.EFINANCE)
        self.assertEqual(selection.source, "explicit")

    def test_auto_mode_only_marks_auto_before_request_planning(self) -> None:
        definition = get_shared_command_definition("stock.price.history")
        selection = resolve_backend_selection(definition, None)
        print_observation("auto 默认", {
            "resolved": selection.resolved.value,
            "candidate_chain": tuple(item.value for item in selection.candidate_chain),
            "source": selection.source,
        })

        self.assertEqual(selection.resolved, BackendName.AUTO)
        self.assertEqual(selection.candidate_chain, ())
        self.assertEqual(selection.source, "default")

    def test_request_aware_auto_planning_prefers_us_requests_for_yfinance(self) -> None:
        definition = get_shared_command_definition("stock.price.history")
        chain = plan_auto_backend_candidates(
            definition,
            {
                "symbols": ["AAPL"],
                "start_date": "20250501",
                "end_date": "20250530",
                "market": "US_stock",
            },
        )
        self.assertEqual(chain[0], BackendName.YFINANCE)

    def test_request_aware_auto_planning_prefers_a_share_requests_for_efinance(self) -> None:
        definition = get_shared_command_definition("stock.price.history")
        chain = plan_auto_backend_candidates(
            definition,
            {
                "symbols": ["000001"],
                "start_date": "20250501",
                "end_date": "20250530",
                "market": "A_stock",
            },
        )
        self.assertEqual(chain[0], BackendName.EFINANCE)

    def test_unsupported_backend_raises_click_exception(self) -> None:
        definition = get_shared_command_definition("stock.price.live")
        with self.assertRaises(click.ClickException) as ctx:
            resolve_backend_selection(definition, "yfinance")

        message = str(ctx.exception)
        print_observation("不支持的 backend", message)
        self.assertIn("yfinance", message)

    def test_provider_extension_uses_provider_default(self) -> None:
        definition = CommandDefinition(
            command_key="test.ext",
            cli_path=("test", "ext"),
            capability="test.ext",
            request_schema=RequestSchema(schema_name="test", fields=()),
            help_text="扩展命令",
            kind=CommandKind.PROVIDER_EXTENSION,
            supported_backends=(BackendName.EFINANCE,),
            allow_watch=False,
            has_side_effect=False,
            provider_name=BackendName.EFINANCE,
        )
        selection = resolve_backend_selection(definition, None)
        print_observation("provider-extension 默认", {
            "resolved": selection.resolved.value,
            "source": selection.source,
        })

        self.assertEqual(selection.resolved, BackendName.EFINANCE)
        self.assertEqual(selection.source, "command-default")


if __name__ == "__main__":
    unittest.main()
