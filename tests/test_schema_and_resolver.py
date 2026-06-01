"""request_schema 与 backend resolver 的独立单元测试。

验证 uild_click_options_for_schema 对各类 RequestField 的正确 Click 参数映射，
以及 esolve_backend_selection 在各种输入下的后端选择逻辑。
"""

from __future__ import annotations

import unittest

import click

from efinance_cli.backends.resolver import resolve_backend_selection
from efinance_cli.command_catalog import get_shared_command_definition
from efinance_cli.models import BackendName, CommandDefinition, CommandKind, RequestField, RequestSchema
from efinance_cli.request_schema import build_click_option, build_click_options_for_schema
from tests.cli_regression_support import make_request_field, make_request_schema, print_observation


class SchemaAndResolverTest(unittest.TestCase):
    """覆盖 schema→Click 映射与后端选择逻辑。"""

    # ------------------------------------------------------------------
    # build_click_option / build_click_options_for_schema
    # ------------------------------------------------------------------

    def test_required_string_field_maps_to_required_option(self) -> None:
        field = make_request_field(
            name="keyword",
            cli_name="query",
            annotation=str,
            required=True,
            help_text="搜索关键字。",
        )
        option = build_click_option(field)
        print_observation("必填 str Option", {"name": option.name, "required": option.required})

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
        print_observation("可选 int Option", {"default": option.default, "required": option.required})

        self.assertFalse(option.required)
        self.assertEqual(option.default, 5)

    def test_bool_field_produces_flag(self) -> None:
        field = make_request_field(
            name="use_local",
            cli_name="use-local-cache",
            annotation=bool,
            default=True,
        )
        option = build_click_option(field)
        print_observation("bool flag Option", {"is_flag": option.is_flag, "default": option.default})

        self.assertTrue(option.is_flag)
        self.assertTrue(option.is_flag)
        self.assertIn('--no-use-local-cache', option.secondary_opts)

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

    def test_build_click_options_for_schema_returns_correct_count(self) -> None:
        schema = make_request_schema(
            fields=(
                make_request_field(name="a", cli_name="alpha", annotation=str, required=True),
                make_request_field(name="b", cli_name="beta", annotation=int, default=10),
            )
        )
        options = build_click_options_for_schema(schema)
        self.assertEqual(len(options), 2)

    # ------------------------------------------------------------------
    # resolve_backend_selection
    # ------------------------------------------------------------------

    def test_explicit_efinance_resolves_correctly(self) -> None:
        definition = get_shared_command_definition("stock.price.live")
        selection = resolve_backend_selection(definition, "efinance")
        print_observation("显式 efinance", {
            "resolved": selection.resolved.value,
            "source": selection.source,
        })

        self.assertEqual(selection.resolved, BackendName.EFINANCE)
        self.assertEqual(selection.source, "explicit")

    def test_auto_mode_produces_candidate_chain(self) -> None:
        definition = get_shared_command_definition("stock.price.history")
        selection = resolve_backend_selection(definition, None)
        print_observation("auto 模式", {
            "resolved": selection.resolved.value,
            "candidate_chain": tuple(item.value for item in selection.candidate_chain),
            "source": selection.source,
        })

        self.assertEqual(selection.resolved, BackendName.AUTO)
        self.assertGreater(len(selection.candidate_chain), 0)
        self.assertEqual(selection.source, "default")

    def test_unsupported_backend_raises_click_exception(self) -> None:
        definition = get_shared_command_definition("stock.price.live")  # only efinance + akshare
        with self.assertRaises(click.ClickException) as ctx:
            resolve_backend_selection(definition, "yfinance")

        message = str(ctx.exception)
        print_observation("不支持后端异常消息", message)
        self.assertIn("yfinance", message)

    def test_provider_extension_uses_provider_default(self) -> None:
        """provider-extension 命令在不传 backend 时应使用 provider_name 作为默认。"""
        definition = CommandDefinition(
            command_key="test.ext",
            cli_path=("test", "ext"),
            capability="test.ext",
            request_schema=RequestSchema(schema_name="test", fields=()),
            help_text="测试扩展命令。",
            kind=CommandKind.PROVIDER_EXTENSION,
            supported_backends=(BackendName.EFINANCE,),
            allow_watch=False,
            has_side_effect=False,
            provider_name=BackendName.EFINANCE,
        )
        selection = resolve_backend_selection(definition, None)
        print_observation("provider-extension 默认后端", {
            "resolved": selection.resolved.value,
            "source": selection.source,
        })

        self.assertEqual(selection.resolved, BackendName.EFINANCE)
        self.assertEqual(selection.source, "command-default")


if __name__ == "__main__":
    unittest.main()


