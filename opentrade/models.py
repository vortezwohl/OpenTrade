"""CLI 内部共享的数据模型。

这里集中定义两类稳定对象：

1. 现有运行时仍在使用的命令元数据、执行请求和 observation 数据结构；
2. 多后端重构引入的共享命令目录、请求 schema、结果契约和后端枚举。

这样做的目的不是把所有抽象揉成一个巨型模型文件，而是先用一个集中入口把
“旧执行链仍在工作”和“新架构骨架开始落地”这两件事稳定下来，方便后续渐进迁移。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping


class BackendName(str, Enum):
    """定义当前已知的后端标识。

    说明：
        这里用显式枚举而不是自由字符串，是为了让帮助信息、请求校验和支持矩阵
        都能围绕同一组稳定标识收敛。未来接入新 provider 时，可以在这里增量扩展。
    """

    EFINANCE = "efinance"
    AKSHARE = "akshare"
    YFINANCE = "yfinance"
    AUTO = "auto"


class CommandKind(str, Enum):
    """定义命令类别。

    共享命令要求语义稳定、能力可切换；扩展命令则允许只属于某个 provider。
    """

    SHARED = "shared"
    PROVIDER_EXTENSION = "provider-extension"


@dataclass(slots=True)
class RequestField:
    """描述共享命令请求 schema 中的单个字段。

    Args:
        name: 请求对象中的内部字段名。
        cli_name: 对外暴露的 CLI 选项名，不含前缀 `--`。
        annotation: 字段的目标类型或联合类型。
        required: 是否必填。
        default: 默认值。
        help_text: 字段帮助说明。
        choices: 若字段取值受限，则列出允许值。
        multiple: 是否支持多值输入。
    """

    name: str
    cli_name: str
    annotation: Any
    required: bool = False
    default: Any = None
    help_text: str = ""
    choices: tuple[str, ...] = field(default_factory=tuple)
    multiple: bool = False


@dataclass(slots=True)
class RequestSchema:
    """定义共享命令的请求契约。

    Args:
        schema_name: schema 的稳定名称。
        fields: 字段列表。
        allow_extra: 是否允许额外字段穿透。
    """

    schema_name: str
    fields: tuple[RequestField, ...]
    allow_extra: bool = False

    def field_map(self) -> dict[str, RequestField]:
        """按内部字段名返回字段映射，便于请求校验与归一化。"""

        return {field.name: field for field in self.fields}


@dataclass(slots=True)
class CommandDefinition:
    """定义后端无关的共享命令或 provider 扩展命令。

    Args:
        command_key: 稳定命令键，例如 `instrument.search`。
        cli_path: CLI 命令路径。
        capability: 绑定的 capability 标识。
        request_schema: 命令请求 schema。
        help_text: 命令帮助文本。
        kind: 命令类别。
        supported_backends: 支持该命令的 backend 集合。
        allow_watch: 是否允许 watch。
        has_side_effect: 是否具有副作用。
        provider_name: 如果是扩展命令，则标识其所属 provider。
    """

    command_key: str
    cli_path: tuple[str, ...]
    capability: str
    request_schema: RequestSchema
    help_text: str
    kind: CommandKind = CommandKind.SHARED
    supported_backends: tuple[BackendName, ...] = field(default_factory=tuple)
    allow_watch: bool = True
    has_side_effect: bool = False
    provider_name: BackendName | None = None

    @property
    def command_name(self) -> str:
        """返回 CLI 叶子命令名。"""

        return self.cli_path[-1]

    @property
    def root_group(self) -> str:
        """返回命令根分组名。"""

        return self.cli_path[0]

    def supports_backend(self, backend_name: BackendName) -> bool:
        """判断指定 backend 是否在该命令的支持矩阵中。"""

        if not self.supported_backends:
            return True
        return backend_name in self.supported_backends


@dataclass(slots=True)
class CapabilityDescriptor:
    """描述共享 capability 的稳定元数据。"""

    capability_name: str
    description: str
    result_contract: str


@dataclass(slots=True)
class StandardResult:
    """统一封装标准结果契约。

    Args:
        contract_name: 结果契约名，例如 `search-results`。
        data: 标准化后的主体数据。
        metadata: 结果元信息。
        raw_payload: provider 原始返回值。
        provider_fields: provider 扩展字段。
    """

    contract_name: str
    data: Any
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_payload: Any = None
    provider_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BackendSelection:
    """封装一次 backend 解析结果。"""

    requested: BackendName | None
    resolved: BackendName
    source: str = "explicit"
    candidate_chain: tuple[BackendName, ...] = field(default_factory=tuple)
    final_backend: BackendName | None = None

    @property
    def is_auto(self) -> bool:
        """判断当前解析结果是否仍保留 auto 语义。"""

        return self.resolved == BackendName.AUTO


@dataclass(slots=True)
class CommandInvocation:
    """定义新执行链中的命令调用上下文。

    Args:
        definition: 共享命令或扩展命令定义。
        backend: backend 解析结果。
        request_data: 已通过 schema 校验的业务参数。
        runtime_options: 当前输出与 watch 运行时参数快照。
    """

    definition: CommandDefinition
    backend: BackendSelection
    request_data: dict[str, Any]
    runtime_options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CommandSpec:
    """描述一个可暴露给 CLI 的 efinance 函数。

    Args:
        module_name: 所属模块名，如 `stock` 或 `fund`。
        function_name: 第三方包中实际调用的函数名。
        callback: 实际可调用对象。
        help_text: 命令帮助文本。
        allow_watch: 是否允许循环刷新。
        has_side_effect: 是否具有副作用，例如下载文件。
    """

    module_name: str
    function_name: str
    callback: Callable[..., Any]
    help_text: str
    cli_path: tuple[str, ...] = field(default_factory=tuple)
    allow_watch: bool = True
    has_side_effect: bool = False

    @property
    def command_name(self) -> str:
        """返回 CLI 中使用的命令名。"""
        return self.cli_path[-1]


@dataclass(slots=True)
class OutputOptions:
    """统一描述结果输出选项。"""

    format_name: str = "table"
    full: bool = False
    transpose: bool = False
    no_index: bool = False
    limit: int | None = None
    output_path: str | None = None
    encoding: str = "utf-8"
    indicator_level: str = "advanced"
    view_mode: str = "observation"
    trace_window: int = 32


@dataclass(slots=True)
class WatchOptions:
    """统一描述循环刷新选项。"""

    enabled: bool = False
    interval: float = 2.0
    count: int | None = 1
    clear_screen: bool = True


@dataclass(slots=True)
class InvocationRequest:
    """描述一次命令执行请求。"""

    spec: CommandSpec
    kwargs: dict[str, Any] = field(default_factory=dict)
    output: OutputOptions = field(default_factory=OutputOptions)
    watch: WatchOptions = field(default_factory=WatchOptions)
    command_definition: CommandDefinition | None = None
    backend_selection: BackendSelection | None = None


@dataclass(slots=True)
class InvocationResult:
    """封装一次命令执行后的结果。"""

    value: Any
    summary: str | None = None


@dataclass(slots=True)
class ObservationEvent:
    bars_ago: int
    event_key: str
    subject_a: str
    relation: str
    subject_b: str | None = None
    prev_a: float | None = None
    prev_b: float | None = None
    curr_a: float | None = None
    curr_b: float | None = None
    description: str = ""


@dataclass(slots=True)
class ObservationTraceGroup:
    name: str
    points: list[dict[str, Any]]


@dataclass(slots=True)
class ObservationSection:
    """描述 observation 中的通用结果分节。

    Args:
        name: 分节名称，供 table/json/csv/tsv 统一标识。
        rows: 分节中的结构化行记录。
        render_hint: 渲染提示，当前支持 `table` 与 `kv`。
    """

    name: str
    rows: list[dict[str, Any]]
    render_hint: str = "records"


@dataclass(slots=True)
class ObservationPayload:
    meta: dict[str, Any]
    latest_quote: dict[str, Any]
    current_metrics: dict[str, Any]
    trace_points: list[ObservationTraceGroup]
    recent_events: list[ObservationEvent]
    sections: list[ObservationSection] = field(default_factory=list)
