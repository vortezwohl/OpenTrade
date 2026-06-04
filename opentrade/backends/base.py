"""多后端 provider 的基础协议与实现骨架。

该模块定义新的最小调用单元：

- `CapabilityHandler`：处理单个 capability；
- `BackendProvider`：声明 provider 身份、支持矩阵和扩展命令占位；
- `ProviderContractError` / `ProviderFailure`：把本地适配期失败与上游执行期失败分层，供 facade 判断是否允许 auto failover。

当前阶段使用普通基类而不是协议或抽象基类，是为了让首批骨架更容易落地和打桩测试。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from opentrade.models import BackendName, CommandDefinition, StandardResult
from opentrade.retry_utils import with_network_retry


class BackendRateLimitError(RuntimeError):
    """表示 backend 在网络访问阶段命中了限流。"""


class ProviderContractError(ValueError):
    """表示 provider 适配阶段发现的本地契约错误。

    这类错误说明当前 normalized request 无法被该 backend 在本地语义上正确消费，
    例如单标的/多标的形状不匹配、共享 market 无法映射或 provider 特定参数
    约束不满足。它不属于上游执行失败，因此 auto 不应继续 failover。
    """

    failure_kind = "provider-contract-error"

    def __init__(
        self,
        backend_name: BackendName,
        command_key: str,
        stage: str,
        detail: str,
    ) -> None:
        self.backend_name = backend_name
        self.command_key = command_key
        self.stage = stage
        self.detail = detail
        message = (
            f"{backend_name.value} {command_key} {self.failure_kind} at {stage}: {detail}"
        )
        super().__init__(message)


class ProviderFailure(RuntimeError):
    """表示 provider 执行期的可归类失败。

    这类异常用于把“本地契约不满足”和“第三方 provider/上游执行失败”分开。
    facade 不再仅依赖原始 Python 异常类型判断 failover，而是优先看失败来源语义。
    """

    failure_kind = "provider-failure"

    def __init__(
        self,
        backend_name: BackendName,
        command_key: str,
        stage: str,
        detail: str,
    ) -> None:
        self.backend_name = backend_name
        self.command_key = command_key
        self.stage = stage
        self.detail = detail
        message = (
            f"{backend_name.value} {command_key} {self.failure_kind} at {stage}: {detail}"
        )
        super().__init__(message)


class ProviderExecutionError(ProviderFailure):
    """表示第三方 callback 执行过程中发生的 provider 失败。"""

    failure_kind = "provider-execution-failure"


class ProviderResponseError(ProviderFailure):
    """表示第三方返回值在标准化阶段暴露出的 provider 响应失败。"""

    failure_kind = "provider-response-failure"


@dataclass(slots=True)
class ProviderRetryPolicy:
    """描述 provider 级统一重试策略。

    Args:
        retryable_exceptions: 允许自动重试的异常集合。
        rate_limit_exceptions: 限流异常集合，语义上属于可重试错误的一部分。
        passthrough_exceptions: 必须直接透传、不得进入自动重试的异常集合。
            当前主要用于 `ProviderContractError` 这类本地契约错误。
    """

    retryable_exceptions: tuple[type[BaseException], ...] = ()
    rate_limit_exceptions: tuple[type[BaseException], ...] = ()
    passthrough_exceptions: tuple[type[BaseException], ...] = ()

    @property
    def effective_retryable_exceptions(self) -> tuple[type[BaseException], ...]:
        """返回合并后的可重试异常集合，并去重保持顺序稳定。"""

        merged: list[type[BaseException]] = []
        for item in self.retryable_exceptions + self.rate_limit_exceptions:
            if item not in merged:
                merged.append(item)
        return tuple(merged)


class CapabilityHandler:
    """定义 capability handler 的最小接口。"""

    capability_name: str

    def execute(self, request_data: dict[str, Any]) -> StandardResult:
        """执行能力请求并返回标准结果。"""

        raise NotImplementedError


@dataclass(slots=True)
class BackendProvider:
    """定义 backend provider 的稳定元数据与 handler 注册表。

    Args:
        backend_name: provider 名称。
        handlers: capability -> handler 映射。
        extension_commands: provider 专属扩展命令定义。
        retry_policy: provider 级统一重试策略。
    """

    backend_name: BackendName
    handlers: dict[str, CapabilityHandler] = field(default_factory=dict)
    extension_commands: tuple[CommandDefinition, ...] = field(default_factory=tuple)
    retry_policy: ProviderRetryPolicy = field(default_factory=ProviderRetryPolicy)
    _retry_wrapper_cache: dict[
        tuple[
            str,
            tuple[type[BaseException], ...],
            tuple[type[BaseException], ...],
        ],
        Callable[[dict[str, Any]], StandardResult],
    ] = field(default_factory=dict, init=False, repr=False)

    def supports(self, capability_name: str) -> bool:
        """判断 provider 是否支持指定 capability。"""

        return capability_name in self.handlers

    def get_handler(self, capability_name: str) -> CapabilityHandler:
        """返回 capability handler。"""

        try:
            return self.handlers[capability_name]
        except KeyError as exc:
            raise KeyError(
                f"Backend '{self.backend_name.value}' 不支持 capability '{capability_name}'"
            ) from exc

    def execute(
        self,
        definition: CommandDefinition,
        request_data: dict[str, Any],
    ) -> StandardResult:
        """通过 provider 统一执行入口调用 capability handler。

        Args:
            definition: 当前命令定义，用于识别 capability 与 side-effect 边界。
            request_data: 已通过 schema 校验的业务请求数据。

        Returns:
            handler 返回的标准结果。

        Raises:
            Exception: 透传 handler 自身错误，或在重试耗尽后保留原有异常语义。
        """

        handler = self.get_handler(definition.capability)
        if definition.has_side_effect:
            return handler.execute(request_data)

        policy = self.retry_policy
        effective_retryable = policy.effective_retryable_exceptions
        if not effective_retryable:
            return handler.execute(request_data)

        wrapped = self._get_retry_wrapper(
            definition.capability,
            handler,
            effective_retryable,
            policy.passthrough_exceptions,
        )
        return wrapped(request_data)

    def _get_retry_wrapper(
        self,
        capability_name: str,
        handler: CapabilityHandler,
        retry_exceptions: tuple[type[BaseException], ...],
        passthrough_exceptions: tuple[type[BaseException], ...],
    ) -> Callable[[dict[str, Any]], StandardResult]:
        """返回当前 handler 的稳定重试包装器。"""

        cache_key = (capability_name, retry_exceptions, passthrough_exceptions)
        cached = self._retry_wrapper_cache.get(cache_key)
        if cached is not None:
            return cached

        def invoke(request_data: dict[str, Any]) -> StandardResult:
            return handler.execute(request_data)

        wrapped = with_network_retry(
            invoke,
            retry_exceptions=retry_exceptions,
            passthrough_exceptions=passthrough_exceptions,
        )
        self._retry_wrapper_cache[cache_key] = wrapped
        return wrapped
