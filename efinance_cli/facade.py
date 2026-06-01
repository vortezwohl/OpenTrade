"""统一命令门面。

命令层只需要关心“命令定义 + backend 选择 + 请求数据”，provider 查找与 handler 调用
都应由门面协调，避免再把 backend 条件分支散落回命令回调中。
"""

from __future__ import annotations

import click

from efinance_cli.backends.factory import get_backend_provider
from efinance_cli.models import BackendName, BackendSelection, CommandDefinition, StandardResult


class AutoBackendExecutionError(RuntimeError):
    """表示 auto 候选链全部失败。"""

    def __init__(self, attempts: list[tuple[BackendName, Exception]]) -> None:
        self.attempts = attempts
        lines = ["auto backend 候选链全部失败："]
        for backend_name, exc in attempts:
            lines.append(f"- {backend_name.value}: {exc}")
        super().__init__("\n".join(lines))


def is_failover_eligible_error(exc: Exception) -> bool:
    """判断异常是否允许进入下一个 auto 候选 backend。"""

    if isinstance(exc, click.ClickException):
        return False
    if isinstance(exc, ValueError):
        return False
    if isinstance(exc, TypeError):
        return False
    if isinstance(exc, KeyError):
        return True
    if isinstance(exc, RuntimeError):
        return True
    if isinstance(exc, OSError):
        return True
    return False


class CommandFacade:
    """统一命令调用入口。"""

    def invoke(
        self,
        definition: CommandDefinition,
        backend: BackendSelection,
        request_data: dict[str, object],
    ) -> StandardResult:
        """执行命令定义绑定的 capability。"""

        backend.final_backend = None if backend.is_auto else backend.resolved
        if backend.is_auto:
            return self._invoke_auto(definition, backend, request_data)
        return self._invoke_single_backend(definition, backend, request_data)

    def _invoke_single_backend(
        self,
        definition: CommandDefinition,
        backend: BackendSelection,
        request_data: dict[str, object],
    ) -> StandardResult:
        """执行单个 concrete backend。"""

        provider = get_backend_provider(backend.resolved)
        handler = provider.get_handler(definition.capability)
        result = handler.execute(request_data)
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
        for candidate in backend.candidate_chain:
            provider = get_backend_provider(candidate)
            try:
                handler = provider.get_handler(definition.capability)
                result = handler.execute(request_data)
            except Exception as exc:
                attempts.append((candidate, exc))
                if not is_failover_eligible_error(exc):
                    raise
                continue
            backend.final_backend = candidate
            return result
        raise AutoBackendExecutionError(attempts)
