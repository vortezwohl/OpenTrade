"""backend 解析逻辑。"""

from __future__ import annotations

import click

from efinance_cli.backends.factory import list_backend_providers
from efinance_cli.command_catalog import get_shared_command_definition
from efinance_cli.models import BackendName, BackendSelection, CommandDefinition


DEFAULT_BACKEND = BackendName.AUTO
AUTO_CANDIDATE_ORDER: tuple[BackendName, ...] = (
    BackendName.AKSHARE,
    BackendName.YFINANCE,
    BackendName.EFINANCE,
)


def normalize_backend_name(value: str | BackendName | None) -> BackendName | None:
    """把用户输入规范化为 `BackendName`。"""

    if value is None:
        return None
    if isinstance(value, BackendName):
        return value
    lowered = str(value).strip().lower()
    for member in BackendName:
        if member.value == lowered:
            return member
    raise click.ClickException(f"Unknown backend: {value}")


def _build_auto_candidate_chain(definition: CommandDefinition) -> tuple[BackendName, ...]:
    """基于支持矩阵与当前注册表构造 auto 候选链。"""

    registry = list_backend_providers()
    return tuple(
        backend_name
        for backend_name in AUTO_CANDIDATE_ORDER
        if definition.supports_backend(backend_name) and backend_name in registry
    )


def resolve_backend_selection(
    command_definition: CommandDefinition | str,
    requested_backend: str | BackendName | None,
) -> BackendSelection:
    """根据命令定义和用户输入解析 backend。"""

    definition = (
        get_shared_command_definition(command_definition)
        if isinstance(command_definition, str)
        else command_definition
    )
    normalized = normalize_backend_name(requested_backend)
    if normalized is None:
        if definition.kind.value == "provider-extension" and definition.provider_name is not None:
            normalized = definition.provider_name
            source = "command-default"
        else:
            normalized = DEFAULT_BACKEND
            source = "default"
    else:
        if (
            normalized == BackendName.AUTO
            and definition.kind.value == "provider-extension"
            and definition.provider_name is not None
        ):
            normalized = definition.provider_name
            source = "auto-adapted"
        else:
            source = "explicit"

    candidate_chain: tuple[BackendName, ...] = ()
    if normalized == BackendName.AUTO:
        candidate_chain = _build_auto_candidate_chain(definition)
        if not candidate_chain:
            supported = ", ".join(item.value for item in definition.supported_backends)
            raise click.ClickException(
                f"命令 '{' '.join(definition.cli_path)}' 没有可用的 auto backend 候选。"
                f"支持的 backend: {supported}"
            )

    if normalized != BackendName.AUTO and not definition.supports_backend(normalized):
        supported = ", ".join(item.value for item in definition.supported_backends)
        if definition.kind.value == "provider-extension" and definition.provider_name is not None:
            default_backend = definition.provider_name.value
            raise click.ClickException(
                f"命令 '{' '.join(definition.cli_path)}' 仅支持 backend: {supported}。"
                f"该命令默认会路由到 '{default_backend}'，请不要显式传入 --backend {normalized.value}。"
            )
        raise click.ClickException(
            f"命令 '{' '.join(definition.cli_path)}' 不支持 backend '{normalized.value}'。"
            f"支持的 backend: {supported}"
        )
    return BackendSelection(
        requested=normalize_backend_name(requested_backend),
        resolved=normalized,
        source=source,
        candidate_chain=candidate_chain,
        final_backend=(normalized if normalized != BackendName.AUTO else None),
    )
