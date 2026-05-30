"""多后端骨架的最小回归测试。

本测试文件只验证新架构的第一批承载层是否已经就位：

- 共享命令目录由显式定义驱动；
- 请求 schema 能生成 Click 参数并完成校验；
- backend 解析能执行支持矩阵检查；
- provider / handler / facade 能承载首批共享 capability；
- `efinance` 搜索能力返回标准搜索契约；
- `akshare` 搜索能力当前明确报告“未实现”，而不是伪造成功。
"""

from __future__ import annotations

import unittest
from collections import namedtuple
from unittest.mock import patch

import click
import pandas as pd

from efinance_cli.command_catalog import (
    SHARED_COMMANDS,
    build_shared_command_definitions_for_group,
    get_capability_descriptor,
    get_shared_command_definition,
    list_shared_root_groups,
)
from efinance_cli.contracts import SEARCH_RESULTS_CONTRACT, StandardizationError
from efinance_cli.enrichment.service import enrich_market_data
from efinance_cli.facade import CommandFacade
from efinance_cli.models import BackendName, RequestField, RequestSchema
from efinance_cli.models import CommandSpec, InvocationRequest, OutputOptions, WatchOptions
from efinance_cli.request_schema import build_click_options_for_schema, validate_request_data
from efinance_cli.backends.factory import get_backend_provider, list_backend_providers
from efinance_cli.backends.providers import AkshareSearchHandler
from efinance_cli.backends.resolver import resolve_backend_selection
from tests.cli_regression_support import print_observation


SearchRecord = namedtuple(
    "SearchRecord",
    ["code", "name", "pinyin", "quote_id", "classify"],
)


class MultiBackendScaffoldTest(unittest.TestCase):
    """验证多后端骨架的最小闭环。"""

    def test_shared_catalog_exposes_stable_command_definition(self) -> None:
        """共享命令目录应暴露稳定命令键和 capability 描述。"""
        definition = get_shared_command_definition("instrument.search")
        capability = get_capability_descriptor(definition.capability)
        print_observation(
            "共享命令定义",
            {
                "command_key": definition.command_key,
                "cli_path": definition.cli_path,
                "capability": definition.capability,
                "supported_backends": [item.value for item in definition.supported_backends],
            },
        )
        self.assertEqual(definition.command_key, "instrument.search")
        self.assertEqual(definition.cli_path, ("instrument", "search"))
        self.assertEqual(capability.result_contract, "search-results")
        self.assertIn(BackendName.EFINANCE, definition.supported_backends)
        self.assertIn(BackendName.AKSHARE, definition.supported_backends)
        self.assertIn("instrument", list_shared_root_groups())
        self.assertEqual(build_shared_command_definitions_for_group("instrument"), [definition])
        self.assertEqual(len(SHARED_COMMANDS), 2)

    def test_shared_catalog_exposes_equity_history_definition(self) -> None:
        """共享命令目录应暴露权益历史命令定义。"""
        definition = get_shared_command_definition("equity.price.history")
        capability = get_capability_descriptor(definition.capability)
        print_observation(
            "共享权益历史定义",
            {
                "command_key": definition.command_key,
                "cli_path": definition.cli_path,
                "capability": definition.capability,
                "supported_backends": [item.value for item in definition.supported_backends],
            },
        )
        self.assertEqual(definition.cli_path, ("equity", "price", "history"))
        self.assertEqual(capability.result_contract, "history-bars")
        self.assertEqual(definition.request_schema.schema_name, "equity-price-history-request")
        self.assertEqual(definition.request_schema.field_map()["period"].default, "daily")
        self.assertEqual(definition.request_schema.field_map()["adjust"].default, "qfq")
        self.assertIn(BackendName.EFINANCE, definition.supported_backends)
        self.assertIn(BackendName.AKSHARE, definition.supported_backends)

    def test_request_schema_builds_click_options_and_validates_payload(self) -> None:
        """显式 schema 应能稳定生成 Click 参数并完成请求校验。"""
        schema = RequestSchema(
            schema_name="demo",
            fields=(
                RequestField("query", "query", str, required=True, help_text="查询词"),
                RequestField("result_count", "result-count", int, default=5, help_text="数量"),
                RequestField("use_local_cache", "use-local-cache", bool, default=True, help_text="缓存"),
            ),
        )
        options = build_click_options_for_schema(schema)
        validated = validate_request_data(
            schema,
            {
                "query": "AAPL",
                "result_count": "2",
                "use_local_cache": False,
            },
        )
        print_observation(
            "schema 选项与校验结果",
            {
                "option_names": [option.name for option in options],
                "validated": validated,
            },
        )
        self.assertEqual([option.name for option in options], ["query", "result_count", "use_local_cache"])
        self.assertEqual(validated["query"], "AAPL")
        self.assertEqual(validated["result_count"], 2)
        self.assertFalse(validated["use_local_cache"])

    def test_request_schema_rejects_unknown_fields(self) -> None:
        """schema 默认不允许未知字段穿透。"""
        schema = RequestSchema(
            schema_name="demo",
            fields=(RequestField("query", "query", str, required=True),),
        )
        with self.assertRaises(click.ClickException):
            validate_request_data(schema, {"query": "AAPL", "extra": "value"})

    def test_backend_resolver_enforces_support_matrix(self) -> None:
        """backend 解析应执行支持矩阵检查。"""
        definition = get_shared_command_definition("instrument.search")
        selection = resolve_backend_selection(definition, "efinance")
        print_observation(
            "backend 解析结果",
            {"requested": selection.requested.value, "resolved": selection.resolved.value, "source": selection.source},
        )
        self.assertEqual(selection.resolved, BackendName.EFINANCE)

    def test_provider_registry_exposes_efinance_and_akshare(self) -> None:
        """provider 注册表应暴露首批已知 backend。"""
        registry = list_backend_providers()
        print_observation("provider 注册表", list(registry))
        self.assertIn(BackendName.EFINANCE, registry)
        self.assertIn(BackendName.AKSHARE, registry)
        self.assertTrue(get_backend_provider(BackendName.EFINANCE).supports("instrument.search"))
        self.assertTrue(get_backend_provider(BackendName.AKSHARE).supports("instrument.search"))
        self.assertTrue(get_backend_provider(BackendName.EFINANCE).supports("equity.price.history"))
        self.assertTrue(get_backend_provider(BackendName.AKSHARE).supports("equity.price.history"))

    def test_facade_invokes_efinance_search_handler_and_returns_standard_result(self) -> None:
        """门面应能调度 `efinance` 搜索 handler 并返回标准结果。"""
        definition = get_shared_command_definition("instrument.search")
        selection = resolve_backend_selection(definition, BackendName.EFINANCE)
        facade = CommandFacade()
        records = [
            SearchRecord("AAPL", "Apple Inc.", "apple", "105.AAPL", "US_stock"),
            SearchRecord("MSFT", "Microsoft", "microsoft", "105.MSFT", "US_stock"),
        ]
        with patch("efinance.utils.search_quote", return_value=records):
            result = facade.invoke(
                definition,
                selection,
                {
                    "query": "AAPL",
                    "market": None,
                    "result_count": 2,
                    "use_local_cache": True,
                },
            )
        print_observation(
            "efinance 搜索标准结果",
            {
                "contract_name": result.contract_name,
                "row_count": len(result.data),
                "first_row": result.data[0],
            },
        )
        self.assertEqual(result.contract_name, SEARCH_RESULTS_CONTRACT.contract_name)
        self.assertEqual(len(result.data), 2)
        self.assertEqual(result.data[0]["code"], "AAPL")
        self.assertEqual(result.data[0]["quote_id"], "105.AAPL")

    def test_akshare_search_handler_returns_standard_result_with_mocked_catalogs(self) -> None:
        """`akshare` 搜索 handler 应能在打桩名录下返回标准搜索结果。"""
        definition = get_shared_command_definition("instrument.search")
        selection = resolve_backend_selection(definition, BackendName.AKSHARE)
        facade = CommandFacade()
        sh_df = pd.DataFrame(
            [
                {"证券代码": "600000", "证券简称": "浦发银行"},
                {"证券代码": "600519", "证券简称": "贵州茅台"},
            ]
        )
        sz_df = pd.DataFrame(
            [
                {"A股代码": "000001", "A股简称": "平安银行"},
            ]
        )
        fund_df = pd.DataFrame(
            [
                {"基金代码": "000001", "拼音缩写": "HXCZHH", "基金简称": "华夏成长混合", "基金类型": "混合型", "拼音全称": "HUAXIA"},
            ]
        )
        us_df = pd.DataFrame(
            [
                {"name": "Apple Inc.", "cname": "苹果", "symbol": "AAPL"},
            ]
        )
        mocked_akshare = type(
            "MockAkshare",
            (),
            {
                "stock_info_sh_name_code": staticmethod(lambda symbol="主板A股": sh_df),
                "stock_info_sz_name_code": staticmethod(lambda symbol="A股列表": sz_df),
                "fund_name_em": staticmethod(lambda: fund_df),
                "get_us_stock_name": staticmethod(lambda: us_df),
            },
        )()
        with patch("efinance_cli.backends.providers._load_akshare_module", return_value=mocked_akshare):
            result = facade.invoke(
                definition,
                selection,
                {
                    "query": "AAPL",
                    "market": None,
                    "result_count": 2,
                    "use_local_cache": True,
                },
            )
        print_observation("akshare 搜索标准结果", result.data)
        self.assertEqual(result.contract_name, SEARCH_RESULTS_CONTRACT.contract_name)
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0]["code"], "AAPL")
        self.assertEqual(result.data[0]["name"], "苹果")
        self.assertEqual(result.data[0]["classify"], "US_stock")

    def test_akshare_search_handler_filters_and_deduplicates_rows(self) -> None:
        """`akshare` 搜索 handler 应做模糊过滤与去重。"""
        handler = AkshareSearchHandler()
        us_df = pd.DataFrame(
            [
                {"name": "Apple Inc.", "cname": "苹果", "symbol": "AAPL"},
                {"name": "Apple Inc.", "cname": "苹果", "symbol": "AAPL"},
                {"name": "Microsoft", "cname": "微软", "symbol": "MSFT"},
            ]
        )
        rows = handler._standardize_catalog_rows(us_df, "US_stock")
        mocked_akshare = type(
            "MockAkshare",
            (),
            {
                "get_us_stock_name": staticmethod(lambda: us_df),
            },
        )()
        with patch("efinance_cli.backends.providers._load_akshare_module", return_value=mocked_akshare):
            result = handler.execute(
                {
                    "query": "app",
                    "market": "US_stock",
                    "result_count": 10,
                    "use_local_cache": True,
                }
            )
        print_observation(
            "akshare 过滤去重结果",
            {"rows": rows, "result": result.data},
        )
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0]["code"], "AAPL")

    def test_efinance_equity_history_handler_returns_standard_result(self) -> None:
        """`efinance` 权益历史 handler 应返回标准历史契约。"""
        definition = get_shared_command_definition("equity.price.history")
        selection = resolve_backend_selection(definition, BackendName.EFINANCE)
        facade = CommandFacade()
        frame = pd.DataFrame(
            [
                {
                    "日期": "2026-05-28",
                    "股票代码": "000001",
                    "开盘": 10.0,
                    "收盘": 10.5,
                    "最高": 10.6,
                    "最低": 9.9,
                    "成交量": 1000,
                    "成交额": 10000.0,
                    "振幅": 3.0,
                    "涨跌幅": 1.2,
                    "涨跌额": 0.12,
                    "换手率": 0.8,
                }
            ]
        )
        with patch("efinance.stock.get_quote_history", return_value=frame):
            result = facade.invoke(
                definition,
                selection,
                {
                    "symbol": "000001",
                    "market": "A_stock",
                    "start_date": "20260501",
                    "end_date": "20260528",
                    "period": "daily",
                    "adjust": "qfq",
                },
            )
        print_observation("efinance 权益历史标准结果", result.data)
        self.assertEqual(result.contract_name, "history-bars")
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0]["symbol"], "000001")
        self.assertEqual(result.data[0]["close"], 10.5)

    def test_akshare_equity_history_handler_returns_standard_result(self) -> None:
        """`akshare` 权益历史 handler 应返回标准历史契约。"""
        definition = get_shared_command_definition("equity.price.history")
        selection = resolve_backend_selection(definition, BackendName.AKSHARE)
        facade = CommandFacade()
        frame = pd.DataFrame(
            [
                {
                    "日期": "2026-05-28",
                    "股票代码": "000001",
                    "开盘": 10.0,
                    "收盘": 10.5,
                    "最高": 10.6,
                    "最低": 9.9,
                    "成交量": 1000,
                    "成交额": 10000.0,
                    "振幅": 3.0,
                    "涨跌幅": 1.2,
                    "涨跌额": 0.12,
                    "换手率": 0.8,
                }
            ]
        )
        mocked_akshare = type(
            "MockAkshare",
            (),
            {
                "stock_zh_a_hist": staticmethod(lambda **kwargs: frame),
            },
        )()
        with patch("efinance_cli.backends.providers._load_akshare_module", return_value=mocked_akshare):
            result = facade.invoke(
                definition,
                selection,
                {
                    "symbol": "000001",
                    "market": "A_stock",
                    "start_date": "20260501",
                    "end_date": "20260528",
                    "period": "daily",
                    "adjust": "none",
                },
            )
        print_observation("akshare 权益历史标准结果", result.data)
        self.assertEqual(result.contract_name, "history-bars")
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0]["symbol"], "000001")
        self.assertEqual(result.metadata["backend"], "akshare")

    def test_shared_executor_keeps_raw_payload_in_raw_view(self) -> None:
        """共享命令在 raw 视图下应保留标准结果封装中的原始 payload。"""
        from efinance_cli.executor import CommandExecutor
        from efinance_cli.models import (
            BackendSelection,
            CommandSpec,
            InvocationRequest,
            OutputOptions,
            WatchOptions,
        )

        definition = get_shared_command_definition("instrument.search")
        request = InvocationRequest(
            spec=CommandSpec(
                module_name="shared",
                function_name="instrument.search",
                callback=lambda **_: None,
                help_text=definition.help_text,
                cli_path=definition.cli_path,
            ),
            kwargs={
                "query": "AAPL",
                "market": None,
                "result_count": 1,
                "use_local_cache": True,
            },
            output=OutputOptions(format_name="json", view_mode="raw"),
            watch=WatchOptions(),
            command_definition=definition,
            backend_selection=BackendSelection(
                requested=BackendName.EFINANCE,
                resolved=BackendName.EFINANCE,
                source="explicit",
            ),
        )
        executor = CommandExecutor()
        records = [SearchRecord("AAPL", "Apple Inc.", "apple", "105.AAPL", "US_stock")]
        with patch("efinance.utils.search_quote", return_value=records):
            result = executor.invoke(request)
        print_observation("shared raw 视图结果", result.value)
        self.assertEqual(result.value["contract_name"], "search-results")
        self.assertIn("data", result.value)
        self.assertIn("raw_payload", result.value)
        self.assertIsInstance(result.value["data"], list)
        self.assertEqual(result.value["data"][0]["code"], "AAPL")

    def test_shared_history_standard_rows_can_enter_enrichment_pipeline(self) -> None:
        """共享历史标准字段结果应可直接进入增强链，而不必回投旧中文列。"""

        request = InvocationRequest(
            spec=CommandSpec(
                module_name="shared",
                function_name="equity.price.history",
                callback=lambda **_: None,
                help_text="test",
            ),
            kwargs={"symbol": "000001"},
            output=OutputOptions(indicator_level="basic", view_mode="raw"),
            watch=WatchOptions(),
        )
        frame = pd.DataFrame(
            [
                {"date": "2026-05-26", "symbol": "000001", "open": 10.0, "close": 10.2, "high": 10.3, "low": 9.9, "volume": 1000},
                {"date": "2026-05-27", "symbol": "000001", "open": 10.2, "close": 10.4, "high": 10.5, "low": 10.1, "volume": 1200},
                {"date": "2026-05-28", "symbol": "000001", "open": 10.4, "close": 10.6, "high": 10.7, "low": 10.3, "volume": 1400},
            ]
        )

        enriched = enrich_market_data(request, frame)
        print_observation("shared history enrichment frame", enriched.to_dict(orient="records"))
        self.assertIsInstance(enriched, pd.DataFrame)
        self.assertIn("close", enriched.columns)
        self.assertIn("ma5", enriched.columns)

    def test_standardization_requires_contract_core_fields(self) -> None:
        """标准契约缺少关键字段时应显式失败。"""
        from efinance_cli.contracts import ensure_mapping_has_required_fields

        with self.assertRaises(StandardizationError):
            ensure_mapping_has_required_fields({"name": "Only Name"}, SEARCH_RESULTS_CONTRACT)


if __name__ == "__main__":
    unittest.main()
