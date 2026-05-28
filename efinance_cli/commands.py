"""Click 命令构建层。

该模块负责把注册中心中的命令描述动态转换为 Click 命令树。这样做的目标是：
- 尽可能 1:1 暴露 `efinance` 公共 API；
- 避免为几十个函数手写重复命令；
- 在统一位置附加表格输出、刷新与导出参数。
"""

from __future__ import annotations

from typing import Any

import click
import pandas as pd

from efinance_cli.executor import (
    CommandExecutor,
    build_request_kwargs,
    default_watch_count,
    split_runtime_options,
)
from efinance_cli.introspection import apply_click_parameters, build_parameter_specs
from efinance_cli.models import (
    CommandSpec,
    InvocationRequest,
    InvocationResult,
    OutputOptions,
    WatchOptions,
)
from efinance_cli.registry import (
    MODULE_HELP_TEXT,
    build_command_specs,
    get_command_spec,
    list_module_names,
)


def create_root_command() -> click.Group:
    """创建根命令组。"""

    @click.group(context_settings={"help_option_names": ["-h", "--help"]})
    @click.version_option(message="%(version)s")
    def cli() -> None:
        """efinance 命令行终端。"""

    cli.add_command(create_search_command())
    cli.add_command(create_watch_command())

    for module_name in list_module_names():
        cli.add_command(create_module_group(module_name))
    return cli


def create_module_group(module_name: str) -> click.Group:
    """为单个模块创建命令组。"""

    @click.group(name=module_name)
    def group() -> None:
        """模块命令组。"""

    group.help = MODULE_HELP_TEXT[module_name]
    for spec in build_command_specs(module_name):
        group.add_command(create_function_command(spec))
    return group


def create_function_command(spec: CommandSpec) -> click.Command:
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
        name=spec.command_name,
        callback=callback,
        help=build_help_text(spec),
        context_settings={"ignore_unknown_options": False},
    )
    command = apply_click_parameters(command, build_parameter_specs(spec.callback))
    attach_runtime_options(command)
    return command


def attach_runtime_options(command: click.Command) -> None:
    """为命令统一追加运行时选项。"""
    params = [
        click.Option(["--format", "format_name"], type=click.Choice(["table", "json", "csv", "tsv"]), default="table", show_default=True, help="输出格式。"),
        click.Option(["--full"], is_flag=True, default=False, help="完整打印全部列与长文本。"),
        click.Option(["--transpose"], is_flag=True, default=False, help="把结果转置后输出。"),
        click.Option(["--no-index"], is_flag=True, default=False, help="表格输出时不打印索引。"),
        click.Option(["--limit"], type=click.INT, default=None, help="仅输出前 N 行。"),
        click.Option(["--output", "output_path"], type=click.Path(dir_okay=False), default=None, help="把结果写入文件。"),
        click.Option(["--encoding"], type=click.STRING, default="utf-8", show_default=True, help="写文件时使用的编码。"),
        click.Option(["--indicator-level"], type=click.Choice(["basic", "advanced", "full", "1", "2", "3"]), default="advanced", show_default=True, help="技术指标丰富度等级。"),
        click.Option(["--view", "view_mode"], type=click.Choice(["raw", "observation"]), default="observation", show_default=True, help="输出视图模式。"),
        click.Option(["--trace-window"], type=click.INT, default=32, show_default=True, help="结构化观察输出的近期 trace bar 数量。"),
        click.Option(["--watch"], is_flag=True, default=False, help="开启循环刷新。"),
        click.Option(["--interval"], type=click.FLOAT, default=2.0, show_default=True, help="刷新间隔秒数。"),
        click.Option(["--count"], type=click.INT, default=None, help="刷新次数；不传时持续刷新。"),
        click.Option(["--clear/--no-clear", "clear_screen"], default=True, show_default=True, help="刷新前是否清屏。"),
    ]
    command.params.extend(params)


def build_help_text(spec: CommandSpec) -> str:
    """生成命令帮助文本。"""
    lines = [spec.help_text]
    lines.append("")
    lines.append(f"对应函数: efinance.{spec.module_name}.{spec.function_name}")
    if spec.has_side_effect:
        lines.append("注意: 该命令具有副作用，执行后可能下载文件或修改运行时状态。")
    return "\n".join(lines)


def create_search_command() -> click.Command:
    """创建顶层搜索命令。"""

    @click.command(name="search")
    @click.argument("keyword")
    @click.option("--market", "market_name", type=click.STRING, default=None, help="市场枚举名，例如 A_stock、Hongkong、US_stock。")
    @click.option("--result-count", type=click.INT, default=5, show_default=True, help="返回候选数量。")
    @click.option("--no-cache", is_flag=True, default=False, help="禁用本地搜索缓存。")
    @click.option("--format", "format_name", type=click.Choice(["table", "json", "csv", "tsv"]), default="table", show_default=True, help="输出格式。")
    @click.option("--full", is_flag=True, default=False, help="完整打印全部列与长文本。")
    @click.option("--transpose", is_flag=True, default=False, help="把结果转置后输出。")
    @click.option("--no-index", is_flag=True, default=False, help="表格输出时不打印索引。")
    @click.option("--limit", type=click.INT, default=None, help="仅输出前 N 行。")
    @click.option("--output", "output_path", type=click.Path(dir_okay=False), default=None, help="把结果写入文件。")
    @click.option("--encoding", type=click.STRING, default="utf-8", show_default=True, help="写文件时使用的编码。")
    @click.option("--watch", is_flag=True, default=False, help="开启循环刷新。")
    @click.option("--interval", type=click.FLOAT, default=2.0, show_default=True, help="刷新间隔秒数。")
    @click.option("--count", "count_refresh", type=click.INT, default=None, help="刷新次数；不传时持续刷新。")
    @click.option("--count-refresh", "count_refresh_alias", type=click.INT, default=None, hidden=True)
    @click.option("--clear/--no-clear", "clear_screen", default=True, show_default=True, help="刷新前是否清屏。")
    def search_command(
        keyword: str,
        market_name: str | None,
        result_count: int,
        no_cache: bool,
        format_name: str,
        full: bool,
        transpose: bool,
        no_index: bool,
        limit: int | None,
        output_path: str | None,
        encoding: str,
        watch: bool,
        interval: float,
        count_refresh: int | None,
        count_refresh_alias: int | None,
        clear_screen: bool,
    ) -> None:
        from efinance.utils import MarketType, search_quote

        market_type = None
        if market_name:
            market_type = getattr(MarketType, market_name, None)
            if market_type is None:
                raise click.ClickException(f"Unknown market enum: {market_name}")

        refresh_count = count_refresh if count_refresh is not None else count_refresh_alias

        def build_frame() -> pd.DataFrame:
            result = search_quote(
                keyword=keyword,
                market_type=market_type,
                count=result_count,
                use_local=not no_cache,
            )
            if result is None:
                return pd.DataFrame(
                    columns=["code", "name", "pinyin", "quote_id", "classify"]
                )
            if isinstance(result, list):
                return pd.DataFrame([item._asdict() for item in result])
            return pd.DataFrame([result._asdict()])

        executor = CommandExecutor()
        request = InvocationRequest(
            spec=get_command_spec("utils", "search_quote"),
            kwargs={},
            output=OutputOptions(
                format_name=format_name,
                full=full,
                transpose=transpose,
                no_index=no_index,
                limit=limit,
                output_path=output_path,
                encoding=encoding,
                indicator_level="advanced",
                view_mode="observation",
                trace_window=32,
            ),
            watch=WatchOptions(
                enabled=watch,
                interval=interval,
                count=default_watch_count(watch, refresh_count),
                clear_screen=clear_screen,
            ),
        )
        if watch:
            request.spec = CommandSpec(
                module_name=request.spec.module_name,
                function_name=request.spec.function_name,
                callback=lambda **_: build_frame(),
                help_text=request.spec.help_text,
                allow_watch=True,
                has_side_effect=False,
            )
            executor.run(request)
            return
        executor._emit(request, InvocationResult(value=build_frame()))

    search_command.help = "根据关键字搜索证券候选项。"
    return search_command


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
    @click.option("--clear/--no-clear", "clear_screen", default=True, show_default=True, help="刷新前是否清屏。")
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
