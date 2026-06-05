"""Provider contract truthfulness 修复回归测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from opentrade.backends.akshare_provider import (
    AkshareSearchHandler,
    _adapt_akshare_stock_history_request,
    _adapt_akshare_stock_profile_request,
)
from opentrade.backends.base import BackendName, ProviderContractError
from opentrade.backends.efinance_provider import (
    _adapt_efinance_request,
    _resolve_efinance_quote_id,
    _resolve_efinance_quote_ids,
)
from opentrade.backends.yfinance_provider import (
    _adapt_yfinance_fund_nav_history_request,
    _adapt_yfinance_fund_profile_request,
    _adapt_yfinance_history_request,
    _adapt_yfinance_profile_request,
    _adapt_yfinance_realtime_request,
)


class ProviderContractsFixTest(unittest.TestCase):
    """覆盖 provider 契约收口后的关键回归。"""

    def test_efinance_quote_price_latest_translates_symbols_to_quote_ids(self) -> None:
        with patch(
            "opentrade.backends.efinance_provider.efinance.utils.get_quote_id",
            side_effect=lambda symbol: f"resolved:{symbol}",
        ) as mock_get_quote_id:
            adapted = _adapt_efinance_request(
                "quote.price.latest",
                {"symbols": ["000001", "AAPL"]},
            )

        self.assertEqual(
            adapted,
            {"quote_id_list": ["resolved:000001", "resolved:AAPL"]},
        )
        self.assertEqual(mock_get_quote_id.call_count, 2)

    def test_efinance_quote_profile_translates_symbol_to_quote_id(self) -> None:
        with patch(
            "opentrade.backends.efinance_provider.efinance.utils.get_quote_id",
            return_value="resolved:000001",
        ):
            adapted = _adapt_efinance_request(
                "quote.profile",
                {"symbol": "000001"},
            )

        self.assertEqual(adapted, {"quote_id": "resolved:000001"})

    def test_efinance_quote_id_helpers_only_consume_shared_symbols(self) -> None:
        with patch(
            "opentrade.backends.efinance_provider.efinance.utils.get_quote_id",
            side_effect=lambda symbol: f"qid:{symbol}",
        ):
            self.assertEqual(
                _resolve_efinance_quote_ids(
                    {"symbols": ["000001", "AAPL"]},
                    "quote.price.latest",
                ),
                ["qid:000001", "qid:AAPL"],
            )
            self.assertEqual(
                _resolve_efinance_quote_id(
                    {"symbol": "000001"},
                    "quote.profile",
                ),
                "qid:000001",
            )

    def test_yfinance_history_request_translates_a_share_symbol_to_ticker(self) -> None:
        adapted = _adapt_yfinance_history_request(
            "stock.price.history",
            {
                "symbols": ["000001"],
                "market": "A_stock",
                "start_date": "20250501",
                "end_date": "20250530",
            },
        )
        self.assertEqual(adapted["symbol"], "000001")
        self.assertEqual(adapted["ticker"], "000001.SZ")

    def test_yfinance_quote_profile_uses_shared_symbol_not_quote_id_field(self) -> None:
        adapted = _adapt_yfinance_profile_request(
            "quote.profile",
            {
                "symbol": "600519",
                "market": "A_stock",
            },
        )
        self.assertEqual(adapted["symbol"], "600519")
        self.assertEqual(adapted["ticker"], "600519.SS")

    def test_yfinance_stock_profile_adds_hk_suffix_without_length_check(self) -> None:
        adapted = _adapt_yfinance_profile_request(
            "stock.profile",
            {
                "symbol": "700",
                "market": "Hongkong",
            },
        )
        self.assertEqual(adapted["symbol"], "700")
        self.assertEqual(adapted["ticker"], "700.HK")

    def test_yfinance_realtime_request_rejects_multi_symbol_path(self) -> None:
        with self.assertRaises(ProviderContractError) as ctx:
            _adapt_yfinance_realtime_request(
                "quote.price.latest",
                {
                    "symbols": ["AAPL", "MSFT"],
                },
            )
        self.assertIn("只支持单个标的", str(ctx.exception))

    def test_yfinance_realtime_request_uses_shared_symbol_and_translated_ticker(self) -> None:
        adapted = _adapt_yfinance_realtime_request(
            "quote.price.latest",
            {
                "symbols": ["000001"],
                "market": "A_stock",
            },
        )
        self.assertEqual(
            adapted["symbols"],
            [{"symbol": "000001", "ticker": "000001.SZ"}],
        )

    def test_yfinance_fund_profile_request_returns_symbol_and_ticker(self) -> None:
        adapted = _adapt_yfinance_fund_profile_request({"symbol": "VTI"})
        self.assertEqual(adapted, {"symbol": "VTI", "ticker": "VTI"})

    def test_yfinance_fund_profile_rejects_mainland_fund_code(self) -> None:
        with self.assertRaises(ProviderContractError) as ctx:
            _adapt_yfinance_fund_profile_request({"symbol": "161725"})
        self.assertIn("Yahoo", str(ctx.exception))

    def test_yfinance_fund_nav_history_rejects_mainland_fund_code(self) -> None:
        with self.assertRaises(ProviderContractError) as ctx:
            _adapt_yfinance_fund_nav_history_request({"symbol": "005827"})
        self.assertIn("Yahoo", str(ctx.exception))

    def test_yfinance_intraday_history_rejects_oversized_window(self) -> None:
        with self.assertRaises(ProviderContractError) as ctx:
            _adapt_yfinance_history_request(
                "stock.price.history",
                {
                    "symbols": ["AAPL"],
                    "market": "US_stock",
                    "start_date": "20250101",
                    "end_date": "20250501",
                    "timeframe": 5,
                },
            )
        self.assertIn("60", str(ctx.exception))

    def test_akshare_stock_history_rejects_unstable_a_share_symbol(self) -> None:
        with self.assertRaises(ProviderContractError) as ctx:
            _adapt_akshare_stock_history_request(
                {
                    "symbols": ["430047"],
                    "market": "A_stock",
                }
            )
        self.assertIn("provider-contract-error", str(ctx.exception))

    def test_akshare_stock_profile_rejects_unstable_a_share_symbol(self) -> None:
        with self.assertRaises(ProviderContractError) as ctx:
            _adapt_akshare_stock_profile_request(
                {
                    "symbol": "430047",
                    "market": "A_stock",
                }
            )
        self.assertIn("provider-contract-error", str(ctx.exception))

    def test_akshare_fund_search_uses_name_and_pinyin_columns(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "基金代码": "161725",
                    "基金简称": "招商中证白酒指数",
                    "拼音缩写": "ZSBJ",
                }
            ]
        )
        rows = AkshareSearchHandler()._standardize_catalog_rows(frame, "fund")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "161725")
        self.assertEqual(rows[0]["name"], "招商中证白酒指数")
        self.assertEqual(rows[0]["pinyin"], "ZSBJ")
        self.assertEqual(rows[0]["classify"], "fund")


if __name__ == "__main__":
    unittest.main()
