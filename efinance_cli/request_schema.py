"""共享命令请求 schema 的构建、校验与 Click 参数映射。

该模块是多后端重构的第一层骨架。它解决两个核心问题：

1. 共享命令的参数不再从第三方函数签名反射得到，而是由显式 schema 驱动；
2. schema 既要能校验请求，也要能稳定生成 Click 参数，避免命令面继续被上游
   provider 的函数签名牵着走。
"""

from __future__ import annotations

import typing
from types import NoneType
from typing import Any

import click

from efinance_cli.models import RequestField, RequestSchema


def build_click_options_for_schema(schema: RequestSchema) -> list[click.Option]:
    """把请求 schema 转换为 Click 选项列表。"""

    options: list[click.Option] = []
    for field in schema.fields:
        options.append(build_click_option(field))
    return options


def build_click_option(field: RequestField) -> click.Option:
    """根据字段定义构造单个 Click 选项。"""

    option_name = f"--{field.cli_name}"
    expected_type = unwrap_annotation(field.annotation)
    if expected_type is bool:
        return click.Option(
            [f"{option_name}/--no-{field.cli_name}", field.name],
            default=bool(field.default),
            show_default=True,
            help=field.help_text,
        )

    if field.choices:
        click_type: click.ParamType = click.Choice(list(field.choices), case_sensitive=False)
    elif expected_type is int:
        click_type = click.INT
    elif expected_type is float:
        click_type = click.FLOAT
    else:
        click_type = click.STRING

    kwargs: dict[str, Any] = {
        "required": field.required,
        "default": field.default,
        "show_default": not field.required and field.default is not None,
        "type": click_type,
        "help": field.help_text,
    }
    if field.multiple:
        kwargs["multiple"] = True
        if field.default is None:
            kwargs["default"] = ()

    return click.Option([option_name, field.name], **kwargs)


def validate_request_data(schema: RequestSchema, raw_data: dict[str, Any]) -> dict[str, Any]:
    """按 schema 校验并归一化请求数据。"""

    field_map = schema.field_map()
    normalized: dict[str, Any] = {}
    for field in schema.fields:
        if field.name not in raw_data or raw_data[field.name] is None:
            if field.required and field.default is None:
                raise click.ClickException(f"Missing required option '--{field.cli_name}'.")
            if field.default is not None or field.name in raw_data:
                normalized[field.name] = field.default
            continue
        normalized[field.name] = coerce_schema_value(field, raw_data[field.name])
        if field.name == "market":
            _validate_market_name(normalized[field.name])

    if not schema.allow_extra:
        unknown = sorted(set(raw_data) - set(field_map))
        if unknown:
            raise click.ClickException(f"Unknown request fields: {', '.join(unknown)}")
    else:
        for key, value in raw_data.items():
            if key not in normalized:
                normalized[key] = value

    return normalized


def coerce_schema_value(field: RequestField, value: Any) -> Any:
    """把 Click 原始值转换为 schema 定义的目标值。"""

    expected_type = unwrap_annotation(field.annotation)
    if field.multiple:
        sequence = value if isinstance(value, (list, tuple)) else (value,)
        return [coerce_scalar(expected_type, item) for item in sequence]
    return coerce_scalar(expected_type, value)


def unwrap_annotation(annotation: Any) -> Any:
    """解包联合类型，返回主类型。"""

    origin = typing.get_origin(annotation)
    if origin is typing.Union:
        args = [item for item in typing.get_args(annotation) if item is not NoneType]
        if not args:
            return str
        return unwrap_annotation(args[0])
    if annotation in (Any, None, NoneType):
        return str
    return annotation


def coerce_scalar(expected_type: Any, value: Any) -> Any:
    """转换单个标量值。"""

    if value is None:
        return None
    if expected_type is bool:
        return normalize_bool(value)
    if expected_type is int:
        return int(value)
    if expected_type is float:
        return float(value)
    return value


def normalize_bool(value: Any) -> bool:
    """把宽松布尔值转换为稳定布尔类型。"""

    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    raise click.ClickException(f"Unable to parse boolean value: {value}")


def _validate_market_name(value: Any) -> None:
    """对首批共享搜索命令的 market 参数做可读校验。"""

    if value in (None, ""):
        return
    allowed = {
        "A_stock",
        "A_stock_index",
        "B_stock",
        "Hongkong",
        "US_stock",
    }
    if str(value) not in allowed:
        raise click.ClickException(f"Unknown market enum: {value}")
