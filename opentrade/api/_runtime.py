"""程序化 API 与现有执行链之间的桥接层。

该模块把 `OpenTrade` 对象式方法调用转换为现有统一执行链可消费的
`InvocationRequest`。设计目标是：

1. 复用现有命令定义、schema 校验、backend 路由和执行器；
2. 让程序化 API 返回 Python 对象而不是终端渲染文本；
3. 保持接口显式、简单，不引入懒导入或动态公共导出。
"""

from __future__ import annotations

from typing import Any, Literal

from opentrade.backends.resolver import resolve_backend_selection
from opentrade.backends.factory import list_provider_extension_commands
from opentrade.command_catalog import get_command_definition
from opentrade.executor import CommandExecutor
from opentrade.models import (
    BackendName,
    CommandDefinition,
    CommandSpec,
    InvocationRequest,
    OutputOptions,
    WatchOptions,
)

BackendValue = str | BackendName | None
ViewMode = Literal["raw", "observation"]


class ApiRuntime:
    """封装程序化 API 的统一执行入口。

    该类对外只暴露一个稳定方法：`execute`。命名空间对象只需要负责把
    Python 方法参数整理为 request_data，然后交给这里完成：

    - 命令定义解析；
    - backend 选择解析；
    - 执行请求构造；
    - 调用统一执行器并返回 Python 对象。
    """

    def execute(
        self,
        command_key: str,
        request_data: dict[str, Any],
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """执行一条程序化命令并返回 Python 对象。

        Args:
            command_key: 稳定命令键，例如 `stock.price.history`。
            request_data: 业务请求参数，键名遵循命令 schema 定义。
            backend: 可选 backend 名称；不传时沿用现有默认解析逻辑。
            view: 返回视图模式，支持 `raw` 与 `observation`。
            indicator_level: 指标增强等级。
            trace_window: observation 视图下的近期窗口长度。
            limit: 结果限制条数；沿用现有执行链语义。

        Returns:
            已经物化完成的 Python 对象，例如 `dict`、`DataFrame`、
            `Series` 或 observation payload。
        """
        definition = self._resolve_definition(command_key)
        backend_selection = resolve_backend_selection(definition, backend)
        request = InvocationRequest(
            spec=CommandSpec(
                module_name="api",
                function_name=command_key,
                callback=lambda **_: None,
                help_text=definition.help_text,
                cli_path=definition.cli_path,
                allow_watch=False,
                has_side_effect=definition.has_side_effect,
            ),
            kwargs=request_data,
            output=OutputOptions(
                format_name="json",
                full=False,
                transpose=False,
                no_index=False,
                limit=limit,
                output_path=None,
                encoding="utf-8",
                indicator_level=indicator_level,
                view_mode=view,
                trace_window=trace_window,
            ),
            watch=WatchOptions(
                enabled=False,
                interval=0.0,
                count=1,
                clear_screen=False,
            ),
            command_definition=definition,
            backend_selection=backend_selection,
        )
        result = CommandExecutor().invoke(request)
        return result.value

    @staticmethod
    def _resolve_definition(command_key: str) -> CommandDefinition:
        """按命令键解析 shared、catalog 与 provider extension 定义。

        Args:
            command_key: 稳定命令键。

        Returns:
            命令定义对象。

        Raises:
            KeyError: 当命令键既不在 catalog 中，也不在 provider extension
                注册表中时抛出。
        """
        try:
            return get_command_definition(command_key)
        except KeyError:
            for definition in list_provider_extension_commands():
                if definition.command_key == command_key:
                    return definition
            raise


class ApiNamespace:
    """程序化命名空间对象的公共基类。

    子类只需要把公开方法参数映射到稳定命令键和 request_data，即可复用
    `_execute` 完成调用。
    """

    def __init__(self, runtime: ApiRuntime) -> None:
        """保存共享运行时桥接器。

        Args:
            runtime: 当前 `OpenTrade` 实例共享的程序化运行时。
        """
        self._runtime = runtime

    def _execute(
        self,
        command_key: str,
        request_data: dict[str, Any],
        *,
        backend: BackendValue = None,
        view: ViewMode = "raw",
        indicator_level: str = "advanced",
        trace_window: int = 32,
        limit: int | None = None,
    ) -> Any:
        """执行当前命名空间下的一条命令。

        Args:
            command_key: 稳定命令键。
            request_data: 业务请求参数。
            backend: 可选 backend 名称。
            view: 返回视图模式。
            indicator_level: 指标增强等级。
            trace_window: observation 窗口长度。
            limit: 结果限制条数。

        Returns:
            已物化的 Python 对象结果。
        """
        return self._runtime.execute(
            command_key,
            request_data,
            backend=backend,
            view=view,
            indicator_level=indicator_level,
            trace_window=trace_window,
            limit=limit,
        )
