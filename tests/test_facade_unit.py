"""CommandFacade 的独立单元测试。

验证 CommandFacade.invoke 在单后端成功/失败、auto failover、副作用命令等
场景下的正确行为。
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from opentrade.backends.base import BackendProvider, BackendRateLimitError, CapabilityHandler
from opentrade.command_catalog import get_shared_command_definition
from opentrade.facade import AutoBackendExecutionError, CommandFacade
from opentrade.models import (
    BackendName,
    BackendSelection,
    CommandDefinition,
    CommandKind,
    RequestSchema,
    StandardResult,
)
from tests.cli_regression_support import print_observation

try:
    from yfinance.exceptions import YFRateLimitError
except Exception:  # pragma: no cover - 测试环境缺依赖时回退
    class YFRateLimitError(Exception):
        """yfinance 不可用时的测试回退异常。"""


def _make_mock_handler(return_value: StandardResult | None = None, side_effect: Exception | None = None) -> CapabilityHandler:
    """构造一个可控的 mock handler。"""
    handler = MagicMock(spec=CapabilityHandler)
    if side_effect:
        handler.execute.side_effect = side_effect
    elif return_value:
        handler.execute.return_value = return_value
    else:
        handler.execute.return_value = StandardResult(contract_name="test", data=[])
    return handler


def _make_mock_provider(backend_name: BackendName, handler: CapabilityHandler) -> BackendProvider:
    """构造一个带有指定 handler 的 mock provider。"""
    provider = MagicMock(spec=BackendProvider)
    provider.get_handler.return_value = handler
    provider.execute.side_effect = lambda definition, request_data: handler.execute(request_data)
    provider.backend_name = backend_name
    return provider


class FacadeUnitTest(unittest.TestCase):
    """覆盖 CommandFacade.invoke 的核心路径。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.definition = get_shared_command_definition("stock.price.history")
        cls.facade = CommandFacade()

    # ------------------------------------------------------------------
    # 单后端成功
    # ------------------------------------------------------------------

    def test_single_backend_success(self) -> None:
        handler = _make_mock_handler(
            return_value=StandardResult(contract_name="history-bars", data=[{"close": 10.5}])
        )
        provider = _make_mock_provider(BackendName.EFINANCE, handler)

        backend = BackendSelection(
            requested=BackendName.EFINANCE,
            resolved=BackendName.EFINANCE,
            source="explicit",
        )

        with patch("opentrade.facade.get_backend_provider", return_value=provider):
            result = self.facade.invoke(self.definition, backend, {"stock_codes": ["000001"]})

        print_observation("单后端成功结果", {"contract_name": result.contract_name, "data": result.data})
        self.assertEqual(result.contract_name, "history-bars")
        self.assertEqual(backend.final_backend, BackendName.EFINANCE)

    # ------------------------------------------------------------------
    # 单后端失败
    # ------------------------------------------------------------------

    def test_single_backend_failure_propagates_exception(self) -> None:
        handler = _make_mock_handler(side_effect=RuntimeError("backend error"))
        provider = _make_mock_provider(BackendName.YFINANCE, handler)

        backend = BackendSelection(
            requested=BackendName.YFINANCE,
            resolved=BackendName.YFINANCE,
            source="explicit",
        )

        with patch("opentrade.facade.get_backend_provider", return_value=provider):
            with self.assertRaises(RuntimeError) as ctx:
                self.facade.invoke(self.definition, backend, {"stock_codes": ["AAPL"]})

        print_observation("单后端失败异常", str(ctx.exception))
        self.assertIn("backend error", str(ctx.exception))

    def test_single_backend_retry_exhaustion_preserves_provider_error(self) -> None:
        """provider 内部重试耗尽后应继续暴露最后一次 provider 异常。"""
        handler = _make_mock_handler(side_effect=BackendRateLimitError("Yahoo rate limited the request. Please retry later."))
        provider = BackendProvider(
            backend_name=BackendName.YFINANCE,
            handlers={self.definition.capability: handler},
        )
        provider.retry_policy.rate_limit_exceptions = (BackendRateLimitError,)

        backend = BackendSelection(
            requested=BackendName.YFINANCE,
            resolved=BackendName.YFINANCE,
            source="explicit",
        )

        with patch("opentrade.facade.get_backend_provider", return_value=provider):
            with patch("vortezwohl.func.retry.sleep", return_value=None):
                with self.assertRaises(BackendRateLimitError) as ctx:
                    self.facade.invoke(self.definition, backend, {"stock_codes": ["AAPL"]})

        print_observation("单后端重试耗尽最终异常", str(ctx.exception))
        self.assertIn("Yahoo rate limited", str(ctx.exception))

    def test_single_backend_passthrough_error_bypasses_retry(self) -> None:
        """命中 provider passthrough 策略的异常应直接透传且不重试。"""
        handler = _make_mock_handler(side_effect=ValueError("bad request"))
        provider = BackendProvider(
            backend_name=BackendName.YFINANCE,
            handlers={self.definition.capability: handler},
        )
        provider.retry_policy.retryable_exceptions = (ValueError,)
        provider.retry_policy.passthrough_exceptions = (ValueError,)

        backend = BackendSelection(
            requested=BackendName.YFINANCE,
            resolved=BackendName.YFINANCE,
            source="explicit",
        )

        with patch("opentrade.facade.get_backend_provider", return_value=provider):
            with patch("vortezwohl.func.retry.sleep", return_value=None):
                with self.assertRaises(ValueError) as ctx:
                    self.facade.invoke(self.definition, backend, {"stock_codes": ["AAPL"]})

        self.assertIn("bad request", str(ctx.exception))
        handler.execute.assert_called_once()

    # ------------------------------------------------------------------
    # auto failover
    # ------------------------------------------------------------------

    def test_auto_first_candidate_success(self) -> None:
        handler = _make_mock_handler(
            return_value=StandardResult(contract_name="history-bars", data=[{"close": 10.5}])
        )
        akshare_provider = _make_mock_provider(BackendName.AKSHARE, handler)

        backend = BackendSelection(
            requested=None,
            resolved=BackendName.AUTO,
            source="default",
            candidate_chain=(BackendName.AKSHARE, BackendName.EFINANCE),
        )

        with patch("opentrade.facade.get_backend_provider", return_value=akshare_provider):
            result = self.facade.invoke(self.definition, backend, {"stock_codes": ["000001"]})

        print_observation("auto 第一候选成功", {"final_backend": backend.final_backend.value})
        self.assertEqual(backend.final_backend, BackendName.AKSHARE)

    def test_auto_first_fails_second_succeeds(self) -> None:
        fail_handler = _make_mock_handler(side_effect=RuntimeError("akshare failed"))
        success_handler = _make_mock_handler(
            return_value=StandardResult(contract_name="history-bars", data=[{"close": 10.5}])
        )

        providers = {
            BackendName.AKSHARE: _make_mock_provider(BackendName.AKSHARE, fail_handler),
            BackendName.YFINANCE: _make_mock_provider(BackendName.YFINANCE, success_handler),
        }

        backend = BackendSelection(
            requested=None,
            resolved=BackendName.AUTO,
            source="default",
            candidate_chain=(BackendName.AKSHARE, BackendName.YFINANCE),
        )

        with patch("opentrade.facade.get_backend_provider", side_effect=lambda name: providers[name]):
            result = self.facade.invoke(self.definition, backend, {"stock_codes": ["000001"]})

        print_observation("auto 第二候选成功", {"final_backend": backend.final_backend.value})
        self.assertEqual(backend.final_backend, BackendName.YFINANCE)

    def test_auto_all_candidates_fail(self) -> None:
        fail_handler = _make_mock_handler(side_effect=RuntimeError("all failed"))

        providers = {
            BackendName.AKSHARE: _make_mock_provider(BackendName.AKSHARE, fail_handler),
            BackendName.YFINANCE: _make_mock_provider(BackendName.YFINANCE, fail_handler),
            BackendName.EFINANCE: _make_mock_provider(BackendName.EFINANCE, fail_handler),
        }

        backend = BackendSelection(
            requested=None,
            resolved=BackendName.AUTO,
            source="default",
            candidate_chain=(BackendName.AKSHARE, BackendName.YFINANCE, BackendName.EFINANCE),
        )

        with patch("opentrade.facade.get_backend_provider", side_effect=lambda name: providers[name]):
            with self.assertRaises(AutoBackendExecutionError) as ctx:
                self.facade.invoke(self.definition, backend, {"stock_codes": ["000001"]})

        message = str(ctx.exception)
        print_observation("全失败异常消息", message)
        for name in ("akshare", "yfinance", "efinance"):
            self.assertIn(name, message)

    def test_auto_ratelimit_error_fails_over_to_next_backend(self) -> None:
        fail_handler = _make_mock_handler(side_effect=YFRateLimitError())
        success_handler = _make_mock_handler(
            return_value=StandardResult(contract_name="history-bars", data=[{"close": 10.5}])
        )

        providers = {
            BackendName.YFINANCE: _make_mock_provider(BackendName.YFINANCE, fail_handler),
            BackendName.EFINANCE: _make_mock_provider(BackendName.EFINANCE, success_handler),
        }

        backend = BackendSelection(
            requested=None,
            resolved=BackendName.AUTO,
            source="default",
            candidate_chain=(BackendName.YFINANCE, BackendName.EFINANCE),
        )

        with patch("opentrade.facade.get_backend_provider", side_effect=lambda name: providers[name]):
            result = self.facade.invoke(self.definition, backend, {"stock_codes": ["AAPL"]})

        print_observation("auto 限流后继续兜底", {"final_backend": backend.final_backend.value})
        self.assertEqual(result.contract_name, "history-bars")
        self.assertEqual(backend.final_backend, BackendName.EFINANCE)

    def test_auto_retryable_network_error_after_internal_retry_still_fails_over(self) -> None:
        """当前 backend 内部重试耗尽后，若异常允许 failover，auto 仍继续下一候选。"""
        fail_handler = _make_mock_handler(side_effect=OSError("temporary failure"))
        success_handler = _make_mock_handler(
            return_value=StandardResult(contract_name="history-bars", data=[{"close": 10.5}])
        )

        retrying_provider = BackendProvider(
            backend_name=BackendName.AKSHARE,
            handlers={self.definition.capability: fail_handler},
        )
        retrying_provider.retry_policy.retryable_exceptions = (OSError,)

        providers = {
            BackendName.AKSHARE: retrying_provider,
            BackendName.EFINANCE: _make_mock_provider(BackendName.EFINANCE, success_handler),
        }

        backend = BackendSelection(
            requested=None,
            resolved=BackendName.AUTO,
            source="default",
            candidate_chain=(BackendName.AKSHARE, BackendName.EFINANCE),
        )

        with patch("opentrade.facade.get_backend_provider", side_effect=lambda name: providers[name]):
            with patch("vortezwohl.func.retry.sleep", return_value=None):
                result = self.facade.invoke(self.definition, backend, {"stock_codes": ["000001"]})

        self.assertEqual(result.contract_name, "history-bars")
        self.assertEqual(backend.final_backend, BackendName.EFINANCE)

    # ------------------------------------------------------------------
    # 副作用命令
    # ------------------------------------------------------------------

    def test_side_effect_command_skips_retry(self) -> None:
        """副作用命令通过 provider 执行入口执行，且仍只调用一次 handler。"""
        handler = _make_mock_handler(
            return_value=StandardResult(contract_name="side-effect-status", data=[{"status": "ok"}])
        )
        provider = _make_mock_provider(BackendName.EFINANCE, handler)

        definition = CommandDefinition(
            command_key="fund.reports.download",
            cli_path=("fund", "reports", "download"),
            capability="fund.reports.download",
            request_schema=RequestSchema(schema_name="test", fields=()),
            help_text="下载基金报告。",
            kind=CommandKind.PROVIDER_EXTENSION,
            supported_backends=(BackendName.EFINANCE,),
            allow_watch=False,
            has_side_effect=True,
            provider_name=BackendName.EFINANCE,
        )

        backend = BackendSelection(
            requested=BackendName.EFINANCE,
            resolved=BackendName.EFINANCE,
            source="explicit",
        )

        with patch("opentrade.facade.get_backend_provider", return_value=provider):
            result = self.facade.invoke(definition, backend, {"fund_code": "161725"})

        self.assertEqual(result.contract_name, "side-effect-status")
        provider.execute.assert_called_once()
        handler.execute.assert_called_once()


if __name__ == "__main__":
    unittest.main()
