"""\u540e\u7aef\u9009\u62e9\u89e3\u6790\u3002

\u8be5\u6a21\u5757\u53ea\u8d1f\u8d23\u628a\u7528\u6237\u4f20\u5165\u7684 `--backend` \u89e3\u6790\u6210\u7a33\u5b9a\u7684\u540e\u7aef\u9009\u62e9\u7ed3\u679c\uff0c
\u4e0d\u5728\u8fd9\u91cc\u751f\u6210 auto \u5019\u9009\u94fe\u3002\u8bf7\u6c42\u611f\u77e5\u7684 auto \u8def\u7531\u4f1a\u5728 schema \u5f52\u4e00\u5316\u4e4b\u540e\u518d\u89c4\u5212\u3002
"""

from __future__ import annotations

import click

from opentrade.command_catalog import get_shared_command_definition
from opentrade.models import BackendName, BackendSelection, CommandDefinition


DEFAULT_BACKEND = BackendName.AUTO


def normalize_backend_name(value: str | BackendName | None) -> BackendName | None:
    """\u628a\u7528\u6237\u8f93\u5165\u5f52\u4e00\u5316\u4e3a `BackendName`\u3002"""

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
    """\u89e3\u6790\u547d\u4ee4\u672c\u6b21\u6267\u884c\u5e94\u4f7f\u7528\u7684\u540e\u7aef\u9009\u62e9\u7ed3\u679c\u3002"""

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

    if normalized != BackendName.AUTO and not definition.supports_backend(normalized):
        supported = ", ".join(item.value for item in definition.supported_backends)
        if definition.kind.value == "provider-extension" and definition.provider_name is not None:
            default_backend = definition.provider_name.value
            raise click.ClickException(
                f"\u547d\u4ee4 '{' '.join(definition.cli_path)}' \u4ec5\u652f\u6301 backend: {supported}\u3002"
                f" \u9ed8\u8ba4\u4f1a\u8def\u7531\u5230 '{default_backend}'\uff1b\u5982\u679c\u60f3\u663e\u5f0f\u6307\u5b9a\uff0c\u8bf7\u4f7f\u7528 --backend {default_backend}\u3002"
            )
        raise click.ClickException(
            f"\u547d\u4ee4 '{' '.join(definition.cli_path)}' \u4e0d\u652f\u6301 backend '{normalized.value}'\u3002"
            f" \u53ef\u7528 backend: {supported}"
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
