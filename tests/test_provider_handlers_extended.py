"""Provider handler 覆盖率补充测试。

为 providers.py 中当前未直接测试的 6 个 handler 建立最小 mock 测试：
AkshareStockPriceLiveHandler、AkshareFundNavHistoryHandler、
AkshareStockProfileHandler、AkshareStockPriceHistoryHandler、
YfinanceRealtimeHandler、EfinanceGenericHandler。
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from opentrade.backends.providers import (
    _build_limited_efinance_live_frame,
    AkshareFundNavHistoryHandler,
    AkshareSearchHandler,
    AkshareStockPriceHistoryHandler,
    AkshareStockPriceLiveHandler,
    AkshareStockProfileHandler,
    EfinanceGenericHandler,
    build_efinance_provider,
    YfinanceRealtimeHandler,
)
from opentrade.command_catalog import get_command_binding, get_command_definition
from opentrade.models import EXECUTION_LIMIT_REQUEST_KEY
from tests.cli_regression_support import print_observation


class ProviderHandlersExtendedTest(unittest.TestCase):
    """覆盖 6 个当前未直接测试的 provider handler。"""

    # ------------------------------------------------------------------
    # AkshareStockPriceLiveHandler
    # ------------------------------------------------------------------

    def test_akshare_stock_price_live_handler_normalizes_fields(self) -> None:
        handler = AkshareStockPriceLiveHandler()
        mock_frame = pd.DataFrame(
            [
                {"代码": "000001", "名称": "平安银行", "最新价": 10.5, "今开": 10.3, "最高": 10.6, "最低": 10.2,
                 "成交量": 100000, "成交额": 1050000, "涨跌幅": 1.5, "涨跌额": 0.15, "换手率": 0.8, "振幅": 3.2},
            ]
        )

        with patch("opentrade.backends.providers._load_akshare_module") as mock_load:
            mock_akshare = MagicMock()
            mock_akshare.stock_zh_a_spot_em.return_value = mock_frame
            mock_load.return_value = mock_akshare

            result = handler.execute({"market": "A_stock"})
            mock_akshare.stock_zh_a_spot_em.assert_called_once_with()

        print_observation("AkshareStockPriceLive 结果", {
            "contract_name": result.contract_name,
            "row_count": len(result.data),
            "first_row_keys": list(result.data[0].keys()) if result.data else [],
        })

        self.assertEqual(result.contract_name, "realtime-quotes")
        self.assertGreater(len(result.data), 0)
        first = result.data[0]
        self.assertEqual(first["symbol"], "000001")
        self.assertEqual(first["name"], "平安银行")

    # ------------------------------------------------------------------
    # AkshareFundNavHistoryHandler
    # ------------------------------------------------------------------

    def test_akshare_fund_nav_history_handler_normalizes_result(self) -> None:
        handler = AkshareFundNavHistoryHandler()
        mock_frame = pd.DataFrame(
            [
                {"净值日期": "2025-01-02", "单位净值": 1.2345, "累计净值": 2.3456, "日增长率": 0.5},
                {"净值日期": "2025-01-03", "单位净值": 1.2400, "累计净值": 2.3500, "日增长率": 0.45},
            ]
        )

        with patch("opentrade.backends.providers._load_akshare_module") as mock_load:
            mock_akshare = MagicMock()
            mock_akshare.fund_open_fund_info_em.return_value = mock_frame
            mock_load.return_value = mock_akshare

            result = handler.execute({"symbol": "161725"})
            mock_akshare.fund_open_fund_info_em.assert_called_once_with(
                symbol="161725",
                indicator="\u5355\u4f4d\u51c0\u503c\u8d70\u52bf",
            )

        print_observation("AkshareFundNavHistory 结果", {
            "contract_name": result.contract_name,
            "row_count": len(result.data),
        })

        self.assertEqual(result.contract_name, "fund-nav-history")
        self.assertGreater(len(result.data), 0)

    # ------------------------------------------------------------------
    # AkshareStockProfileHandler
    # ------------------------------------------------------------------

    def test_akshare_stock_profile_handler_normalizes_result(self) -> None:
        handler = AkshareStockProfileHandler()
        mock_result = pd.DataFrame(
            [
                {"item": "股票代码", "value": "000001"},
                {"item": "股票简称", "value": "平安银行"},
                {"item": "市盈率-动态", "value": 5.2},
                {"item": "市净率", "value": 0.6},
                {"item": "总市值", "value": 3000000000000},
                {"item": "行业", "value": "银行"},
            ]
        )

        with patch("opentrade.backends.providers._load_akshare_module") as mock_load:
            mock_akshare = MagicMock()
            mock_akshare.stock_individual_info_em.return_value = mock_result
            mock_load.return_value = mock_akshare

            result = handler.execute({"symbol": "000001", "market": "A_stock"})
            mock_akshare.stock_individual_info_em.assert_called_once_with(symbol="000001")

        print_observation("AkshareStockProfile 结果", {
            "contract_name": result.contract_name,
        })

        self.assertEqual(result.contract_name, "profile-info")

    # ------------------------------------------------------------------
    # AkshareStockPriceHistoryHandler
    # ------------------------------------------------------------------

    def test_akshare_stock_price_history_handler_normalizes_result(self) -> None:
        handler = AkshareStockPriceHistoryHandler()
        mock_frame = pd.DataFrame(
            [
                {"日期": "2025-01-02", "开盘": 10.0, "收盘": 10.5, "最高": 10.6, "最低": 9.9,
                 "成交量": 100000, "成交额": 1050000, "振幅": 3.2, "涨跌幅": 1.5, "涨跌额": 0.15, "换手率": 0.8},
            ]
        )

        with patch("opentrade.backends.providers._load_akshare_module") as mock_load:
            mock_akshare = MagicMock()
            mock_akshare.stock_zh_a_hist.return_value = mock_frame
            mock_load.return_value = mock_akshare

            result = handler.execute({
                "symbols": ["000001"],
                "market": "A_stock",
                "start_date": "20250101",
                "end_date": "20250131",
                "timeframe": 101,
                "adjustment": 1,
            })
            mock_akshare.stock_zh_a_hist.assert_called_once_with(
                symbol="000001",
                period="daily",
                start_date="20250101",
                end_date="20250131",
                adjust="qfq",
            )

        print_observation("AkshareStockPriceHistory 结果", {
            "contract_name": result.contract_name,
            "row_count": len(result.data),
        })

        self.assertEqual(result.contract_name, "history-bars")
        self.assertGreater(len(result.data), 0)

    # ------------------------------------------------------------------
    # YfinanceRealtimeHandler
    # ------------------------------------------------------------------

    def test_yfinance_realtime_handler_normalizes_result(self) -> None:
        handler = YfinanceRealtimeHandler("stock.price.latest")

        with patch("opentrade.backends.providers._build_yfinance_ticker") as mock_ticker, \
             patch("opentrade.backends.providers._resolve_yfinance_realtime_symbols", return_value=["AAPL"]), \
             patch("opentrade.backends.providers._build_yfinance_realtime_row") as mock_row:
            mock_row.return_value = {"symbol": "AAPL", "name": "Apple Inc.", "close": 195.5}

            result = handler.execute({"symbols": ["AAPL"]})
            mock_ticker.assert_not_called()
            mock_row.assert_called_once_with("stock.price.latest", "AAPL")

        print_observation("YfinanceRealtime 结果", {
            "contract_name": result.contract_name,
            "first_row": result.data[0] if result.data else {},
        })

        self.assertEqual(result.contract_name, "realtime-quotes")
        self.assertGreater(len(result.data), 0)
        self.assertIn("symbol", result.data[0])

    # ------------------------------------------------------------------
    # EfinanceGenericHandler
    # ------------------------------------------------------------------

    def test_efinance_provider_execute_wraps_generic_handler_with_retry(self) -> None:
        """efinance provider 应在统一执行入口为普通命令挂载 retry。"""
        provider = build_efinance_provider()
        definition = get_command_definition("bond.catalog")

        mock_result = pd.DataFrame(
            [
                {"债券代码": "019641", "债券简称": "20国债01"},
            ]
        )

        with patch("efinance.bond.get_all_base_info", return_value=mock_result):
            with patch("vortezwohl.func.retry.sleep", return_value=None):
                result = provider.execute(definition, {})

        print_observation("efinance provider execute bond.catalog 结果", {
            "contract_name": result.contract_name,
        })

        cache_key = (
            definition.capability,
            provider.retry_policy.effective_retryable_exceptions,
            provider.retry_policy.passthrough_exceptions,
        )
        self.assertIn(cache_key, provider._retry_wrapper_cache)
        self.assertEqual(result.contract_name, "provider-records")

    def test_efinance_provider_execute_reuses_retry_wrapper_for_same_capability(self) -> None:
        """同一 capability 重复执行时应复用 provider 内部的稳定 retry wrapper。"""
        provider = build_efinance_provider()
        definition = get_command_definition("bond.catalog")
        handler = provider.get_handler(definition.capability)

        with patch("efinance.bond.get_all_base_info", return_value=pd.DataFrame([{"债券代码": "019641"}])):
            provider.execute(definition, {})
            wrapper = provider._retry_wrapper_cache[
                (
                    definition.capability,
                    provider.retry_policy.effective_retryable_exceptions,
                    provider.retry_policy.passthrough_exceptions,
                )
            ]
            provider.execute(definition, {})

        self.assertEqual(len(provider._retry_wrapper_cache), 1)
        cache_key = (
            definition.capability,
            provider.retry_policy.effective_retryable_exceptions,
            provider.retry_policy.passthrough_exceptions,
        )
        self.assertIn(cache_key, provider._retry_wrapper_cache)
        self.assertIs(provider._retry_wrapper_cache[cache_key], wrapper)

    def test_efinance_provider_execute_distinguishes_passthrough_cache_keys(self) -> None:
        """不同 passthrough 策略必须落到不同 provider wrapper cache key。"""
        provider = build_efinance_provider()
        definition = get_command_definition("bond.catalog")
        original_passthrough = provider.retry_policy.passthrough_exceptions

        with patch("efinance.bond.get_all_base_info", return_value=pd.DataFrame([{"债券代码": "019641"}])):
            provider.execute(definition, {})
            provider.retry_policy.passthrough_exceptions = (ValueError,)
            provider.execute(definition, {})

        self.assertEqual(len(provider._retry_wrapper_cache), 2)
        self.assertIn(
            (
                definition.capability,
                provider.retry_policy.effective_retryable_exceptions,
                original_passthrough,
            ),
            provider._retry_wrapper_cache,
        )
        self.assertIn(
            (
                definition.capability,
                provider.retry_policy.effective_retryable_exceptions,
                (ValueError,),
            ),
            provider._retry_wrapper_cache,
        )

    def test_efinance_provider_execute_skips_retry_for_side_effect_command(self) -> None:
        """副作用命令（如 fund.reports.download）应在 provider 入口跳过 retry。"""
        provider = build_efinance_provider()
        definition = get_command_definition("fund.reports.download")

        mock_result = {"status": "ok"}

        with patch("efinance.fund.get_pdf_reports", return_value=mock_result) as mock_fn:
            result = provider.execute(
                definition,
                {"fund_code": "161725", "max_count": 2, "save_dir": "pdf"},
            )

        print_observation("efinance provider execute side-effect 结果", {
            "contract_name": result.contract_name,
            "data": result.data,
        })

        self.assertEqual(provider._retry_wrapper_cache, {})
        mock_fn.assert_called_once()

    # ------------------------------------------------------------------
    # AkshareSearchHandler
    # ------------------------------------------------------------------

    def test_akshare_search_handler_reraises_retryable_network_error(self) -> None:
        """命中 provider retry policy 的网络异常应直接上抛。"""
        handler = AkshareSearchHandler()

        with patch.object(
            handler,
            "_build_catalog_loaders",
            return_value=[("A_stock", MagicMock(side_effect=OSError("catalog down")))],
        ):
            with patch("opentrade.backends.providers._load_akshare_module", return_value=MagicMock()):
                with self.assertRaises(OSError):
                    handler.execute({"keyword": "AAPL"})

    def test_akshare_search_handler_keeps_non_retryable_loader_errors_in_payload(self) -> None:
        """非 retryable 的目录局部失败仍可保留 errors 聚合并返回有效结果。"""
        handler = AkshareSearchHandler()
        success_frame = pd.DataFrame([{"A股代码": "AAPL", "A股简称": "Apple"}])

        with patch.object(
            handler,
            "_build_catalog_loaders",
            return_value=[
                ("A_stock", MagicMock(side_effect=RuntimeError("catalog unavailable"))),
                ("A_stock", MagicMock(return_value=success_frame)),
            ],
        ):
            with patch("opentrade.backends.providers._load_akshare_module", return_value=MagicMock()):
                result = handler.execute({"keyword": "AAPL", "market_type": "A_stock"})

        self.assertEqual(result.contract_name, "search-results")
        self.assertEqual(result.data[0]["code"], "AAPL")
        self.assertIn("catalog unavailable", result.raw_payload["errors"][0])

    def test_efinance_market_live_handler_applies_execution_limit(self) -> None:
        handler = EfinanceGenericHandler("market.price.live")
        limited_frame = pd.DataFrame(
            [
                {
                    "代码": "000001",
                    "名称": "平安银行",
                    "最新价": 10.5,
                    "涨跌幅": 1.2,
                    "行情ID": "0.000001",
                    "市场类型": "深A",
                }
            ]
        )

        with patch("opentrade.backends.providers._build_limited_efinance_live_frame", return_value=limited_frame) as mock_limit:
            result = handler.execute({"market": "A_stock", EXECUTION_LIMIT_REQUEST_KEY: 1})

        mock_limit.assert_called_once_with("沪深A股", 1)
        self.assertEqual(result.contract_name, "realtime-quotes")
        self.assertTrue(result.metadata["execution_limit_applied"])
        self.assertEqual(result.metadata["execution_limit_mode"], "provider-request")

    def test_limited_efinance_live_frame_derives_execution_columns(self) -> None:
        payload = {
            "data": {
                "diff": [
                    {"f12": "000001", "f14": "平安银行", "f3": 1.2, "f2": 10.5, "f13": 0, "f124": 1717400000, "f297": 20250603},
                    {"f12": "600519", "f14": "贵州茅台", "f3": 0.8, "f2": 1600.0, "f13": 1, "f124": 1717400100, "f297": 20250603},
                ]
            }
        }
        response = MagicMock()
        response.json.return_value = payload

        with patch("importlib.import_module") as mock_import:
            config_module = MagicMock()
            config_module.EASTMONEY_QUOTE_FIELDS = {
                "f12": "代码",
                "f14": "名称",
                "f3": "涨跌幅",
                "f2": "最新价",
                "f13": "市场编号",
                "f124": "更新时间戳",
                "f297": "最新交易日",
            }
            config_module.EASTMONEY_REQUEST_HEADERS = {}
            config_module.MARKET_NUMBER_DICT = {"0": "深A", "1": "沪A"}
            getter_module = MagicMock()
            getter_module.session.get.return_value = response
            mock_import.side_effect = lambda name: config_module if name == "efinance.common.config" else getter_module

            frame = _build_limited_efinance_live_frame("沪深A股", 1)

        self.assertEqual(len(frame), 1)
        self.assertIn("行情ID", frame.columns)
        self.assertIn("市场类型", frame.columns)
        self.assertIn("更新时间", frame.columns)
        self.assertEqual(frame.iloc[0]["代码"], "000001")


if __name__ == "__main__":
    unittest.main()
