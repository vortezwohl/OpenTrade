"""后端选择解析。

该模块只负责把用户传入的 `--backend` 解析成稳定的后端选择结果，
不在这里生成 auto 候选链。请求感知的 auto 路由会在 schema
归一化之后再规划。
"""

from __future__ import annotations

import click

from opentrade.command_catalog import get_shared_command_definition
from opentrade.models import BackendName, BackendSelection, CommandDefinition

DEFAULT_BACKEND = BackendName.AUTO


def normalize_backend_name(
    value: str | BackendName | None
) -> BackendName | None:
    """把用户输入归一化为 `BackendName`。"""
    if value is None:
        return None
    if isinstance(value, BackendName):
        return value
    lowered = str(value).strip().lower()
    for member in BackendName:
        if member.value == lowered:
            return member
    raise click.ClickException(f"Unknown backend: {value}")


def resolve_backend_selection(
    command_definition: CommandDefinition | str,
    requested_backend: str | BackendName | None,
) -> BackendSelection:
    """解析命令本次执行应使用的后端选择结果。"""
    definition = (
        get_shared_command_definition(command_definition)
        if isinstance(command_definition, str) else command_definition
    )
    normalized = normalize_backend_name(requested_backend)
    if normalized is None:
        if (
            definition.kind.value == "provider-extension"
            and definition.provider_name is not None
        ):
            normalized = definition.provider_name
            source = "command-default"
        else:
            normalized = DEFAULT_BACKEND
            source = "default"
    else:
        if (normalized == BackendName.AUTO
                and definition.kind.value == "provider-extension"
                and definition.provider_name is not None):
            normalized = definition.provider_name
            source = "auto-adapted"
        else:
            source = "explicit"

    if (
        normalized != BackendName.AUTO
        and not definition.supports_backend(normalized)
    ):
        supported = ", ".join(
            item.value for item in definition.supported_backends
        )
        if (
            definition.kind.value == "provider-extension"
            and definition.provider_name is not None
        ):
            default_backend = definition.provider_name.value
            raise click.ClickException(
                f"命令 '{' '.join(definition.cli_path)}' 仅支持 backend: "
                f"{supported}。默认会路由到 '{default_backend}'；"
                f"如果想显式指定，请使用 --backend {default_backend}。"
            )
        raise click.ClickException(
            f"命令 '{' '.join(definition.cli_path)}' 不支持 backend "
            f"'{normalized.value}'。可用 backend: {supported}"
        )
    return BackendSelection(
        requested=normalize_backend_name(requested_backend),
        resolved=normalized,
        source=source,
        candidate_chain=(),
        attempted_candidates=[],
        final_backend=(normalized if normalized != BackendName.AUTO else None),
        fallback_used=False,
    )
