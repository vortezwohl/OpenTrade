"""后端无关共享命令目录。

该模块定义系统新的稳定命令对象。当前阶段已经落下两类代表性共享命令：

- `instrument.search`：验证目录模型、schema 和支持矩阵；
- `equity.price.history`：验证共享历史能力、双后端 handler 与结果契约。

这样可以在不一次性迁移全部旧命令的前提下，逐步把新架构的主链闭环打通。
"""

from __future__ import annotations

from efinance_cli.models import (
    BackendName,
    CapabilityDescriptor,
    CommandDefinition,
    CommandKind,
    RequestField,
    RequestSchema,
)


GROUP_HELP_TEXT: dict[str, str] = {
    "equity": "跨后端股票与权益类历史价格能力。",
    "instrument": "跨后端的证券检索与标的解析能力。",
    "watch": "为任意子命令开启循环刷新。",
}


SHARED_CAPABILITIES: dict[str, CapabilityDescriptor] = {
    "equity.price.history": CapabilityDescriptor(
        capability_name="equity.price.history",
        description="获取权益类标的历史 K 线数据。",
        result_contract="history-bars",
    ),
    "instrument.search": CapabilityDescriptor(
        capability_name="instrument.search",
        description="按关键字搜索标的候选项。",
        result_contract="search-results",
    ),
}


SHARED_COMMANDS: tuple[CommandDefinition, ...] = (
    CommandDefinition(
        command_key="equity.price.history",
        cli_path=("equity", "price", "history"),
        capability="equity.price.history",
        request_schema=RequestSchema(
            schema_name="equity-price-history-request",
            fields=(
                RequestField(
                    name="symbol",
                    cli_name="symbol",
                    annotation=str,
                    required=True,
                    help_text="股票代码，例如 000001。",
                ),
                RequestField(
                    name="market",
                    cli_name="market",
                    annotation=str | None,
                    default=None,
                    choices=("A_stock", "Hongkong", "US_stock"),
                    help_text="市场枚举名；使用 akshare 时当前仅支持 A_stock。",
                ),
                RequestField(
                    name="start_date",
                    cli_name="start-date",
                    annotation=str,
                    default="19000101",
                    help_text="开始日期，格式 YYYYMMDD。",
                ),
                RequestField(
                    name="end_date",
                    cli_name="end-date",
                    annotation=str,
                    default="20500101",
                    help_text="结束日期，格式 YYYYMMDD。",
                ),
                RequestField(
                    name="period",
                    cli_name="period",
                    annotation=str,
                    default="daily",
                    choices=("daily", "weekly", "monthly"),
                    help_text="K 线周期。",
                ),
                RequestField(
                    name="adjust",
                    cli_name="adjust",
                    annotation=str,
                    default="qfq",
                    choices=("qfq", "hfq", "none"),
                    help_text="复权方式；none 表示不复权。",
                ),
            ),
        ),
        help_text="获取权益类标的历史 K 线数据。",
        kind=CommandKind.SHARED,
        supported_backends=(BackendName.EFINANCE, BackendName.AKSHARE),
        allow_watch=True,
        has_side_effect=False,
    ),
    CommandDefinition(
        command_key="instrument.search",
        cli_path=("instrument", "search"),
        capability="instrument.search",
        request_schema=RequestSchema(
            schema_name="instrument-search-request",
            fields=(
                RequestField(
                    name="query",
                    cli_name="query",
                    annotation=str,
                    required=True,
                    help_text="搜索关键字。",
                ),
                RequestField(
                    name="market",
                    cli_name="market",
                    annotation=str | None,
                    default=None,
                    help_text="市场枚举名，例如 A_stock、Hongkong、US_stock。",
                ),
                RequestField(
                    name="result_count",
                    cli_name="result-count",
                    annotation=int,
                    default=5,
                    help_text="返回候选数量。",
                ),
                RequestField(
                    name="use_local_cache",
                    cli_name="use-local-cache",
                    annotation=bool,
                    default=True,
                    help_text="是否允许使用本地搜索缓存。",
                ),
            ),
        ),
        help_text="根据关键字搜索证券候选项。",
        kind=CommandKind.SHARED,
        supported_backends=(BackendName.EFINANCE, BackendName.AKSHARE),
        allow_watch=True,
        has_side_effect=False,
    ),
)


def list_shared_root_groups() -> list[str]:
    """返回当前共享命令树的根分组。"""

    roots = sorted({command.root_group for command in SHARED_COMMANDS})
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


def get_capability_descriptor(capability_name: str) -> CapabilityDescriptor:
    """返回 capability 描述。"""

    try:
        return SHARED_CAPABILITIES[capability_name]
    except KeyError as exc:
        raise KeyError(f"未知 capability: {capability_name}") from exc
