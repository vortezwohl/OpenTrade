"""命令执行门面。

这里屏蔽 provider registry、backend 调度和自动 failover 细节，
让执行器只需要按命令定义和请求数据完成一次能力调用。
"""

from __future__ import annotations

import click

from opentrade.backends.base import (
    BackendRateLimitError,
    ProviderContractError,
    ProviderFailure,
)
from opentrade.backends.factory import get_backend_provider
from opentrade.models import (
    BackendName,
    BackendSelection,
    CommandDefinition,
    EXECUTION_LIMIT_REQUEST_KEY,
    StandardResult,
)


class AutoBackendExecutionError(RuntimeError):
    """表示 auto 候选链全部执行失败。"""

    def __init__(self, attempts: list[tuple[BackendName, Exception]]) -> None:
        self.attempts = attempts
        lines = ["auto backend 候选全部执行失败"]
        for backend_name, exc in attempts:
            lines.append(f"- {backend_name.value}: {exc}")
        super().__init__("\n".join(lines))


def is_failover_eligible_error(exc: Exception) -> bool:
    """判断异常是否允许 auto 继续切换 backend。

    只有已分类的 provider 失败和明确的远端故障才继续 failover； 本地契约错误和原始输入/参数错误会立即停止。
    """
    if isinstance(exc, (click.ClickException, ProviderContractError)):
        return False
    if isinstance(exc, (ProviderFailure, BackendRateLimitError, OSError)):
        return True
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return False
    return False


class CommandFacade:
    """协调命令定义与 backend 调用。"""

    def invoke(
        self,
        definition: CommandDefinition,
        backend: BackendSelection,
        request_data: dict[str, object],
        *,
        execution_limit: int | None = None,
    ) -> StandardResult:
        """执行一次 capability 调用。"""
        provider_request = dict(request_data)
        if execution_limit is not None:
            provider_request[EXECUTION_LIMIT_REQUEST_KEY] = execution_limit

        backend.final_backend = None if backend.is_auto else backend.resolved
        backend.attempted_candidates.clear()
        backend.fallback_used = False
        if backend.is_auto:
            return self._invoke_auto(definition, backend, provider_request)
        return self._invoke_single_backend(
            definition, backend, provider_request
        )

    def _invoke_single_backend(
        self,
        definition: CommandDefinition,
        backend: BackendSelection,
        request_data: dict[str, object],
    ) -> StandardResult:
        """执行单个 concrete backend。"""
        provider = get_backend_provider(backend.resolved)
        result = provider.execute(definition, request_data)
        backend.final_backend = backend.resolved
        return result

    def _invoke_auto(
        self,
        definition: CommandDefinition,
        backend: BackendSelection,
        request_data: dict[str, object],
    ) -> StandardResult:
        """按 auto 候选链依次尝试 backend。"""
        attempts: list[tuple[BackendName, Exception]] = []
        for index, candidate in enumerate(backend.candidate_chain):
            provider = get_backend_provider(candidate)
            backend.attempted_candidates.append(candidate)
            try:
                result = provider.execute(definition, request_data)
            except Exception as exc:
                attempts.append((candidate, exc))
                if not is_failover_eligible_error(exc):
                    raise
                continue
            backend.final_backend = candidate
            backend.fallback_used = index > 0
            return result
        raise AutoBackendExecutionError(attempts)
