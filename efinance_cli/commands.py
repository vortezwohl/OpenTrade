"""Click 命令构建层。

该模块负责挂载 shared 命令目录与 provider 扩展命令。
旧的函数驱动命令树已经被下线，命令面不再从第三方函数签名动态反射生成。
provider-specific 扩展命令也不再以 provider 名称直接暴露为顶层根组，而是按
自身声明的业务语义路径挂到统一命令树中。
"""

from __future__ import annotations
from typing import Any

import click

from efinance_cli.backends.resolver import resolve_backend_selection
from efinance_cli.backends.factory import list_provider_extension_commands
from efinance_cli.command_catalog import (
    GROUP_HELP_TEXT as SHARED_GROUP_HELP_TEXT,
    build_shared_command_definitions_for_group,
    list_shared_root_groups,
)
from efinance_cli.executor import (
    CommandExecutor,
    default_watch_count,
    split_runtime_options,
)
from efinance_cli.models import (
    BackendName,
    CommandDefinition,
    InvocationRequest,
    CommandSpec,
    OutputOptions,
    WatchOptions,
)
from efinance_cli.request_schema import build_click_options_for_schema


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

    for definition in list_provider_extension_commands():
        root_group = _get_or_create_root_group(cli, definition.root_group)
        attach_definition_to_tree(root_group, definition)
    return cli


def create_shared_root_group(group_name: str) -> click.Group:
    """根据共享命令目录创建根命令组。"""

    @click.group(name=group_name)
    def group() -> None:
        """共享命令语义分组。"""

    group.help = SHARED_GROUP_HELP_TEXT[group_name]
    for definition in build_shared_command_definitions_for_group(group_name):
        attach_definition_to_tree(group, definition)
    return group


def _get_or_create_root_group(cli: click.Group, group_name: str) -> click.Group:
    """按根组名获取或创建顶层命令分组。"""

    existing = cli.commands.get(group_name)
    if existing is not None:
        if not isinstance(existing, click.Group):
            raise ValueError(f"Top-level path conflict at {group_name}")
        return existing

    @click.group(name=group_name)
    def group() -> None:
        """动态创建的命令语义分组。"""

    group.help = SHARED_GROUP_HELP_TEXT.get(group_name, f"{group_name} 命令分组。")
    cli.add_command(group)
    return group

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
def build_shared_help_text(definition: CommandDefinition) -> str:
    """生成共享命令帮助文本。"""

    lines = [definition.help_text]
    lines.append("")
    lines.append(f"命令键: {definition.command_key}")
    lines.append(f"能力标识: {definition.capability}")
    supported = ", ".join(item.value for item in definition.supported_backends)
    lines.append(f"支持后端: {supported}")
    lines.append(f"命令类别: {definition.kind.value}")
    if BackendName.YFINANCE in definition.supported_backends:
        lines.append("注意: yfinance 以 Yahoo ticker / symbol 语义为主，本地市场专属命令面并不完整。")
    if definition.provider_name is not None:
        lines.append(f"所属 Provider: {definition.provider_name.value}")
    if definition.has_side_effect:
        lines.append("注意: 该命令具有副作用，执行后可能修改运行时状态或外部资源。")
    return "\n".join(lines)


def create_search_group() -> click.Group:
    """创建顶层 search 分组，仅保留 shared 默认搜索。"""

    @click.group(name="search", invoke_without_command=True)
    @click.pass_context
    def search_group(ctx: click.Context, **kwargs: Any) -> None:
        """搜索证券候选项。"""
        if ctx.resilient_parsing:
            return
        if ctx.invoked_subcommand is None:
            if not kwargs.get("keyword"):
                raise click.ClickException("Missing option '--query'.")
            ctx.invoke(default_search_command.callback, **kwargs)

    default_search_command = create_search_command(command_name="search")
    default_search_command.hidden = True
    search_group.params = list(default_search_command.params)
    for parameter in search_group.params:
        if isinstance(parameter, click.Option) and parameter.name == "keyword":
            parameter.required = False
    search_group.help = "根据关键字搜索证券候选项。"
    from efinance_cli.command_catalog import build_shared_command_definitions_for_group

    for definition in build_shared_command_definitions_for_group("search"):
        if definition.command_key == "instrument.search":
            continue
        attach_definition_to_tree(search_group, definition)
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
