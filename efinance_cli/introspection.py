"""把 Python 函数签名映射为统一语义化的 Click 参数。

本模块负责两件事：
1. 从上游 `efinance` 函数签名中提取参数元信息；
2. 在 CLI 暴露层把内部参数名改写为更稳定、更易记的语义化名称。

这次重构不再追求“尽量贴近上游函数签名”，而是把 CLI 参数面收敛为统一规范。
因此所有业务参数都通过显式 option 暴露，不再使用必填位置参数。
"""

from __future__ import annotations

import enum
import inspect
import json
import typing
from dataclasses import dataclass
from types import NoneType
from typing import Any

import click


CommandKey = tuple[str, str]

GLOBAL_CLI_NAME_OVERRIDES: dict[str, str] = {
    "beg": "start-date",
    "end": "end-date",
    "start_date": "start-date",
    "end_date": "end-date",
    "keyword": "query",
    "market_type": "market",
    "fs": "market",
    "stock_code": "symbol",
    "fund_code": "symbol",
    "bond_code": "symbol",
    "index_code": "symbol",
    "code": "symbol",
    "stock_codes": "symbols",
    "fund_codes": "symbols",
    "bond_codes": "symbols",
    "codes": "symbols",
    "quote_id": "quote-id",
    "quote_ids": "quote-ids",
    "quote_id_list": "quote-ids",
    "save_dir": "output-dir",
    "suppress_error": "ignore-errors",
    "use_local": "use-local-cache",
    "use_id_cache": "use-id-cache",
    "ft": "fund-type",
    "pz": "max-pages",
    "klt": "timeframe",
    "fqt": "adjustment",
    "category": "market-category",
    "market_name": "market-name",
    "market_number": "market-id",
    "drop_duplicate": "deduplicate",
}

COMMAND_CLI_NAME_OVERRIDES: dict[CommandKey, dict[str, str]] = {
    ("fund", "get_pdf_reports"): {
        "max_count": "max-files",
    },
}


@dataclass(slots=True)
class ParameterSpec:
    """描述一个 CLI 参数的内部名、外部名和类型语义。"""

    name: str
    cli_name: str
    annotation: Any
    required: bool
    default: Any
    kind: inspect._ParameterKind

    @property
    def is_variadic(self) -> bool:
        """判断当前参数是否适合映射为多值 option。"""
        origin = typing.get_origin(self.annotation)
        args = typing.get_args(self.annotation)
        return origin in (list, tuple, set) or any(
            typing.get_origin(arg) in (list, tuple, set) for arg in args
        )


def resolve_cli_name(parameter_name: str, command_key: CommandKey | None = None) -> str:
    """把内部参数名转换为理想化的 CLI 参数名。"""
    if command_key is not None:
        command_overrides = COMMAND_CLI_NAME_OVERRIDES.get(command_key, {})
        if parameter_name in command_overrides:
            return command_overrides[parameter_name]
    if parameter_name == "max_count":
        return "max-records"
    if parameter_name in GLOBAL_CLI_NAME_OVERRIDES:
        return GLOBAL_CLI_NAME_OVERRIDES[parameter_name]
    return parameter_name.replace("_", "-")


def build_parameter_specs(
    function: Any,
    command_key: CommandKey | None = None,
) -> list[ParameterSpec]:
    """从函数签名生成参数描述列表。"""
    signature = inspect.signature(function)
    try:
        resolved_hints = typing.get_type_hints(function)
    except Exception:
        resolved_hints = {}

    specs: list[ParameterSpec] = []
    for parameter in signature.parameters.values():
        if parameter.kind in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }:
            continue
        specs.append(
            ParameterSpec(
                name=parameter.name,
                cli_name=resolve_cli_name(parameter.name, command_key=command_key),
                annotation=resolved_hints.get(parameter.name, parameter.annotation),
                required=parameter.default is inspect._empty,
                default=None if parameter.default is inspect._empty else parameter.default,
                kind=parameter.kind,
            )
        )
    return specs


def apply_click_parameters(
    command: click.Command,
    specs: list[ParameterSpec],
) -> click.Command:
    """按参数描述把 Click 参数挂载到命令对象上。"""
    params = [build_click_parameter(spec) for spec in specs]
    command.params = params + command.params
    return command


def build_click_parameter(spec: ParameterSpec) -> click.Parameter:
    """构建单个 Click 参数对象。"""
    if resolve_base_type(spec.annotation) is bool:
        return click.Option(
            [f"--{spec.cli_name}/--no-{spec.cli_name}", spec.name],
            default=bool(spec.default),
            show_default=True,
        )

    kwargs: dict[str, Any] = {
        "required": spec.required,
        "default": spec.default,
        "show_default": not spec.required and spec.default not in (None, inspect._empty),
        "type": build_click_type(spec.annotation),
    }
    if spec.is_variadic:
        kwargs["multiple"] = True
        if spec.default is None:
            kwargs["default"] = ()

    return click.Option([f"--{spec.cli_name}", spec.name], **kwargs)


def build_click_type(annotation: Any) -> click.ParamType:
    """把注解转换为 Click 类型。"""
    base = resolve_base_type(annotation)
    if inspect.isclass(base) and issubclass(base, enum.Enum):
        return click.Choice([member.name for member in base], case_sensitive=False)
    if base is int:
        return click.INT
    if base is float:
        return click.FLOAT
    if base is bool:
        return click.STRING
    return click.STRING


def coerce_parameter_value(annotation: Any, value: Any) -> Any:
    """把 Click 解析出的值转换成真实调用值。"""
    if value is None:
        return None

    base = resolve_base_type(annotation)
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    if inspect.isclass(base) and issubclass(base, enum.Enum):
        if isinstance(value, base):
            return value
        for member in base:
            if member.name.lower() == str(value).lower():
                return member
        raise click.BadParameter(f"Unsupported enum value: {value}")

    if origin in (list, tuple, set) or any(
        typing.get_origin(arg) in (list, tuple, set) for arg in args
    ):
        sequence = value if isinstance(value, (list, tuple)) else [value]
        item_type = infer_sequence_item_type(annotation)
        converted = [coerce_scalar(item_type, item) for item in sequence]
        if origin is tuple:
            return tuple(converted)
        if origin is set:
            return set(converted)
        return converted

    if base is bool:
        return normalize_bool(value)

    if isinstance(value, tuple) and len(value) == 1:
        value = value[0]

    return coerce_scalar(base, value)


def resolve_base_type(annotation: Any) -> Any:
    """获取注解的基础类型。"""
    if annotation in (inspect._empty, Any):
        return str

    origin = typing.get_origin(annotation)
    if origin is typing.Union:
        args = [arg for arg in typing.get_args(annotation) if arg is not NoneType]
        if not args:
            return str
        if len(args) == 1:
            return resolve_base_type(args[0])
        if any(typing.get_origin(arg) in (list, tuple, set) for arg in args):
            return list
        return resolve_base_type(args[0])

    if origin in (list, tuple, set):
        return origin
    return annotation


def infer_sequence_item_type(annotation: Any) -> Any:
    """推断集合类注解中的元素类型。"""
    args = typing.get_args(annotation)
    if not args:
        return str
    item = args[0]
    if typing.get_origin(item) is typing.Union:
        nested = [arg for arg in typing.get_args(item) if arg is not NoneType]
        return nested[0] if nested else str
    return item


def coerce_scalar(expected_type: Any, value: Any) -> Any:
    """转换单个标量值。"""
    if value is None:
        return None
    if expected_type in (inspect._empty, Any, str):
        return try_parse_structured_string(value)
    if expected_type is int:
        return int(value)
    if expected_type is float:
        return float(value)
    if expected_type is bool:
        return normalize_bool(value)
    return try_parse_structured_string(value)


def try_parse_structured_string(value: Any) -> Any:
    """尽量把 JSON 风格字符串解析为结构化对象。"""
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped.startswith("[") or stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return value
    return value


def normalize_bool(value: Any) -> bool:
    """把宽松的字符串表示转换为布尔值。"""
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    raise click.BadParameter(f"Unable to parse boolean value: {value}")
