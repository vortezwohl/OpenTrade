"""CLI 内部共享的数据模型。

这里集中定义命令元数据、运行时参数和结果封装对象，避免不同模块各自维护一份
松散的字典结构。命令层、执行层和渲染层通过这些数据模型协作，可以把职责边界
保持得更加稳定。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


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
    allow_watch: bool = True
    has_side_effect: bool = False

    @property
    def command_name(self) -> str:
        """返回 CLI 中使用的命令名。"""
        return self.function_name.replace("_", "-")


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
