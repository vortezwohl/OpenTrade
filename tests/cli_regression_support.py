"""CLI 回归测试的共享辅助工具。

该文件集中处理命令树枚举、样例参数构造和测试统计，避免各个测试文件重复维护同一份
命令目录理解逻辑。当前命令面已经收敛为 shared 命令与 provider-extension 命令，
因此这里的样例构造也只围绕这套稳定命令树展开。
"""

from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path
from pprint import pformat
import sys
from typing import Iterator

import click

from opentrade.commands import create_root_command


SearchRecord = namedtuple(
    "SearchRecord",
    ["code", "name", "pinyin", "quote_id", "classify"],
)

RUNTIME_OUTPUT_OPTION_NAMES = {
    "format_name",
    "full",
    "transpose",
    "no_index",
    "limit",
    "output_path",
    "encoding",
    "indicator_level",
    "view_mode",
    "trace_window",
}

RUNTIME_WATCH_OPTION_NAMES = {
    "watch",
    "interval",
    "count",
    "clear_screen",
}

RUNTIME_EXECUTION_OPTION_NAMES = {
    "backend_name",
}


@dataclass(slots=True)
class LeafCommand:
    """描述一条可直接执行的叶子命令。"""

    path: tuple[str, ...]
    command: click.Command

    @property
    def dotted_path(self) -> str:
        """返回便于日志与报告展示的路径文本。"""
        return " ".join(self.path)


def build_cli() -> click.Group:
    """构建一棵真实的 CLI 命令树。"""
    return create_root_command()


def collect_leaf_commands(cli: click.MultiCommand | None = None) -> list[LeafCommand]:
    """递归收集全部叶子命令。"""
    root = cli or build_cli()
    if isinstance(root, click.Group):
        commands: list[LeafCommand] = []
        for child in root.commands.values():
            commands.extend(_iter_leaf_commands(child, ()))
        return commands
    return list(_iter_leaf_commands(root, ()))


def _iter_leaf_commands(
    command: click.Command,
    prefix: tuple[str, ...],
) -> Iterator[LeafCommand]:
    """递归遍历命令树。"""
    current_path = prefix + ((command.name,) if command.name else ())
    if isinstance(command, click.Group):
        for child in command.commands.values():
            yield from _iter_leaf_commands(child, current_path)
        return
    yield LeafCommand(path=current_path, command=command)


def count_all_parameters(leaf_commands: list[LeafCommand] | None = None) -> int:
    """统计全部叶子命令参数数量。"""
    commands = leaf_commands or collect_leaf_commands()
    return sum(len(item.command.params) for item in commands)


def build_required_tokens(
    leaf: LeafCommand,
    exclude_option_names: set[str] | None = None,
) -> list[str]:
    """为一条命令构造最小必填参数。"""
    excluded = exclude_option_names or set()
    if leaf.path == ("watch",):
        return ["watch", "search", "--query", "AAPL"]

    tokens: list[str] = list(leaf.path)
    for parameter in leaf.command.params:
        if isinstance(parameter, click.Argument):
            tokens.extend(_sample_argument_values(parameter))
            continue
        if (
            isinstance(parameter, click.Option)
            and parameter.required
            and parameter.name not in excluded
        ):
            tokens.extend(_build_required_option_tokens(parameter))
    return tokens


def build_option_cases(parameter: click.Option, base_dir: Path) -> list[tuple[list[str], object]]:
    """为单个选项参数构造若干测试用例。"""
    option_tokens: list[tuple[list[str], object]] = []
    primary = list(parameter.opts)
    secondary = list(parameter.secondary_opts)

    if parameter.is_flag:
        if primary:
            option_tokens.append(([primary[0]], True))
        if secondary:
            option_tokens.append(([secondary[0]], False))
        return option_tokens

    sample_value = _sample_option_value(parameter, base_dir)
    if primary:
        option_tokens.append(([primary[0], sample_value], _coerce_expected_value(parameter, sample_value)))
    return option_tokens


def build_search_records() -> list[SearchRecord]:
    """返回稳定的搜索结果样例。"""
    return [
        SearchRecord("AAPL", "Apple Inc.", "apple", "105.AAPL", "US_stock"),
        SearchRecord("MSFT", "Microsoft", "microsoft", "105.MSFT", "US_stock"),
    ]


def build_all_optional_option_tokens(leaf: LeafCommand, base_dir: Path) -> list[str]:
    """为单条命令构造“所有可选参数同时出现一次”的样例调用片段。"""

    tokens: list[str] = []
    for parameter in leaf.command.params:
        if not isinstance(parameter, click.Option):
            continue
        if parameter.required:
            continue
        option_cases = build_option_cases(parameter, base_dir)
        if not option_cases:
            continue
        tokens.extend(option_cases[0][0])
    return tokens


def _build_required_option_tokens(parameter: click.Option) -> list[str]:
    """为必填 option 构造最小命令行片段。"""
    sample = _sample_text_value(parameter.name or "")
    return [parameter.opts[0], sample]


def _sample_argument_values(parameter: click.Argument) -> list[str]:
    """按参数名生成最小样例参数值。"""
    sample = _sample_text_value(parameter.name)
    if parameter.nargs == -1:
        return [sample]
    return [sample]


def _sample_option_value(parameter: click.Option, base_dir: Path) -> str:
    """按 Click 类型与参数语义构造样例值。"""
    name = parameter.name or ""
    param_type = parameter.type

    if name == "output_path":
        return str(base_dir / "command-output.txt")
    if name == "encoding":
        return "utf-8"
    if name == "format_name":
        return "json"
    if name == "indicator_level":
        return "full"
    if name == "view_mode":
        return "observation"
    if name == "trace_window":
        return "8"
    if name == "interval":
        return "0.25"
    if name in {"limit", "count", "result_count", "max_count", "pz", "top"}:
        return "2"
    if isinstance(param_type, click.Choice):
        return next(iter(param_type.choices))
    if isinstance(param_type, click.types.IntParamType):
        return "2"
    if isinstance(param_type, click.types.FloatParamType):
        return "1.5"
    return _sample_text_value(name)


def _sample_text_value(name: str) -> str:
    """按常见参数语义构造可读样例值。"""
    lowered = name.lower()
    if "date" in lowered or lowered in {"beg", "end"}:
        return "20250101"
    if "quote_id" in lowered:
        return "105.AAPL"
    if lowered == "fs":
        return "m:105+t:3"
    if lowered in {"keyword", "query"}:
        return "AAPL"
    if lowered in {"market_type", "market_name"}:
        return "A_stock"
    if lowered == "market_number":
        return "1"
    if lowered in {"stock_code", "fund_code", "bond_code", "index_code", "code"}:
        return "000001"
    if lowered in {"stock_codes", "fund_codes", "bond_codes", "codes"}:
        return "000001"
    if lowered == "category":
        return "sample_category"
    if lowered == "save_dir":
        return "sample_output_dir"
    if lowered == "name":
        return "sample_name"
    return "sample_value"


def _coerce_expected_value(parameter: click.Option, raw_value: str) -> object:
    """把命令行字符串样例转换为断言用的 Python 值。"""
    param_type = parameter.type
    if parameter.multiple:
        return (raw_value,)
    if isinstance(param_type, click.Choice):
        return raw_value
    if isinstance(param_type, click.types.IntParamType):
        return int(raw_value)
    if isinstance(param_type, click.types.FloatParamType):
        return float(raw_value)
    return raw_value


def print_observation(title: str, value: object) -> None:
    """打印测试过程中的实际输出，便于人工查看。"""
    safe_title = str(title).encode("ascii", errors="backslashreplace").decode("ascii")
    sys.stdout.write(f"\n===== {safe_title} =====\n")
    if isinstance(value, str):
        safe_value = value.encode("ascii", errors="backslashreplace").decode("ascii")
        sys.stdout.write(f"{safe_value if safe_value else '<empty>'}\n")
        return
    safe_repr = pformat(value, sort_dicts=False).encode("ascii", errors="backslashreplace").decode("ascii")
    sys.stdout.write(f"{safe_repr}\n")



def make_request_field(
    name: str = "test_field",
    cli_name: str = "test-field",
    annotation: type = str,
    required: bool = False,
    default: object = None,
    help_text: str = "测试字段说明。",
    choices: tuple[str, ...] = (),
    multiple: bool = False,
) -> "RequestField":  # noqa: F821
    """快速构造一个 RequestField 实例，用于 request_schema 单元测试。

    所有参数均有合理默认值，调用方可按需覆盖。
    """
    from opentrade.models import RequestField

    return RequestField(
        name=name,
        cli_name=cli_name,
        annotation=annotation,
        required=required,
        default=default,
        help_text=help_text,
        choices=choices,
        multiple=multiple,
    )


def make_request_schema(
    schema_name: str = "test-schema",
    fields: tuple | None = None,
    allow_extra: bool = False,
) -> "RequestSchema":  # noqa: F821
    """快速构造一个 RequestSchema 实例，用于 request_schema 单元测试。

    Args:
        schema_name: schema 的稳定名称。
        fields: 字段元组；不传时使用单个默认必填 str 字段。
        allow_extra: 是否允许额外字段。
    """
    from opentrade.models import RequestField, RequestSchema

    if fields is None:
        fields = (
            RequestField(
                name="keyword",
                cli_name="query",
                annotation=str,
                required=True,
                help_text="搜索关键字。",
            ),
        )
    return RequestSchema(
        schema_name=schema_name,
        fields=fields,
        allow_extra=allow_extra,
    )
