"""后端无关共享命令目录。

该模块把仓库内维护的命令参考矩阵固化为运行时 command catalog。当前原则：

1. `shared` 只保留真正支持多 backend 的命令；
2. 仅支持单一 backend 的命令必须下沉到对应 provider 的 extension 命令集合；
3. 命令定义由显式元数据驱动，而不是由上游函数名动态反射。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from efinance_cli.models import (
    BackendName,
    CapabilityDescriptor,
    CommandDefinition,
    CommandKind,
    RequestField,
    RequestSchema,
)


REFERENCE_CATALOG_PATH = (
    Path(__file__).resolve().parent.parent
    / ".skill"
    / "efinance_cli"
    / "references"
    / "command-catalog.json"
)

_REFERENCE_CATALOG = json.loads(REFERENCE_CATALOG_PATH.read_text(encoding="utf-8"))

MARKET_CHOICES: tuple[str, ...] = tuple(_REFERENCE_CATALOG["market_enums"])

GROUP_HELP_TEXT: dict[str, str] = {
    name: str(payload.get("role", "")).strip() or f"{name} 命令分组。"
    for name, payload in _REFERENCE_CATALOG["top_level_commands"].items()
    if name not in {"search", "watch"}
}
GROUP_HELP_TEXT["watch"] = "为任意子命令开启循环刷新。"

SPECIAL_ROOT_GROUPS = {"instrument", "search", "watch"}

JSON_ANNOTATION_TO_TYPE: dict[str, Any] = {
    "StringParamType": str,
    "IntParamType": int,
    "FloatParamType": float,
    "BoolParamType": bool,
    "Choice": str,
}


def _supported_backends_for_command(command_path: str) -> tuple[BackendName, ...]:
    if command_path in {
        "stock price history",
        "stock profile",
        "fund nav history",
        "quote price history",
        "quote price latest",
        "quote profile",
        "fund profile",
        "stock price latest",
        "stock price snapshot",
    }:
        return (
            BackendName.EFINANCE,
            BackendName.AKSHARE,
            BackendName.YFINANCE,
        ) if command_path in {
            "stock price history",
            "stock profile",
            "fund nav history",
        } else (
            BackendName.EFINANCE,
            BackendName.YFINANCE,
        )
    if command_path == "stock price live":
        return (BackendName.EFINANCE, BackendName.AKSHARE)
    if command_path == "search":
        return (
            BackendName.EFINANCE,
            BackendName.AKSHARE,
            BackendName.YFINANCE,
        )
    return (BackendName.EFINANCE,)


def is_multi_backend_support(backends: tuple[BackendName, ...]) -> bool:
    """判断一条命令是否具备真正的多 backend 支持。"""

    return len(backends) >= 2


def _result_contract_for_command(command_key: str, cli_path: tuple[str, ...]) -> str:
    joined = ".".join(cli_path)
    if command_key == "instrument.search" or command_key == "search.local":
        return "search-results"
    if joined.endswith("nav.history"):
        return "fund-nav-history"
    if joined.endswith("price.history"):
        return "history-bars"
    if joined.endswith("price.live") or joined.endswith("price.latest"):
        return "realtime-quotes"
    if joined.endswith("profile"):
        return "profile-info"
    if joined == "resolve.quote-id":
        return "scalar-value"
    if joined in {"fund.disclosure.dates"}:
        return "scalar-list"
    if joined in {"fund.reports.download", "market.add"}:
        return "side-effect-status"
    return "provider-records"


def _build_request_field(parameter: dict[str, Any]) -> RequestField:
    annotation_name = str(parameter.get("annotation", "StringParamType"))
    annotation = JSON_ANNOTATION_TO_TYPE.get(annotation_name, str)
    legal_values = parameter.get("legal_values")
    choices = tuple(legal_values) if isinstance(legal_values, list) else ()
    if str(parameter.get("name")) == "fs":
        choices = ()
    default = parameter.get("default")
    if isinstance(default, bool):
        annotation = bool
    elif isinstance(default, int) and annotation is str:
        annotation = int
    elif isinstance(default, float) and annotation is str:
        annotation = float
    if parameter.get("multiple") and isinstance(default, list):
        default = tuple(default)
    return RequestField(
        name=str(parameter["name"]),
        cli_name=str(parameter["cli_name"]),
        annotation=annotation,
        required=bool(parameter.get("required", False)),
        default=default,
        help_text=str(parameter.get("description", "")).strip(),
        choices=choices,
        multiple=bool(parameter.get("multiple", False)),
    )


def _command_key_for_path(command_path: str) -> str:
    if command_path == "search local":
        return "search.local"
    return command_path.replace(" ", ".")


def _cli_path_for_path(command_path: str) -> tuple[str, ...]:
    if command_path == "search local":
        return ("search", "local")
    return tuple(command_path.split())


def _build_command_from_reference(entry: dict[str, Any]) -> CommandDefinition:
    command_path = str(entry["command_path"])
    command_key = _command_key_for_path(command_path)
    cli_path = _cli_path_for_path(command_path)
    supported_backends = _supported_backends_for_command(command_path)
    return CommandDefinition(
        command_key=command_key,
        cli_path=cli_path,
        capability=command_key,
        request_schema=RequestSchema(
            schema_name=f"{command_key.replace('.', '-')}-request",
            fields=tuple(_build_request_field(item) for item in entry.get("parameters", [])),
        ),
        help_text=str(entry.get("help_text", "")).strip(),
        kind=(
            CommandKind.SHARED
            if is_multi_backend_support(supported_backends)
            else CommandKind.PROVIDER_EXTENSION
        ),
        supported_backends=supported_backends,
        allow_watch=bool(entry.get("watch_supported", True)),
        has_side_effect=bool(entry.get("has_side_effect", False)),
        provider_name=(
            None
            if is_multi_backend_support(supported_backends)
            else supported_backends[0]
        ),
    )


DEFAULT_SEARCH_COMMAND = CommandDefinition(
    command_key="instrument.search",
    cli_path=("instrument", "search"),
    capability="instrument.search",
    request_schema=RequestSchema(
        schema_name="instrument-search-request",
        fields=(
            RequestField(
                name="keyword",
                cli_name="query",
                annotation=str,
                required=True,
                help_text="搜索关键字。",
            ),
            RequestField(
                name="market_type",
                cli_name="market",
                annotation=str | None,
                default=None,
                choices=MARKET_CHOICES,
                help_text="市场枚举名。",
            ),
            RequestField(
                name="count",
                cli_name="result-count",
                annotation=int,
                default=5,
                help_text="返回候选数量。",
            ),
            RequestField(
                name="use_local",
                cli_name="use-local-cache",
                annotation=bool,
                default=True,
                help_text="是否允许使用本地缓存。",
            ),
        ),
    ),
    help_text="根据关键字搜索证券候选项。",
    kind=CommandKind.SHARED,
    supported_backends=(
        BackendName.EFINANCE,
        BackendName.AKSHARE,
        BackendName.YFINANCE,
    ),
    allow_watch=True,
    has_side_effect=False,
)


SHARED_COMMANDS: tuple[CommandDefinition, ...] = (
    DEFAULT_SEARCH_COMMAND,
    *tuple(
        _build_command_from_reference(entry)
        for entry in _REFERENCE_CATALOG["commands"]
        if entry["command_path"] != "watch"
        and is_multi_backend_support(_supported_backends_for_command(str(entry["command_path"])))
    ),
)

SINGLE_BACKEND_COMMANDS: tuple[CommandDefinition, ...] = tuple(
    _build_command_from_reference(entry)
    for entry in _REFERENCE_CATALOG["commands"]
    if entry["command_path"] != "watch"
    and not is_multi_backend_support(_supported_backends_for_command(str(entry["command_path"])))
)

COMMAND_BINDINGS: dict[str, dict[str, str | None]] = {
    DEFAULT_SEARCH_COMMAND.command_key: {"module": "utils", "function": "search_quote"},
}
for entry in _REFERENCE_CATALOG["commands"]:
    command_path = str(entry["command_path"])
    if command_path == "watch":
        continue
    COMMAND_BINDINGS[_command_key_for_path(command_path)] = {
        "module": entry.get("module"),
        "function": entry.get("function"),
    }


SHARED_CAPABILITIES: dict[str, CapabilityDescriptor] = {
    command.command_key: CapabilityDescriptor(
        capability_name=command.capability,
        description=command.help_text,
        result_contract=_result_contract_for_command(command.command_key, command.cli_path),
    )
    for command in SHARED_COMMANDS
}

SINGLE_BACKEND_CAPABILITIES: dict[str, CapabilityDescriptor] = {
    command.command_key: CapabilityDescriptor(
        capability_name=command.capability,
        description=command.help_text,
        result_contract=_result_contract_for_command(command.command_key, command.cli_path),
    )
    for command in SINGLE_BACKEND_COMMANDS
}


def list_shared_root_groups() -> list[str]:
    """返回当前共享命令树的根分组。"""

    roots = sorted(
        {
            command.root_group
            for command in SHARED_COMMANDS
            if command.root_group not in SPECIAL_ROOT_GROUPS
        }
    )
    return roots


def build_shared_command_definitions_for_group(group_name: str) -> list[CommandDefinition]:
    """按根分组返回共享命令定义。"""

    return sorted(
        [command for command in SHARED_COMMANDS if command.root_group == group_name],
        key=lambda item: item.cli_path,
    )


def get_shared_command_definition(command_key: str) -> CommandDefinition:
    """按稳定命令键返回共享命令定义。"""

    for command in SHARED_COMMANDS:
        if command.command_key == command_key:
            return command
    raise KeyError(f"未知共享命令: {command_key}")


def get_command_definition(command_key: str) -> CommandDefinition:
    """按稳定命令键返回任意命令定义。"""

    for command in SHARED_COMMANDS:
        if command.command_key == command_key:
            return command
    for command in SINGLE_BACKEND_COMMANDS:
        if command.command_key == command_key:
            return command
    raise KeyError(f"未知命令定义: {command_key}")


def get_single_backend_command_definitions(
    provider_name: BackendName | None = None,
) -> tuple[CommandDefinition, ...]:
    """返回单 backend 命令定义，可按 provider 过滤。"""

    if provider_name is None:
        return SINGLE_BACKEND_COMMANDS
    return tuple(
        command
        for command in SINGLE_BACKEND_COMMANDS
        if command.provider_name == provider_name
    )


def get_capability_descriptor(capability_name: str) -> CapabilityDescriptor:
    """返回 capability 描述。"""

    try:
        return SHARED_CAPABILITIES[capability_name]
    except KeyError:
        pass
    try:
        return SINGLE_BACKEND_CAPABILITIES[capability_name]
    except KeyError as exc:
        raise KeyError(f"未知 capability: {capability_name}") from exc


def get_command_binding(command_key: str) -> dict[str, str | None]:
    """返回命令键绑定的上游来源信息。"""

    try:
        return COMMAND_BINDINGS[command_key]
    except KeyError as exc:
        raise KeyError(f"未知命令绑定: {command_key}") from exc
