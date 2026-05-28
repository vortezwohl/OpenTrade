"""efinance 底层网络调用的统一重试封装。

该模块只服务于一次性的原子网络调用，例如单次 `efinance` 函数调用或单次
HTTP 请求。它不负责包裹整条 CLI 执行链，避免把参数错误、渲染错误等非网络
问题错误地纳入重试范围。
"""

from __future__ import annotations

import inspect
import socket
import ssl
from functools import wraps
from typing import Any, Callable, TypeVar, cast

from requests.exceptions import RequestException
from urllib3.exceptions import (
    HTTPError as Urllib3HTTPError,
    MaxRetryError,
    NewConnectionError,
    ProtocolError,
    SSLError as Urllib3SSLError,
    TimeoutError as Urllib3TimeoutError,
)
from vortezwohl.func import Retry


F = TypeVar("F", bound=Callable[..., Any])

NETWORK_RELATED_EXCEPTIONS: tuple[type[BaseException], ...] = (
    RequestException,
    Urllib3HTTPError,
    Urllib3TimeoutError,
    Urllib3SSLError,
    ProtocolError,
    NewConnectionError,
    MaxRetryError,
    socket.timeout,
    socket.gaierror,
    ssl.SSLError,
    ConnectionError,
    TimeoutError,
)

_NETWORK_RETRY = Retry(max_retries=32, delay=True)


def with_network_retry(function: F) -> F:
    """为原子网络调用追加统一重试策略。

    Args:
        function: 需要补充网络重试能力的函数。

    Returns:
        保留原始签名的包装函数。
    """

    cached = getattr(function, "__efinance_network_retry_wrapper__", None)
    if cached is not None:
        return cast(F, cached)

    decorated = _NETWORK_RETRY.on_exceptions(*NETWORK_RELATED_EXCEPTIONS)(function)

    @wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return decorated(*args, **kwargs)

    wrapper.__signature__ = inspect.signature(function)
    setattr(function, "__efinance_network_retry_wrapper__", wrapper)
    return cast(F, wrapper)


def call_with_network_retry(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """立即以统一重试策略执行一次原子网络调用。"""

    return with_network_retry(function)(*args, **kwargs)
