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


def with_network_retry(
    function: F,
    retry_exceptions: tuple[type[BaseException], ...] | None = None,
) -> F:
    """为原子网络调用追加统一重试策略。

    Args:
        function: 需要补充网络重试能力的函数。
        retry_exceptions: 当前调用允许触发重试的异常集合；默认使用基础网络异常集合。

    Returns:
        保留原始签名的包装函数。
    """

    normalized_retry_exceptions = (
        NETWORK_RELATED_EXCEPTIONS if retry_exceptions is None else retry_exceptions
    )
    wrappers = getattr(function, NETWORK_RETRY_WRAPPERS_ATTR, None)
    if wrappers is None:
        wrappers = {}
        setattr(function, NETWORK_RETRY_WRAPPERS_ATTR, wrappers)

    cached = wrappers.get(normalized_retry_exceptions)
    if cached is not None:
        return cast(F, cached)

    @wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        last_error: BaseException | None = None

        def tracked_call(*call_args: Any, **call_kwargs: Any) -> Any:
            nonlocal last_error
            try:
                return function(*call_args, **call_kwargs)
            except BaseException as exc:  # noqa: BLE001
                last_error = exc
                raise

        decorated = _NETWORK_RETRY.on_exceptions(*normalized_retry_exceptions)(tracked_call)
        try:
            return decorated(*args, **kwargs)
        except MaxRetriesReachedError:
            if last_error is not None:
                raise last_error
            raise

    wrapper.__signature__ = inspect.signature(function)
    wrappers[normalized_retry_exceptions] = wrapper
    return cast(F, wrapper)


def call_with_network_retry(
    function: Callable[..., Any],
    *args: Any,
    retry_exceptions: tuple[type[BaseException], ...] | None = None,
    **kwargs: Any,
) -> Any:
    """立即以统一重试策略执行一次原子网络调用。"""

    return with_network_retry(function, retry_exceptions=retry_exceptions)(*args, **kwargs)
