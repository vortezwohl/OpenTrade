"""把 Python 函数签名映射为 Click 参数。

本模块负责做最小可用的签名反射：尽可能根据注解和默认值推导 CLI 选项，
并把复杂或不稳定的类型统一降级为字符串输入，再在调用前做轻量转换。
这样可以在保证命令覆盖面的同时，避免为每个函数手写大量重复的参数定义。
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


@dataclass(slots=True)
class ParameterSpec:
    """描述一个命令参数应如何暴露到 Click。"""

    name: str
    cli_name: str
    annotation: Any
    required: bool
    default: Any
    kind: inspect._ParameterKind

    @property
    def is_variadic(self) -> bool:
        """当前参数是否适合映射为多值参数。"""
        origin = typing.get_origin(self.annotation)
        args = typing.get_args(self.annotation)
        return origin in (list, tuple, set) or any(
            typing.get_origin(arg) in (list, tuple, set) for arg in args
        )


def build_parameter_specs(function: Any) -> list[ParameterSpec]:
    """从函数签名生成参数描述。"""
    signature = inspect.signature(function)
    try:
        resolved_hints = typing.get_type_hints(function)
    except Exception:
        resolved_hints = {}
    specs: list[ParameterSpec] = []
    for parameter in signature.parameters.values():
        if parameter.kind == inspect.Parameter.VAR_POSITIONAL:
            continue
        if parameter.kind == inspect.Parameter.VAR_KEYWORD:
            continue
        specs.append(
            ParameterSpec(
                name=parameter.name,
                cli_name=parameter.name.replace("_", "-"),
                annotation=resolved_hints.get(parameter.name, parameter.annotation),
                required=parameter.default is inspect._empty,
                default=None if parameter.default is inspect._empty else parameter.default,
                kind=parameter.kind,
            )
        )
    return specs


def apply_click_parameters(command: click.Command, specs: list[ParameterSpec]) -> click.Command:
    """按签名描述把 Click 参数附着到命令对象上。"""
    params: list[click.Parameter] = []
    for spec in reversed(specs):
        click_param = build_click_parameter(spec)
        params.insert(0, click_param)
    command.params = params + command.params
    return command


def build_click_parameter(spec: ParameterSpec) -> click.Parameter:
    """构建单个 Click 参数对象。"""
    param_type = build_click_type(spec.annotation)
    if spec.required and spec.kind in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ):
        return click.Argument(
            [spec.name],
            nargs=-1 if spec.is_variadic else 1,
            type=param_type,
            required=True,
        )

    option_decls = [f"--{spec.cli_name}"]
    kwargs: dict[str, Any] = {
        "required": False,
        "default": spec.default,
        "show_default": spec.default not in (None, inspect._empty),
        "type": param_type,
    }
    if spec.is_variadic:
        kwargs["multiple"] = True
        if spec.default is None:
            kwargs["default"] = ()
    if resolve_base_type(spec.annotation) is bool and spec.default is False:
        option_decls.append(f"--no-{spec.cli_name}")
        return click.Option(
            option_decls,
            is_flag=True,
            flag_value=True,
            default=False,
            help=f"切换参数 {spec.name}。",
        )
    return click.Option(option_decls, **kwargs)


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
    """把 Click 解析出的值转换成实际调用值。"""
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
    """推断集合类注解内部的元素类型。"""
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
    """尽量把 JSON 或逗号串解析成结构化对象。"""
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
