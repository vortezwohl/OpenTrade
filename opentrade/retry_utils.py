"""后端无关的原子网络调用重试工具。

该模块只负责为单次、可独立重放的网络调用补充统一退避重试能力，例如单次
provider handler 调用、单次 HTTP 请求或单次第三方 SDK 访问。

它不负责：

- 判断命令是否具有副作用；
- 决定哪些 provider 异常属于可重试或必须直接透传；
- 处理多 backend `auto` failover。

这些运行时策略由 provider 执行入口和 facade 协调，本模块只提供最小、可复用
的重试包装能力。
"""

from __future__ import annotations

import inspect
from functools import wraps
from http.client import BadStatusLine, IncompleteRead
from typing import Any, Callable, TypeVar, cast

from urllib3.exceptions import HTTPError as Urllib3HTTPError
from vortezwohl.func import Retry
from vortezwohl.func.retry import MaxRetriesReachedError


F = TypeVar("F", bound=Callable[..., Any])
NETWORK_RETRY_WRAPPERS_ATTR = "__network_retry_wrappers__"

NETWORK_RELATED_EXCEPTIONS: tuple[type[BaseException], ...] = (
    Urllib3HTTPError,
    OSError,
    IncompleteRead,
    BadStatusLine,
)

_NETWORK_RETRY = Retry(max_retries=8, delay=True)


class _PassthroughSignal(BaseException):
    """用于让 passthrough 异常绕过三方 Retry 的内部信号。"""

    def __init__(self, error: BaseException) -> None:
        super().__init__(str(error))
        self.error = error


def with_network_retry(
    function: F,
    retry_exceptions: tuple[type[BaseException], ...] | None = None,
    passthrough_exceptions: tuple[type[BaseException], ...] = (),
) -> F:
    """为原子网络调用追加统一重试策略。

    Args:
        function: 需要补充网络重试能力的函数。
        retry_exceptions: 当前调用允许触发重试的异常集合；默认使用基础网络异常集合。
        passthrough_exceptions: 命中后必须直接透传、不得进入自动重试的异常集合。

    Returns:
        保留原始签名的包装函数。
    """

    normalized_retry_exceptions = (
        NETWORK_RELATED_EXCEPTIONS if retry_exceptions is None else retry_exceptions
    )
    cache_key = (normalized_retry_exceptions, passthrough_exceptions)
    wrappers = getattr(function, NETWORK_RETRY_WRAPPERS_ATTR, None)
    if wrappers is None:
        wrappers = {}
        setattr(function, NETWORK_RETRY_WRAPPERS_ATTR, wrappers)

    cached = wrappers.get(cache_key)
    if cached is not None:
        return cast(F, cached)

    last_error_ref: dict[str, BaseException | None] = {"error": None}

    def tracked_call(*args: Any, **kwargs: Any) -> Any:
        try:
            return function(*args, **kwargs)
        except passthrough_exceptions as exc:
            raise _PassthroughSignal(exc) from exc
        except BaseException as exc:  # noqa: BLE001
            last_error_ref["error"] = exc
            raise

    decorated = (
        _NETWORK_RETRY.on_exceptions(*normalized_retry_exceptions)(tracked_call)
        if normalized_retry_exceptions
        else tracked_call
    )

    @wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        last_error_ref["error"] = None
        try:
            return decorated(*args, **kwargs)
        except _PassthroughSignal as signal:
            raise signal.error
        except MaxRetriesReachedError:
            if last_error_ref["error"] is not None:
                raise last_error_ref["error"]
            raise

    wrapper.__signature__ = inspect.signature(function)
    wrappers[cache_key] = wrapper
    return cast(F, wrapper)


def call_with_network_retry(
    function: Callable[..., Any],
    *args: Any,
    retry_exceptions: tuple[type[BaseException], ...] | None = None,
    passthrough_exceptions: tuple[type[BaseException], ...] = (),
    **kwargs: Any,
) -> Any:
    """立即以统一重试策略执行一次原子网络调用。"""

    return with_network_retry(
        function,
        retry_exceptions=retry_exceptions,
        passthrough_exceptions=passthrough_exceptions,
    )(*args, **kwargs)
