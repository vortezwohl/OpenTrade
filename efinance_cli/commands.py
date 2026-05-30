"""Click 命令构建层。

该模块负责把注册中心中的命令描述动态转换为自然化语义命令树，并统一附加输出、
观察视图与刷新控制参数。当前版本同时承载两套路径：

- 旧的 `efinance` 函数驱动命令树；
- 新的共享命令目录驱动命令树。

这样做是为了先把多后端骨架接入，再逐步把代表性命令迁移到新的 capability 架构。
"""

from __future__ import annotations
from typing import Any

import click
import pandas as pd

from efinance_cli.backends.resolver import resolve_backend_selection
from efinance_cli.command_catalog import (
    GROUP_HELP_TEXT as SHARED_GROUP_HELP_TEXT,
    build_shared_command_definitions_for_group,
    list_shared_root_groups,
)
from efinance_cli.executor import (
    CommandExecutor,
    build_request_kwargs,
    default_watch_count,
    split_runtime_options,
)
from efinance_cli.introspection import apply_click_parameters, build_parameter_specs
from efinance_cli.models import (
    BackendName,
    CommandSpec,
    CommandDefinition,
    InvocationRequest,
    OutputOptions,
    WatchOptions,
)
from efinance_cli.request_schema import build_click_options_for_schema
from efinance_cli.registry import (
    GROUP_HELP_TEXT,
    build_command_specs_for_group,
    get_command_spec,
    list_root_group_names,
)
from efinance_cli.retry_utils import call_with_network_retry


def create_root_command() -> click.Group:
    """创建根命令组。"""

    @click.group(context_settings={"help_option_names": ["-h", "--help"]})
    @click.version_option(message="%(version)s")
    def cli() -> None:
        """efinance 命令行终端。"""

    cli.add_command(create_search_group())
    cli.add_command(create_watch_command())

    for group_name in list_shared_root_groups():
        cli.add_command(create_shared_root_group(group_name))

    for group_name in list_root_group_names():
        if group_name == "search":
            continue
        if group_name in cli.commands:
            continue
        cli.add_command(create_root_group(group_name))
    return cli


def create_root_group(group_name: str) -> click.Group:
    """根据自然化分组名称创建根命令组。"""

    @click.group(name=group_name)
    def group() -> None:
        """自然化语义分组。"""

    group.help = GROUP_HELP_TEXT[group_name]
    for spec in build_command_specs_for_group(group_name):
        attach_spec_to_tree(group, spec)
    return group


def create_shared_root_group(group_name: str) -> click.Group:
    """根据共享命令目录创建根命令组。"""

    @click.group(name=group_name)
    def group() -> None:
        """共享命令语义分组。"""

    group.help = SHARED_GROUP_HELP_TEXT[group_name]
    for definition in build_shared_command_definitions_for_group(group_name):
        attach_definition_to_tree(group, definition)
    return group


def attach_spec_to_tree(root_group: click.Group, spec: CommandSpec) -> None:
    """把命令规格按 cli_path 递归挂载到命令树。"""
    path_parts = spec.cli_path[1:]
    if not path_parts:
        raise ValueError(f"Invalid cli_path for command: {spec.cli_path}")

    current_group = root_group
    for part in path_parts[:-1]:
        child = current_group.commands.get(part)
        if child is None:
            child = click.Group(name=part)
            current_group.add_command(child)
        elif not isinstance(child, click.Group):
            raise ValueError(f"Path conflict at {' '.join(spec.cli_path)}")
        current_group = child
    current_group.add_command(create_function_command(spec, command_name=path_parts[-1]))


def attach_definition_to_tree(root_group: click.Group, definition: CommandDefinition) -> None:
    """把共享命令定义递归挂载到命令树。"""

    path_parts = definition.cli_path[1:]
    if not path_parts:
        raise ValueError(f"Invalid cli_path for shared command: {definition.cli_path}")

    current_group = root_group
    for part in path_parts[:-1]:
        child = current_group.commands.get(part)
        if child is None:
            child = click.Group(name=part)
            current_group.add_command(child)
        elif not isinstance(child, click.Group):
            raise ValueError(f"Path conflict at {' '.join(definition.cli_path)}")
        current_group = child
    current_group.add_command(create_shared_command(definition, command_name=path_parts[-1]))


def create_function_command(spec: CommandSpec, command_name: str | None = None) -> click.Command:
    """为单个 efinance 函数创建 Click 命令。"""

    def callback(**kwargs: Any) -> None:
        business_kwargs, runtime_kwargs = split_runtime_options(kwargs)
        executor = CommandExecutor()
        request = InvocationRequest(
            spec=spec,
            kwargs=build_request_kwargs(spec.callback, business_kwargs),
            output=OutputOptions(
                format_name=runtime_kwargs["format_name"],
                full=runtime_kwargs["full"],
                transpose=runtime_kwargs["transpose"],
                no_index=runtime_kwargs["no_index"],
                limit=runtime_kwargs["limit"],
                output_path=runtime_kwargs["output_path"],
                encoding=runtime_kwargs["encoding"],
                indicator_level=runtime_kwargs["indicator_level"],
                view_mode=runtime_kwargs["view_mode"],
                trace_window=runtime_kwargs["trace_window"],
            ),
            watch=WatchOptions(
                enabled=runtime_kwargs["watch"],
                interval=runtime_kwargs["interval"],
                count=default_watch_count(runtime_kwargs["watch"], runtime_kwargs["count"]),
                clear_screen=runtime_kwargs["clear_screen"],
            ),
        )
        executor.run(request)

    command = click.Command(
        name=command_name or spec.command_name,
        callback=callback,
        help=build_help_text(spec),
        context_settings={"ignore_unknown_options": False},
    )
    command = apply_click_parameters(
        command,
        build_parameter_specs(spec.callback, command_key=(spec.module_name, spec.function_name)),
    )
    attach_runtime_options(command)
    return command


def create_shared_command(
    definition: CommandDefinition,
    command_name: str | None = None,
    cli_path_override: tuple[str, ...] | None = None,
) -> click.Command:
    """为共享命令定义创建 Click 命令。"""

    effective_path = cli_path_override or definition.cli_path

    def callback(**kwargs: Any) -> None:
        business_kwargs, runtime_kwargs = split_runtime_options(kwargs)
        backend_selection = resolve_backend_selection(definition, runtime_kwargs["backend_name"])
        executor = CommandExecutor()
        request = InvocationRequest(
            spec=CommandSpec(
                module_name="shared",
                function_name=definition.command_key,
                callback=lambda **_: None,
                help_text=definition.help_text,
                cli_path=effective_path,
                allow_watch=definition.allow_watch,
                has_side_effect=definition.has_side_effect,
            ),
            kwargs=business_kwargs,
            output=OutputOptions(
                format_name=runtime_kwargs["format_name"],
                full=runtime_kwargs["full"],
                transpose=runtime_kwargs["transpose"],
                no_index=runtime_kwargs["no_index"],
                limit=runtime_kwargs["limit"],
                output_path=runtime_kwargs["output_path"],
                encoding=runtime_kwargs["encoding"],
                indicator_level=runtime_kwargs["indicator_level"],
                view_mode=runtime_kwargs["view_mode"],
                trace_window=runtime_kwargs["trace_window"],
            ),
            watch=WatchOptions(
                enabled=runtime_kwargs["watch"],
                interval=runtime_kwargs["interval"],
                count=default_watch_count(runtime_kwargs["watch"], runtime_kwargs["count"]),
                clear_screen=runtime_kwargs["clear_screen"],
            ),
            command_definition=definition,
            backend_selection=backend_selection,
        )
        executor.run(request)

    command = click.Command(
        name=command_name or definition.command_name,
        callback=callback,
        help=build_shared_help_text(definition),
        context_settings={"ignore_unknown_options": False},
    )
    command.params = build_click_options_for_schema(definition.request_schema)
    attach_runtime_options(command, include_backend=True)
    return command


def attach_runtime_options(command: click.Command, include_backend: bool = False) -> None:
    """为命令统一追加运行时参数。"""
    params: list[click.Option] = []
    if include_backend:
        params.append(
            click.Option(
                ["--backend", "backend_name"],
                type=click.Choice([item.value for item in BackendName], case_sensitive=False),
                default=None,
                help="指定数据后端；不传时使用默认后端。",
            )
        )
    params.extend([
        click.Option(
            ["--format", "format_name"],
            type=click.Choice(["table", "json", "csv", "tsv"]),
            default="table",
            show_default=True,
            help="输出格式。",
        ),
        click.Option(["--full"], is_flag=True, default=False, help="完整打印全部列与长文本。"),
        click.Option(["--transpose"], is_flag=True, default=False, help="把结果转置后输出。"),
        click.Option(["--no-index"], is_flag=True, default=False, help="表格输出时不打印索引。"),
        click.Option(["--limit"], type=click.INT, default=None, help="仅输出前 N 行。"),
        click.Option(
            ["--output", "output_path"],
            type=click.Path(dir_okay=False),
            default=None,
            help="把结果写入文件。",
        ),
        click.Option(
            ["--encoding"],
            type=click.STRING,
            default="utf-8",
            show_default=True,
            help="写文件时使用的编码。",
        ),
        click.Option(
            ["--indicator-level"],
            type=click.Choice(["basic", "advanced", "full", "1", "2", "3"]),
            default="advanced",
            show_default=True,
            help="技术指标丰富度等级。",
        ),
        click.Option(
            ["--view", "view_mode"],
            type=click.Choice(["raw", "observation"]),
            default="observation",
            show_default=True,
            help="输出视图模式。",
        ),
        click.Option(
            ["--trace-window"],
            type=click.INT,
            default=32,
            show_default=True,
            help="结构化观察输出的近期 trace bar 数量。",
        ),
        click.Option(["--watch"], is_flag=True, default=False, help="开启循环刷新。"),
        click.Option(
            ["--interval"],
            type=click.FLOAT,
            default=2.0,
            show_default=True,
            help="刷新间隔秒数。",
        ),
        click.Option(["--count"], type=click.INT, default=None, help="刷新次数；不传时持续刷新。"),
        click.Option(
            ["--clear/--no-clear", "clear_screen"],
            default=True,
            show_default=True,
            help="刷新前是否清屏。",
        ),
    ])
    command.params.extend(params)


def build_help_text(spec: CommandSpec) -> str:
    """生成命令帮助文本。"""
    lines = [spec.help_text]
    lines.append("")
    lines.append(f"对应函数: efinance.{spec.module_name}.{spec.function_name}")
    if spec.has_side_effect:
        lines.append("注意: 该命令具有副作用，执行后可能下载文件或修改运行时状态。")
    return "\n".join(lines)


def build_shared_help_text(definition: CommandDefinition) -> str:
    """生成共享命令帮助文本。"""

    lines = [definition.help_text]
    lines.append("")
    lines.append(f"命令键: {definition.command_key}")
    lines.append(f"能力标识: {definition.capability}")
    supported = ", ".join(item.value for item in definition.supported_backends)
    lines.append(f"支持后端: {supported}")
    lines.append(f"命令类别: {definition.kind.value}")
    if definition.has_side_effect:
        lines.append("注意: 该命令具有副作用，执行后可能修改运行时状态或外部资源。")
    return "\n".join(lines)


def create_search_group() -> click.Group:
    """创建顶层 search 分组，包含默认搜索与本地搜索。"""

    @click.group(name="search", invoke_without_command=True)
    @click.pass_context
    def search_group(ctx: click.Context, **kwargs: Any) -> None:
        """搜索证券候选项。"""
        if ctx.resilient_parsing:
            return
        if ctx.invoked_subcommand is None:
            if not kwargs.get("query"):
                raise click.ClickException("Missing option '--query'.")
            ctx.invoke(default_search_command.callback, **kwargs)

    default_search_command = create_search_command(command_name="search")
    default_search_command.hidden = True
    search_group.params = list(default_search_command.params)
    for parameter in search_group.params:
        if isinstance(parameter, click.Option) and parameter.name == "query":
            parameter.required = False
    search_group.help = "根据关键字搜索证券候选项。"

    local_search = create_function_command(
        get_command_spec("utils", "search_quote_locally"),
        command_name="local",
    )
    search_group.add_command(local_search)
    return search_group


def create_search_command(command_name: str = "search") -> click.Command:
    """创建默认搜索命令。"""
    from efinance_cli.command_catalog import get_shared_command_definition

    definition = get_shared_command_definition("instrument.search")
    command = create_shared_command(
        definition,
        command_name=command_name,
        cli_path_override=(command_name,),
    )
    command.help = "根据关键字搜索证券候选项。"
    return command


def create_watch_command() -> click.Command:
    """创建顶层 watch 包装命令。"""

    @click.command(
        name="watch",
        context_settings={
            "ignore_unknown_options": True,
            "allow_extra_args": True,
        },
    )
    @click.option("--interval", type=click.FLOAT, default=2.0, show_default=True, help="刷新间隔秒数。")
    @click.option("--count", type=click.INT, default=None, help="刷新次数；不传时持续刷新。")
    @click.option(
        "--clear/--no-clear",
        "clear_screen",
        default=True,
        show_default=True,
        help="刷新前是否清屏。",
    )
    @click.pass_context
    def watch_command(
        ctx: click.Context,
        interval: float,
        count: int | None,
        clear_screen: bool,
    ) -> None:
        if not ctx.args:
            raise click.ClickException("watch must be followed by a full subcommand.")
        root = ctx.parent.command if ctx.parent else None
        if root is None:
            raise click.ClickException("Unable to resolve the root command.")

        forwarded = list(ctx.args)
        if "--watch" not in forwarded:
            forwarded.append("--watch")
        if "--interval" not in forwarded:
            forwarded.extend(["--interval", str(interval)])
        if count is not None and "--count" not in forwarded:
            forwarded.extend(["--count", str(count)])
        if clear_screen and "--clear" not in forwarded and "--no-clear" not in forwarded:
            forwarded.append("--clear")
        if not clear_screen and "--clear" not in forwarded and "--no-clear" not in forwarded:
            forwarded.append("--no-clear")
        root.main(args=forwarded, prog_name=ctx.find_root().info_name, standalone_mode=False)

    watch_command.help = "为任意子命令开启循环刷新。"
    return watch_command
