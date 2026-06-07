"""程序化 Python API 的单元测试。

这些测试聚焦新增 `OpenTrade` 对象式入口的三个核心目标：

1. 顶层导入稳定且简单；
2. 命名空间对象清晰、便于 IDE 发现；
3. 调用路径复用现有执行链，而不是重新发明一套运行时。
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from opentrade import OpenTrade
from opentrade.models import InvocationResult


class PythonApiTest(unittest.TestCase):
    """覆盖程序化 API 的顶层导入与代表性调用路径。"""

    def test_top_level_import_exposes_open_trade(self) -> None:
        """顶层包应显式暴露 `OpenTrade`。"""
        client = OpenTrade()
        self.assertIsInstance(client, OpenTrade)

    def test_namespaces_are_discoverable(self) -> None:
        """`OpenTrade` 应暴露稳定命名空间属性。"""
        client = OpenTrade()
        for name in (
            "search",
            "quote",
            "stock",
            "fund",
            "bond",
            "futures",
            "market",
            "resolve",
        ):
            self.assertTrue(hasattr(client, name), msg=name)

    def test_api_has_no_watch_namespace(self) -> None:
        """程序化 API 不应暴露 watch 入口。"""
        client = OpenTrade()
        self.assertFalse(hasattr(client, "watch"))

    def test_representative_shared_calls_route_through_executor(self) -> None:
        """代表性 shared command 应复用统一执行链。"""
        captured: list[dict[str, object]] = []

        def fake_invoke(self, request):  # noqa: ANN001
            captured.append(
                {
                    "command_key": request.command_definition.command_key,
                    "kwargs": dict(request.kwargs),
                    "backend": request.backend_selection.resolved.value,
                    "view": request.output.view_mode,
                    "watch": request.watch.enabled,
                }
            )
            return InvocationResult(value={"ok": True})

        client = OpenTrade()
        with patch("opentrade.executor.CommandExecutor.invoke", new=fake_invoke):
            client.search.instruments("AAPL", result_count=3)
            client.stock.price_history(["AAPL"], backend="yfinance")
            client.quote.price_latest(["AAPL"])
            client.resolve.quote_id("000001")

        self.assertEqual(
            [item["command_key"] for item in captured],
            [
                "instrument.search",
                "stock.price.history",
                "quote.price.latest",
                "resolve.quote-id",
            ],
        )
        self.assertEqual(captured[0]["kwargs"]["keyword"], "AAPL")
        self.assertEqual(captured[1]["backend"], "yfinance")
        self.assertEqual(captured[1]["kwargs"]["symbols"], ["AAPL"])
        self.assertEqual(captured[2]["view"], "raw")
        self.assertFalse(any(item["watch"] for item in captured))

    def test_extension_calls_route_through_executor(self) -> None:
        """代表性 provider extension 也应走统一执行链。"""
        captured: list[dict[str, object]] = []

        def fake_invoke(self, request):  # noqa: ANN001
            captured.append(
                {
                    "command_key": request.command_definition.command_key,
                    "kwargs": dict(request.kwargs),
                    "backend": request.backend_selection.resolved.value,
                }
            )
            return InvocationResult(value={"ok": True})

        client = OpenTrade()
        with patch("opentrade.executor.CommandExecutor.invoke", new=fake_invoke):
            client.search.local("平安银行")
            client.stock.industry_boards()
            client.quote.news("AAPL")

        self.assertEqual(
            [item["command_key"] for item in captured],
            [
                "search.local",
                "akshare.industry.boards",
                "yfinance.quote.news",
            ],
        )
        self.assertEqual(captured[0]["backend"], "efinance")
        self.assertEqual(captured[1]["backend"], "akshare")
        self.assertEqual(captured[2]["backend"], "yfinance")

    def test_backend_resolution_matches_existing_cli_semantics(self) -> None:
        """程序化 API 应沿用现有 backend 默认与自适应语义。"""
        captured: list[dict[str, object]] = []

        def fake_invoke(self, request):  # noqa: ANN001
            captured.append(
                {
                    "command_key": request.command_definition.command_key,
                    "backend": request.backend_selection.resolved.value,
                    "source": request.backend_selection.source,
                }
            )
            return InvocationResult(value={"ok": True})

        client = OpenTrade()
        with patch("opentrade.executor.CommandExecutor.invoke", new=fake_invoke):
            client.stock.price_history(["000001"])
            client.search.local("平安银行")
            client.quote.news("AAPL", backend="auto")

        self.assertEqual(
            captured,
            [
                {
                    "command_key": "stock.price.history",
                    "backend": "auto",
                    "source": "default",
                },
                {
                    "command_key": "search.local",
                    "backend": "efinance",
                    "source": "command-default",
                },
                {
                    "command_key": "yfinance.quote.news",
                    "backend": "yfinance",
                    "source": "auto-adapted",
                },
            ],
        )

    def test_indicator_subpackage_boundary_stays_unchanged(self) -> None:
        """技术指标仍应通过子包导入，而不是挂到顶层对象式入口。"""
        from opentrade import indicators

        client = OpenTrade()
        self.assertTrue(hasattr(indicators, "macd"))
        self.assertTrue(hasattr(indicators, "rsi"))
        self.assertFalse(hasattr(client, "macd"))


if __name__ == "__main__":
    unittest.main()
