"""控制台结果渲染层。

渲染层采用 Strategy 风格：不同返回类型使用不同渲染策略，但外部统一通过
`render_value` 入口调用。这样既能保持 DataFrame、Series、list、dict 这些返回值
的展示一致性，也能在后续扩展到更复杂的数据结构时控制影响范围。
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

import pandas as pd

from efinance_cli.models import OutputOptions


def render_value(value: Any, options: OutputOptions) -> str:
    """把函数返回值渲染为字符串。"""
    if options.format_name == "json":
        return render_json(value)
    if options.format_name == "csv":
        return render_csv(value, options)
    if options.format_name == "tsv":
        return render_csv(value, options, sep="\t")
    return render_table(value, options)


def render_table(value: Any, options: OutputOptions) -> str:
    """按表格风格渲染结果。"""
    if value is None:
        return "NULL"
    if isinstance(value, pd.DataFrame):
        return render_dataframe(value, options)
    if isinstance(value, pd.Series):
        frame = value.to_frame(name="值")
        return render_dataframe(frame, options)
    if isinstance(value, dict):
        return render_mapping(value, options)
    if isinstance(value, (list, tuple, set)):
        return render_sequence(value, options)
    return str(value)


def render_json(value: Any) -> str:
    """渲染 JSON。"""
    return json.dumps(to_serializable(value), ensure_ascii=False, indent=2, default=str)


def render_csv(value: Any, options: OutputOptions, sep: str = ",") -> str:
    """渲染 CSV/TSV。"""
    if isinstance(value, pd.Series):
        value = value.to_frame(name="值")
    if isinstance(value, pd.DataFrame):
        frame = maybe_limit(value, options)
        if options.transpose:
            frame = frame.transpose()
        return frame.to_csv(index=not options.no_index, sep=sep)
    if isinstance(value, dict):
        frames: list[pd.DataFrame] = []
        for key, item in value.items():
            frame = to_dataframe(item)
            frame.insert(0, "__source__", key)
            frames.append(frame)
        if not frames:
            return ""
        return pd.concat(frames, ignore_index=True).to_csv(
            index=not options.no_index,
            sep=sep,
        )
    return pd.DataFrame({"value": list(value) if isinstance(value, (list, tuple, set)) else [value]}).to_csv(
        index=not options.no_index,
        sep=sep,
    )


def render_dataframe(frame: pd.DataFrame, options: OutputOptions) -> str:
    """渲染 DataFrame。"""
    frame = maybe_limit(frame, options)
    if options.transpose:
        frame = frame.transpose()
    if not options.full:
        with pd.option_context(
            "display.max_columns",
            20,
            "display.width",
            200,
            "display.max_colwidth",
            60,
        ):
            return frame.to_string(index=not options.no_index)
    with pd.option_context(
        "display.max_columns",
        None,
        "display.width",
        None,
        "display.max_colwidth",
        None,
    ):
        return frame.to_string(index=not options.no_index)


def render_mapping(value: dict[Any, Any], options: OutputOptions) -> str:
    """渲染字典结果。"""
    if not value:
        return "{}"
    chunks: list[str] = []
    for key, item in value.items():
        chunks.append(f"== {key} ==")
        chunks.append(render_table(item, options))
    return "\n\n".join(chunks)


def render_sequence(value: Any, options: OutputOptions) -> str:
    """渲染列表、元组或集合。"""
    data = list(value)
    frame = pd.DataFrame({"value": data})
    return render_dataframe(frame, options)


def maybe_limit(frame: pd.DataFrame, options: OutputOptions) -> pd.DataFrame:
    """按配置裁剪行数。"""
    if options.limit is None:
        return frame
    return frame.head(options.limit)


def to_dataframe(value: Any) -> pd.DataFrame:
    """尽量把任意值转换成 DataFrame。"""
    if isinstance(value, pd.DataFrame):
        return value
    if isinstance(value, pd.Series):
        return value.to_frame(name="值")
    if isinstance(value, (list, tuple, set)):
        return pd.DataFrame({"value": list(value)})
    return pd.DataFrame({"value": [value]})


def to_serializable(value: Any) -> Any:
    """把复杂对象转换为 JSON 可序列化结构。"""
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, pd.Series):
        return value.to_dict()
    if isinstance(value, dict):
        return {str(key): to_serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_serializable(item) for item in value]
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "_asdict"):
        return value._asdict()
    return value
