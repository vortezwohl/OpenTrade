"""backend 解析逻辑。"""

from __future__ import annotations

import click

from efinance_cli.command_catalog import get_shared_command_definition
from efinance_cli.models import BackendName, BackendSelection, CommandDefinition


DEFAULT_BACKEND = BackendName.EFINANCE


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
        normalized = DEFAULT_BACKEND
        source = "default"
    else:
        source = "explicit"

    if not definition.supports_backend(normalized):
        supported = ", ".join(item.value for item in definition.supported_backends)
        raise click.ClickException(
            f"Command '{definition.command_key}' does not support backend '{normalized.value}'. "
            f"Supported backends: {supported}"
        )
    return BackendSelection(requested=normalize_backend_name(requested_backend), resolved=normalized, source=source)
