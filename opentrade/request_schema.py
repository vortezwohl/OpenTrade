"""把请求 schema 转成 Click 选项并做标准化。

主要职责：

1. 根据 schema 构造 Click 选项；
2. 把 CLI 原始参数归一化成 shared 命令使用的 provider-neutral request；
3. 在进入 backend 适配前完成字段标准化和基础语义校验。
"""

from __future__ import annotations

import typing
from types import NoneType
from typing import Any

import click

from opentrade.command_catalog import MARKET_CHOICES
from opentrade.models import RequestField, RequestSchema


def build_click_options_for_schema(
    schema: RequestSchema
) -> list[click.Option]:
    """根据 schema 构造 Click 选项列表。"""
    options: list[click.Option] = []
    for field in schema.fields:
        options.append(build_click_option(field))
    return options


def build_click_option(field: RequestField) -> click.Option:
    """为单个字段构造 Click 选项。"""
    primary_option_name = f"--{field.cli_name}"
    option_declarations = [primary_option_name]
    option_declarations.extend(f"--{alias}" for alias in field.cli_aliases)
    expected_type = unwrap_annotation(field.annotation)
    if expected_type is bool:
        return click.Option(
            [
                f"{primary_option_name}/--no-{field.cli_name}",
                field.name,
            ],
            default=bool(field.default),
            show_default=True,
            help=field.help_text,
        )

    if field.choices:
        click_type: click.ParamType = click.Choice(
            list(field.choices), case_sensitive=False
        )
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

    return click.Option([*option_declarations, field.name], **kwargs)


def validate_request_data(schema: RequestSchema,
                          raw_data: dict[str, Any]) -> dict[str, Any]:
    """按 schema 校验并标准化请求数据。"""
    normalized: dict[str, Any] = {}
    consumed_keys: set[str] = set()
    for field in schema.fields:
        value, provided = _extract_raw_field_value(field, raw_data)
        consumed_keys.update(_known_field_names(field))
        if not provided or value is None:
            if field.required and field.default is None:
                raise click.ClickException(
                    f"Missing required option '--{field.cli_name}'."
                )
            if field.default is not None or field.name in raw_data:
                normalized[field.name
                           ] = _normalize_schema_field(field, field.default)
            continue
        normalized[
            field.name
        ] = _normalize_schema_field(field, coerce_schema_value(field, value))
        _validate_semantic_field(field, normalized[field.name])

    if not schema.allow_extra:
        unknown = sorted(set(raw_data) - consumed_keys)
        if unknown:
            raise click.ClickException(
                f"Unknown request fields: {', '.join(unknown)}"
            )
    else:
        for key, value in raw_data.items():
            if key not in normalized:
                normalized[key] = value

    return normalized


def coerce_schema_value(field: RequestField, value: Any) -> Any:
    """把 Click 原始参数值转换为 schema 约束下的 Python 值。"""
    expected_type = unwrap_annotation(field.annotation)
    if field.multiple:
        sequence = value if isinstance(value, (list, tuple)) else (value, )
        return [coerce_scalar(expected_type, item) for item in sequence]
    if isinstance(value, (list, tuple)):
        if len(value) != 1:
            raise click.ClickException(
                f"Option '--{field.cli_name}' only accepts a single value.",
            )
        value = value[0]
    return coerce_scalar(expected_type, value)


def unwrap_annotation(annotation: Any) -> Any:
    """拆出可用于 Click 的基础类型。"""
    origin = typing.get_origin(annotation)
    if origin is typing.Union:
        args = [
            item for item in typing.get_args(annotation)
            if item is not NoneType
        ]
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
    return str(value).strip() if isinstance(value, str) else value


def normalize_bool(value: Any) -> bool:
    """把常见布尔文本解析为布尔值。"""
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    raise click.ClickException(f"Unable to parse boolean value: {value}")


def _extract_raw_field_value(field: RequestField,
                             raw_data: dict[str, Any]) -> tuple[Any, bool]:
    for key in _known_field_names(field):
        if key in raw_data:
            return raw_data[key], True
    return None, False


def _known_field_names(field: RequestField) -> tuple[str, ...]:
    return (field.name, *field.legacy_names)


def _normalize_schema_field(field: RequestField, value: Any) -> Any:
    if value is None:
        return None
    semantic_type = field.semantic_type or field.name
    if semantic_type in {"symbol", "quote-id", "keyword"}:
        return str(value).strip()
    if semantic_type in {"symbols", "quote-ids"}:
        values = value if isinstance(value, list) else [value]
        return [str(item).strip() for item in values if str(item).strip()]
    if semantic_type in {"start-date", "end-date"}:
        return _normalize_compact_date(value)
    if semantic_type == "market":
        return _normalize_market_name(value)
    return value


def _validate_semantic_field(field: RequestField, value: Any) -> None:
    semantic_type = field.semantic_type or field.name
    if semantic_type == "market":
        _validate_market_name(value)
    if field.name == "symbol" and value in (None, ""):
        raise click.ClickException(
            f"Missing required option '--{field.cli_name}'."
        )


def _normalize_compact_date(value: Any) -> str:
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return text
    compact = text.replace("-", "")
    if len(compact) == 8 and compact.isdigit():
        return compact
    raise click.ClickException(f"Unsupported date format: {value}")


def _normalize_market_name(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text in MARKET_CHOICES:
        return text
    lowered = text.lower()
    alias_map = {
        "a_stock": "A_stock",
        "ashare": "A_stock",
        "a-share": "A_stock",
        "us_stock": "US_stock",
        "us": "US_stock",
        "hongkong": "Hongkong",
        "hk": "Hongkong",
    }
    return alias_map.get(lowered, text)


def _validate_market_name(value: Any) -> None:
    """校验 shared market 枚举是否合法。"""
    if value in (None, ""):
        return
    if isinstance(value, (list, tuple)):
        values = value
    else:
        values = (value, )
    allowed = set(MARKET_CHOICES)
    invalid = [str(item) for item in values if str(item) not in allowed]
    if invalid:
        raise click.ClickException(
            "Unknown market enum: " + ", ".join(invalid)
        )


def _validate_identifier_shape(field: RequestField, value: Any) -> None:
    """校验共享标识符形状，避免把 provider-native ID 混入 shared 契约。"""
    values = value if isinstance(value, list) else [value]
    invalid: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if not text:
            continue
        if field.name in {"symbol", "symbols"
                          } and _looks_like_eastmoney_quote_id(text):
            invalid.append(text)
    if invalid:
        raise click.ClickException(
            "Shared symbol contract does not accept Eastmoney quote_id: " +
            ", ".join(invalid)
        )


def _looks_like_eastmoney_quote_id(text: str) -> bool:
    if "." not in text:
        return False
    left, right = text.split(".", 1)
    return left.isdigit() and right.isdigit()
