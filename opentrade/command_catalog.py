"""共享命令目录与运行时命令元数据。

这个模块负责读取仓库内维护的 command catalog，并把它们构造成统一的运行时定义。

1. `shared` 命令使用统一 schema 和 backend 支持矩阵；
2. 单后端命令继续作为 provider 的 extension 能力暴露；
3. shared 层只保留 provider-neutral 字段，provider 原生参数留在适配层。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from opentrade.models import (
    BackendName,
    CapabilityDescriptor,
    CommandDefinition,
    CommandKind,
    LimitStrategy,
    RequestField,
    RequestSchema,
)


REFERENCE_CATALOG_PATH = (
    Path(__file__).resolve().parent / "metadata" / "command-catalog.json"
)

_REFERENCE_CATALOG = json.loads(REFERENCE_CATALOG_PATH.read_text(encoding="utf-8"))

MARKET_CHOICES: tuple[str, ...] = tuple(_REFERENCE_CATALOG["market_enums"])

GROUP_HELP_TEXT: dict[str, str] = {
    name: str(payload.get("role", "")).strip() or f"{name} 命令组"
    for name, payload in _REFERENCE_CATALOG["top_level_commands"].items()
    if name not in {"search", "watch"}
}
GROUP_HELP_TEXT["watch"] = "循环刷新执行支持 watch 的命令"

SPECIAL_ROOT_GROUPS = {"instrument", "search", "watch"}

SINGLE_BACKEND_LIMIT_STRATEGIES: dict[str, str] = {
    "market price live": LimitStrategy.PROVIDER_REQUEST.value,
    "bond price live": LimitStrategy.PROVIDER_REQUEST.value,
    "futures price live": LimitStrategy.PROVIDER_REQUEST.value,
}

JSON_ANNOTATION_TO_TYPE: dict[str, Any] = {
    "StringParamType": str,
    "IntParamType": int,
    "FloatParamType": float,
    "BoolParamType": bool,
    "Choice": str,
}

SHARED_COMMAND_CONFIGS: dict[str, dict[str, Any]] = {
    "instrument.search": {
        "cli_path": ("instrument", "search"),
        "help_text": "按关键词搜索可交易标的",
        "supported_backends": (
            BackendName.EFINANCE,
            BackendName.AKSHARE,
            BackendName.YFINANCE,
        ),
        "limit_strategy": LimitStrategy.ADAPTER_LIGHTWEIGHT.value,
        "fields": (
            RequestField(
                name="keyword",
                cli_name="query",
                annotation=str,
                required=True,
                help_text="搜索关键词",
                semantic_type="keyword",
                legacy_names=("query",),
            ),
            RequestField(
                name="market",
                cli_name="market",
                annotation=str | None,
                default=None,
                choices=MARKET_CHOICES,
                help_text="市场枚举",
                semantic_type="market",
                legacy_names=("market_type",),
            ),
            RequestField(
                name="result_count",
                cli_name="result-count",
                annotation=int,
                default=5,
                help_text="返回结果数量",
                semantic_type="result-count",
                legacy_names=("count",),
            ),
            RequestField(
                name="use_local_cache",
                cli_name="use-local-cache",
                annotation=bool,
                default=True,
                help_text="是否优先使用本地缓存",
                semantic_type="cache-toggle",
                legacy_names=("use_local",),
            ),
        ),
    },
    "stock.price.history": {
        "cli_path": ("stock", "price", "history"),
        "help_text": "查询股票历史 K 线行情",
        "supported_backends": (
            BackendName.EFINANCE,
            BackendName.AKSHARE,
            BackendName.YFINANCE,
        ),
        "limit_strategy": LimitStrategy.DISPLAY_ONLY.value,
        "fields": (
            RequestField(
                name="symbols",
                cli_name="symbols",
                annotation=str,
                required=True,
                multiple=True,
                default=(),
                help_text="股票代码，支持多个",
                semantic_type="symbols",
                legacy_names=("stock_codes",),
            ),
            RequestField(
                name="start_date",
                cli_name="start-date",
                annotation=str,
                default="19000101",
                help_text="开始日期，格式 YYYYMMDD",
                semantic_type="start-date",
                legacy_names=("beg",),
            ),
            RequestField(
                name="end_date",
                cli_name="end-date",
                annotation=str,
                default="20500101",
                help_text="结束日期，格式 YYYYMMDD",
                semantic_type="end-date",
                legacy_names=("end",),
            ),
            RequestField(
                name="timeframe",
                cli_name="timeframe",
                annotation=int,
                default=101,
                help_text="K 线周期",
                semantic_type="timeframe",
                legacy_names=("klt", "period"),
            ),
            RequestField(
                name="adjustment",
                cli_name="adjustment",
                annotation=int,
                default=1,
                help_text="复权类型",
                semantic_type="adjustment",
                legacy_names=("fqt", "adjust"),
            ),
            RequestField(
                name="market",
                cli_name="market",
                annotation=str | None,
                default=None,
                choices=MARKET_CHOICES,
                help_text="市场枚举",
                semantic_type="market",
                legacy_names=("market_type",),
            ),
            RequestField(
                name="ignore_errors",
                cli_name="ignore-errors",
                annotation=bool,
                default=False,
                help_text="是否忽略单个标的错误",
                semantic_type="ignore-errors",
                legacy_names=("suppress_error",),
            ),
            RequestField(
                name="use_id_cache",
                cli_name="use-id-cache",
                annotation=bool,
                default=True,
                help_text="是否使用 quote_id 缓存",
                semantic_type="cache-toggle",
            ),
        ),
    },
    "stock.price.latest": {
        "cli_path": ("stock", "price", "latest"),
        "help_text": "查询股票最新行情",
        "supported_backends": (BackendName.EFINANCE, BackendName.YFINANCE),
        "limit_strategy": LimitStrategy.DISPLAY_ONLY.value,
        "fields": (
            RequestField(
                name="symbols",
                cli_name="symbols",
                annotation=str,
                required=True,
                multiple=True,
                default=(),
                help_text="股票代码，支持多个",
                semantic_type="symbols",
                legacy_names=("stock_codes",),
            ),
            RequestField(
                name="market",
                cli_name="market",
                annotation=str | None,
                default=None,
                choices=MARKET_CHOICES,
                help_text="市场枚举",
                semantic_type="market",
                legacy_names=("market_type",),
            ),
        ),
    },
    "stock.price.live": {
        "cli_path": ("stock", "price", "live"),
        "help_text": "查询市场实时行情列表",
        "supported_backends": (BackendName.EFINANCE, BackendName.AKSHARE),
        "limit_strategy": LimitStrategy.DISPLAY_ONLY.value,
        "fields": (
            RequestField(
                name="market",
                cli_name="market",
                annotation=str,
                required=False,
                default="A_stock",
                choices=MARKET_CHOICES,
                help_text="市场枚举",
                semantic_type="market",
                legacy_names=("market_type", "fs"),
            ),
        ),
    },
    "stock.price.snapshot": {
        "cli_path": ("stock", "price", "snapshot"),
        "help_text": "查询单只股票快照",
        "supported_backends": (BackendName.EFINANCE, BackendName.YFINANCE),
        "limit_strategy": LimitStrategy.DISPLAY_ONLY.value,
        "fields": (
            RequestField(
                name="symbol",
                cli_name="symbol",
                annotation=str,
                required=True,
                help_text="股票代码",
                semantic_type="symbol",
                legacy_names=("stock_code",),
            ),
            RequestField(
                name="market",
                cli_name="market",
                annotation=str | None,
                default=None,
                choices=MARKET_CHOICES,
                help_text="市场枚举",
                semantic_type="market",
                legacy_names=("market_type",),
            ),
        ),
    },
    "stock.profile": {
        "cli_path": ("stock", "profile"),
        "help_text": "查询单只股票资料",
        "supported_backends": (
            BackendName.EFINANCE,
            BackendName.AKSHARE,
            BackendName.YFINANCE,
        ),
        "limit_strategy": LimitStrategy.DISPLAY_ONLY.value,
        "fields": (
            RequestField(
                name="symbol",
                cli_name="symbol",
                annotation=str,
                required=True,
                help_text="股票代码",
                semantic_type="symbol",
                legacy_names=("stock_code",),
                cli_aliases=("symbols",),
            ),
            RequestField(
                name="market",
                cli_name="market",
                annotation=str | None,
                default=None,
                choices=MARKET_CHOICES,
                help_text="市场枚举",
                semantic_type="market",
                legacy_names=("market_type",),
            ),
        ),
    },
    "fund.nav.history": {
        "cli_path": ("fund", "nav", "history"),
        "help_text": "查询基金历史净值",
        "supported_backends": (
            BackendName.EFINANCE,
            BackendName.AKSHARE,
            BackendName.YFINANCE,
        ),
        "limit_strategy": LimitStrategy.DISPLAY_ONLY.value,
        "fields": (
            RequestField(
                name="symbol",
                cli_name="symbol",
                annotation=str,
                required=True,
                help_text="基金代码或 Yahoo ticker",
                semantic_type="symbol",
                legacy_names=("fund_code",),
            ),
            RequestField(
                name="max_pages",
                cli_name="max-pages",
                annotation=int,
                default=40000,
                help_text="efinance 最大翻页数",
                semantic_type="page-limit",
                legacy_names=("pz",),
            ),
        ),
    },
    "fund.profile": {
        "cli_path": ("fund", "profile"),
        "help_text": "查询基金资料",
        "supported_backends": (BackendName.EFINANCE, BackendName.YFINANCE),
        "limit_strategy": LimitStrategy.DISPLAY_ONLY.value,
        "fields": (
            RequestField(
                name="symbols",
                cli_name="symbols",
                annotation=str,
                required=True,
                multiple=True,
                default=(),
                help_text="基金代码，支持多个",
                semantic_type="symbols",
                legacy_names=("fund_codes",),
            ),
        ),
    },
    "quote.price.history": {
        "cli_path": ("quote", "price", "history"),
        "help_text": "查询通用行情历史价格",
        "supported_backends": (BackendName.EFINANCE, BackendName.YFINANCE),
        "limit_strategy": LimitStrategy.DISPLAY_ONLY.value,
        "fields": (
            RequestField(
                name="symbols",
                cli_name="symbols",
                annotation=str,
                required=True,
                multiple=True,
                default=(),
                help_text="通用 symbol / quote 标识，支持多个",
                semantic_type="symbols",
                legacy_names=("codes",),
            ),
            RequestField(
                name="start_date",
                cli_name="start-date",
                annotation=str,
                default="19000101",
                help_text="开始日期，格式 YYYYMMDD",
                semantic_type="start-date",
                legacy_names=("beg",),
            ),
            RequestField(
                name="end_date",
                cli_name="end-date",
                annotation=str,
                default="20500101",
                help_text="结束日期，格式 YYYYMMDD",
                semantic_type="end-date",
                legacy_names=("end",),
            ),
            RequestField(
                name="timeframe",
                cli_name="timeframe",
                annotation=int,
                default=101,
                help_text="K 线周期",
                semantic_type="timeframe",
                legacy_names=("klt", "period"),
            ),
            RequestField(
                name="adjustment",
                cli_name="adjustment",
                annotation=int,
                default=1,
                help_text="复权类型",
                semantic_type="adjustment",
                legacy_names=("fqt", "adjust"),
            ),
            RequestField(
                name="market",
                cli_name="market",
                annotation=str | None,
                default=None,
                choices=MARKET_CHOICES,
                help_text="市场枚举",
                semantic_type="market",
                legacy_names=("market_type",),
            ),
            RequestField(
                name="ignore_errors",
                cli_name="ignore-errors",
                annotation=bool,
                default=False,
                help_text="是否忽略单个标的错误",
                semantic_type="ignore-errors",
                legacy_names=("suppress_error",),
            ),
            RequestField(
                name="use_id_cache",
                cli_name="use-id-cache",
                annotation=bool,
                default=True,
                help_text="是否使用 quote_id 缓存",
                semantic_type="cache-toggle",
            ),
        ),
    },
    "quote.price.latest": {
        "cli_path": ("quote", "price", "latest"),
        "help_text": "查询通用行情最新价格",
        "supported_backends": (BackendName.EFINANCE, BackendName.YFINANCE),
        "limit_strategy": LimitStrategy.PROVIDER_REQUEST.value,
        "fields": (
            RequestField(
                name="quote_ids",
                cli_name="quote-ids",
                annotation=str,
                required=True,
                multiple=True,
                default=(),
                help_text="通用 quote_id 或 Yahoo ticker，支持多个",
                semantic_type="quote-ids",
                legacy_names=("quote_id_list",),
            ),
        ),
    },
    "quote.profile": {
        "cli_path": ("quote", "profile"),
        "help_text": "查询通用行情资料",
        "supported_backends": (BackendName.EFINANCE, BackendName.YFINANCE),
        "limit_strategy": LimitStrategy.DISPLAY_ONLY.value,
        "fields": (
            RequestField(
                name="quote_id",
                cli_name="quote-id",
                annotation=str,
                required=True,
                help_text="单个 quote_id 或 Yahoo ticker",
                semantic_type="quote-id",
            ),
        ),
    },
}


def _limit_strategy_for_command_path(command_path: str) -> str:
    """返回单后端命令声明的 `--limit` 策略。"""

    return SINGLE_BACKEND_LIMIT_STRATEGIES.get(
        command_path,
        LimitStrategy.DISPLAY_ONLY.value,
    )


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
    return (BackendName.EFINANCE,)


def is_multi_backend_support(backends: tuple[BackendName, ...]) -> bool:
    """判断当前命令是否属于多 backend shared 能力。"""

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
        # `market price live` 的 provider-extension 参数仍使用原生 `fs`，这里不要把它当成 shared market 枚举。
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
        semantic_type=str(parameter.get("semantic_type") or "").strip() or None,
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
        limit_strategy=_limit_strategy_for_command_path(command_path),
    )


def _build_shared_command(command_key: str, payload: dict[str, Any]) -> CommandDefinition:
    return CommandDefinition(
        command_key=command_key,
        cli_path=tuple(payload["cli_path"]),
        capability=command_key,
        request_schema=RequestSchema(
            schema_name=f"{command_key.replace('.', '-')}-request",
            fields=tuple(payload["fields"]),
        ),
        help_text=str(payload["help_text"]),
        kind=CommandKind.SHARED,
        supported_backends=tuple(payload["supported_backends"]),
        allow_watch=bool(payload.get("allow_watch", True)),
        has_side_effect=bool(payload.get("has_side_effect", False)),
        provider_name=None,
        limit_strategy=str(payload.get("limit_strategy", LimitStrategy.DISPLAY_ONLY.value)),
    )


SHARED_COMMANDS: tuple[CommandDefinition, ...] = tuple(
    _build_shared_command(command_key, payload)
    for command_key, payload in SHARED_COMMAND_CONFIGS.items()
)

SINGLE_BACKEND_COMMANDS: tuple[CommandDefinition, ...] = tuple(
    _build_command_from_reference(entry)
    for entry in _REFERENCE_CATALOG["commands"]
    if entry["command_path"] != "watch"
    and not is_multi_backend_support(_supported_backends_for_command(str(entry["command_path"])))
)

COMMAND_BINDINGS: dict[str, dict[str, str | None]] = {
    command.command_key: {"module": "utils", "function": "search_quote"}
    if command.command_key == "instrument.search"
    else {"module": None, "function": None}
    for command in SHARED_COMMANDS
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
    """返回所有共享命令的根分组。"""

    roots = sorted(
        {
            command.root_group
            for command in SHARED_COMMANDS
            if command.root_group not in SPECIAL_ROOT_GROUPS
        }
    )
    return roots


def build_shared_command_definitions_for_group(group_name: str) -> list[CommandDefinition]:
    """返回指定分组下的共享命令定义。"""

    return sorted(
        [command for command in SHARED_COMMANDS if command.root_group == group_name],
        key=lambda item: item.cli_path,
    )


def get_shared_command_definition(command_key: str) -> CommandDefinition:
    """按 command_key 获取共享命令定义。"""

    for command in SHARED_COMMANDS:
        if command.command_key == command_key:
            return command
    raise KeyError(f"未知命令: {command_key}")


def get_command_definition(command_key: str) -> CommandDefinition:
    """按 command_key 获取任意命令定义。"""

    for command in SHARED_COMMANDS:
        if command.command_key == command_key:
            return command
    for command in SINGLE_BACKEND_COMMANDS:
        if command.command_key == command_key:
            return command
    raise KeyError(f"未知命令: {command_key}")


def get_single_backend_command_definitions(
    provider_name: BackendName | None = None,
) -> tuple[CommandDefinition, ...]:
    """按 provider 过滤单后端命令定义。"""

    if provider_name is None:
        return SINGLE_BACKEND_COMMANDS
    return tuple(
        command
        for command in SINGLE_BACKEND_COMMANDS
        if command.provider_name == provider_name
    )


def get_capability_descriptor(capability_name: str) -> CapabilityDescriptor:
    """按 capability 获取能力描述。"""

    try:
        return SHARED_CAPABILITIES[capability_name]
    except KeyError:
        pass
    try:
        return SINGLE_BACKEND_CAPABILITIES[capability_name]
    except KeyError as exc:
        raise KeyError(f"未知 capability: {capability_name}") from exc


def get_command_binding(command_key: str) -> dict[str, str | None]:
    """按 command_key 获取函数绑定。"""

    try:
        return COMMAND_BINDINGS[command_key]
    except KeyError as exc:
        raise KeyError(f"未知命令: {command_key}") from exc
