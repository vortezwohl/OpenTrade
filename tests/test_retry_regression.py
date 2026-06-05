"""统一网络重试工具的回归测试。

legacy registry 命令树已下线后，这里只验证仍然真实存在的重试边界：

- 包装前后签名保持稳定；
- 在短时网络抖动下会按配置恢复；
- 超过上限后会显式失败；
- 网络异常注册表保持最小且不重复。
"""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import MagicMock, patch

from requests.exceptions import ConnectionError

from opentrade.retry_utils import (
    NETWORK_RELATED_EXCEPTIONS,
    NETWORK_RETRY_WRAPPERS_ATTR,
    _NETWORK_RETRY,
    call_with_network_retry,
    with_network_retry,
)
from tests.cli_regression_support import print_observation


def _render_wrapper_keys(
    wrappers: dict[object, object]
) -> list[tuple[object, ...]]:
    """把 wrapper cache key 渲染成便于断言与观察的结构。"""
    rendered: list[tuple[object, ...]] = []
    for key in wrappers:
        parts: list[object] = []
        for item in key:
            if isinstance(item, tuple):
                parts.append(tuple(member.__name__ for member in item))
            else:
                parts.append(item)
        rendered.append(tuple(parts))
    return rendered


def build_flaky_network_call(failures_before_success: int):
    """构造一个前若干次失败、随后成功的原子网络调用样本。"""
    state = {"count": 0}

    def flaky() -> str:
        state["count"] += 1
        if state["count"] <= failures_before_success:
            raise ConnectionError(f"transient failure #{state['count']}")
        return "ok"

    return flaky, state


class RetryRegressionTest(unittest.TestCase):
    """验证统一网络重试封装的行为边界。"""

    def test_with_network_retry_preserves_original_signature(self) -> None:
        """包装后函数应保留原始签名。"""

        def sample(symbol: str, limit: int = 10) -> str:
            return f"{symbol}:{limit}"

        wrapped = with_network_retry(sample)
        print_observation(
            "retry 包装前后签名",
            {
                "original": str(inspect.signature(sample)),
                "wrapped": str(inspect.signature(wrapped)),
            },
        )
        self.assertEqual(inspect.signature(sample), inspect.signature(wrapped))

    def test_with_network_retry_reuses_cached_wrapper_for_same_exception_set(
        self
    ) -> None:
        """同一异常集合重复包装时应复用缓存 wrapper。"""

        def sample() -> str:
            return "ok"

        wrapped_1 = with_network_retry(sample)
        wrapped_2 = with_network_retry(sample)

        wrappers = getattr(sample, NETWORK_RETRY_WRAPPERS_ATTR)
        print_observation(
            "retry wrapper cache keys", _render_wrapper_keys(wrappers)
        )
        self.assertIs(wrapped_1, wrapped_2)
        self.assertEqual(len(wrappers), 1)

    def test_with_network_retry_distinguishes_passthrough_exception_sets(
        self
    ) -> None:
        """不同 passthrough 集合不得复用同一个 wrapper。"""

        def sample() -> str:
            return "ok"

        wrapped_1 = with_network_retry(
            sample, passthrough_exceptions=(ValueError, )
        )
        wrapped_2 = with_network_retry(
            sample, passthrough_exceptions=(TypeError, )
        )
        wrappers = getattr(sample, NETWORK_RETRY_WRAPPERS_ATTR)

        self.assertIsNot(wrapped_1, wrapped_2)
        self.assertIn((NETWORK_RELATED_EXCEPTIONS, (ValueError, )), wrappers)
        self.assertIn((NETWORK_RELATED_EXCEPTIONS, (TypeError, )), wrappers)

    def test_with_network_retry_keeps_empty_retry_exception_tuple_distinct(
        self
    ) -> None:
        """显式空异常集合应表示禁用自动重试，而不是回退到默认集合。"""

        def sample() -> str:
            raise ConnectionError("fail once")

        wrapped = with_network_retry(sample, retry_exceptions=())
        wrappers = getattr(sample, NETWORK_RETRY_WRAPPERS_ATTR)
        print_observation(
            "retry wrapper empty-exception keys",
            _render_wrapper_keys(wrappers)
        )
        self.assertIn(((), ()), wrappers)
        with self.assertRaises(ConnectionError):
            wrapped()

    def test_with_network_retry_passthrough_exceptions_bypass_retry(
        self
    ) -> None:
        """命中 passthrough 异常时应直接透传，且不进入自动重试。"""
        state = {"count": 0}

        def sample() -> str:
            state["count"] += 1
            raise ValueError("bad request")

        wrapped = with_network_retry(
            sample,
            retry_exceptions=(ValueError, ),
            passthrough_exceptions=(ValueError, ),
        )

        with patch("vortezwohl.func.retry.sleep", return_value=None):
            with self.assertRaises(ValueError):
                wrapped()

        self.assertEqual(state["count"], 1)

    def test_with_network_retry_reuses_stable_retry_decorator_across_calls(
        self
    ) -> None:
        """同一 wrapper 多次调用时不应重复构造底层 decorator。"""

        def sample() -> str:
            return "ok"

        original_on_exceptions = _NETWORK_RETRY.on_exceptions
        on_exceptions_spy = MagicMock(wraps=original_on_exceptions)

        with patch.object(_NETWORK_RETRY, "on_exceptions", on_exceptions_spy):
            wrapped = with_network_retry(sample)
            wrapped()
            wrapped()

        self.assertEqual(on_exceptions_spy.call_count, 1)

    def test_retry_limit_recovers_after_transient_failures(
        self,
    ) -> None:
        """当前策略应能容忍前 max_retries 次瞬时失败，并在下一次成功时恢复。"""
        max_retries = getattr(_NETWORK_RETRY, "_max_retries", 0)
        flaky, state = build_flaky_network_call(
            failures_before_success=max_retries
        )
        with patch("vortezwohl.func.retry.sleep", return_value=None):
            result = call_with_network_retry(flaky)

        print_observation(
            "retry 上限后恢复",
            {
                "result": result,
                "attempts": state["count"]
            },
        )
        self.assertEqual(result, "ok")
        self.assertEqual(state["count"], max_retries + 1)

    def test_retry_limit_still_fails_after_transient_failures(
        self,
    ) -> None:
        """超过上限时应恢复抛出最后一次真实异常。"""
        max_retries = getattr(_NETWORK_RETRY, "_max_retries", 0)
        flaky, state = build_flaky_network_call(
            failures_before_success=max_retries + 1
        )
        with patch("vortezwohl.func.retry.sleep", return_value=None):
            with self.assertRaises(ConnectionError) as ctx:
                call_with_network_retry(flaky)

        print_observation(
            "retry 超上限失败次数", {
                "attempts": state["count"],
                "error": str(ctx.exception)
            }
        )
        self.assertEqual(state["count"], max_retries + 1)

    def test_network_exception_registry_contains_only_base_network_exceptions(
        self
    ) -> None:
        """网络异常集合应只保留不可再折叠的基类。"""
        names = sorted(
            {
                f"{item.__module__}.{item.__name__}"
                for item in NETWORK_RELATED_EXCEPTIONS
            }
        )
        print_observation("network exception registry", names)
        self.assertEqual(
            names,
            [
                "builtins.OSError",
                "http.client.BadStatusLine",
                "http.client.IncompleteRead",
                "urllib3.exceptions.HTTPError",
            ],
        )
        self.assertEqual(len(NETWORK_RELATED_EXCEPTIONS), 4)
        self.assertFalse(
            any(
                any(
                    (other is not item) and issubclass(other, item)
                    for other in NETWORK_RELATED_EXCEPTIONS
                ) for item in NETWORK_RELATED_EXCEPTIONS
            )
        )


if __name__ == "__main__":
    unittest.main()
