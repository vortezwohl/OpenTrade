"""控制台结果渲染层。

该模块统一负责把执行结果转换为 `table`、`json`、`csv`、`tsv` 文本。除常规
`DataFrame` / `Series` / `dict` 之外，也负责渲染结构化 observation payload。
observation 模式使用独立的 boxed ASCII 布局，保证：

- section 风格统一；
- `trace_points` 先于 `recent_events`；
- 超长内容先折行，再根据折行结果动态计算宽度；
- 任何一行都不会穿出右边框。
"""

from __future__ import annotations

import json
import textwrap
from dataclasses import asdict, is_dataclass
from typing import Any, Iterable

import pandas as pd

from efinance_cli.models import (
    ObservationEvent,
    ObservationPayload,
    ObservationSection,
    ObservationTraceGroup,
    OutputOptions,
)


BOX_MAX_CONTENT_WIDTH = 62
TRACE_BLOCK_BAR_COUNT = 8


def should_include_index(options: OutputOptions) -> bool:
    """统一判断导出类输出是否需要保留索引列。"""

    if options.format_name in {"csv", "tsv"}:
        return False
    return not options.no_index


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
    if isinstance(value, ObservationPayload):
        return render_observation_table(value, options)
    if isinstance(value, dict) and any(isinstance(item, ObservationPayload) for item in value.values()):
        return render_observation_mapping(value, options)
    if isinstance(value, pd.DataFrame):
        return render_dataframe(value, options)
    if isinstance(value, pd.Series):
        frame = value.to_frame(name="value")
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

    if isinstance(value, ObservationPayload):
        return observation_to_long_frame(value).to_csv(
            index=should_include_index(options),
            sep=sep,
        )
    if isinstance(value, dict) and any(isinstance(item, ObservationPayload) for item in value.values()):
        frames: list[pd.DataFrame] = []
        for key, item in value.items():
            if isinstance(item, ObservationPayload):
                frame = observation_to_long_frame(item, source=str(key))
            else:
                frame = to_dataframe(item)
                frame.insert(0, "__source__", key)
            frames.append(frame)
        if not frames:
            return ""
        return pd.concat(frames, ignore_index=True).to_csv(
            index=should_include_index(options),
            sep=sep,
        )
    if isinstance(value, pd.Series):
        value = value.to_frame(name="value")
    if isinstance(value, pd.DataFrame):
        frame = maybe_limit(value, options)
        if options.transpose:
            frame = frame.transpose()
        return frame.to_csv(index=should_include_index(options), sep=sep)
    if isinstance(value, dict):
        frames: list[pd.DataFrame] = []
        for key, item in value.items():
            frame = to_dataframe(item)
            frame.insert(0, "__source__", key)
            frames.append(frame)
        if not frames:
            return ""
        return pd.concat(frames, ignore_index=True).to_csv(
            index=should_include_index(options),
            sep=sep,
        )
    frame = pd.DataFrame({"value": list(value) if isinstance(value, (list, tuple, set)) else [value]})
    return frame.to_csv(index=should_include_index(options), sep=sep)


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

    if isinstance(value, ObservationPayload):
        return observation_to_long_frame(value)
    if isinstance(value, pd.DataFrame):
        return value
    if isinstance(value, pd.Series):
        return value.to_frame(name="value")
    if isinstance(value, dict):
        return pd.DataFrame([to_serializable(value)])
    if isinstance(value, (list, tuple, set)):
        return pd.DataFrame({"value": list(value)})
    return pd.DataFrame({"value": [value]})


def to_serializable(value: Any) -> Any:
    """把复杂对象转换为 JSON 可序列化结构。"""

    if isinstance(value, ObservationPayload):
        return {
            "meta": to_serializable(value.meta),
            "latest_quote": to_serializable(value.latest_quote),
            "current_metrics": to_serializable(value.current_metrics),
            "trace_points": to_serializable(value.trace_points),
            "recent_events": to_serializable(value.recent_events),
            "sections": to_serializable(value.sections),
        }
    if isinstance(value, ObservationSection):
        return {
            "name": value.name,
            "rows": to_serializable(value.rows),
            "render_hint": value.render_hint,
        }
    if isinstance(value, ObservationTraceGroup):
        return {
            "name": value.name,
            "points": to_serializable(value.points),
        }
    if isinstance(value, ObservationEvent):
        return asdict(value)
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


def render_observation_table(payload: ObservationPayload, options: OutputOptions) -> str:
    """渲染单个 observation payload。"""

    sections: list[str] = []
    sections.append(render_boxed_section("meta", render_mapping_lines(payload.meta)))
    if payload.latest_quote:
        sections.append(render_boxed_section("latest_quote", render_mapping_lines(payload.latest_quote)))
    sections.append(render_boxed_section("current_metrics", render_mapping_lines(payload.current_metrics)))
    sections.extend(render_generic_sections_text(payload.sections, options))
    sections.extend(render_trace_groups_text(payload.trace_points))
    sections.append(render_events_text(payload.recent_events))
    return "\n\n".join(section for section in sections if section)


def render_observation_mapping(value: dict[Any, Any], options: OutputOptions) -> str:
    """渲染多个 observation payload。"""

    sections: list[str] = []
    for key, item in value.items():
        if isinstance(item, ObservationPayload):
            sections.append(render_boxed_section(f"source.{key}", None))
            sections.append(render_observation_table(item, options))
        else:
            sections.append(f"== {key} ==")
            sections.append(render_table(item, options))
    return "\n\n".join(section for section in sections if section)


def render_trace_groups_text(trace_groups: list[ObservationTraceGroup]) -> list[str]:
    """渲染 trace group 列表。"""

    sections: list[str] = []
    for group in trace_groups:
        section_title = f"trace_points.{group.name}"
        if not group.points:
            sections.append(render_boxed_section(section_title, ["<empty>"]))
            continue

        fields = [field for field in group.points[0].keys() if field != "bar_offset"]
        blocks = chunk_points(group.points, TRACE_BLOCK_BAR_COUNT)
        block_lines: list[str] = []
        for block_index, block in enumerate(blocks, start=1):
            if block_lines:
                block_lines.append("")
            first_offset = block[0]["bar_offset"]
            last_offset = block[-1]["bar_offset"]
            block_lines.append(f"[block {block_index}] bar_offset: {first_offset} -> {last_offset}")
            block_lines.append(
                "bar_offset: "
                + " | ".join(str(point["bar_offset"]) for point in block)
            )
            for field in fields:
                block_lines.append(
                    f"{field}: "
                    + " | ".join(normalize_display_scalar(point.get(field)) for point in block)
                )
        sections.append(render_boxed_section(section_title, block_lines))
    return sections


def render_generic_sections_text(
    sections: list[ObservationSection],
    options: OutputOptions,
) -> list[str]:
    """把通用 observation sections 渲染为 table 文本。"""

    rendered: list[str] = []
    for section in sections:
        if section.render_hint == "kv":
            lines = render_mapping_lines(section.rows[0] if section.rows else {})
            rendered.append(render_boxed_section(section.name, lines))
            continue
        if section.render_hint == "records":
            rendered.extend(render_record_sections(section, options))
            continue
        rendered.append(render_boxed_section(section.name, ["<unsupported render_hint>"]))
    return rendered


def render_record_sections(
    section: ObservationSection,
    options: OutputOptions,
) -> list[str]:
    """把 observation section 渲染为逐记录纵向文本。"""

    rows = section.rows
    if options.limit is not None:
        rows = rows[: options.limit]
    if not rows:
        return [render_boxed_section(section.name, ["<empty>"])]

    rendered: list[str] = []
    for index, row in enumerate(rows, start=1):
        rendered.append(
            render_boxed_section(
                f"{section.name}[{index}]",
                render_mapping_lines(row),
            )
        )
    return rendered


def render_events_text(events: list[ObservationEvent]) -> str:
    """把 recent events 渲染为单个总外框。"""

    if not events:
        return render_boxed_section("recent_events", ["<empty>"])

    lines: list[str] = []
    for index, event in enumerate(events, start=1):
        if index > 1:
            lines.append("")
        event_dict = to_serializable(event)
        lines.append(f"[{index}] bars_ago: {event_dict['bars_ago']}")
        ordered_keys = [
            "event_key",
            "subject_a",
            "relation",
            "subject_b",
            "description",
        ]
        for key in ordered_keys:
            value = event_dict.get(key)
            if value in (None, ""):
                continue
            lines.append(f"    {key}: {normalize_display_scalar(value)}")

        metric_chunks = build_event_metric_chunks(event_dict)
        if metric_chunks:
            lines.extend(metric_chunks)
    return render_boxed_section("recent_events", lines)


def build_event_metric_chunks(event_dict: dict[str, Any]) -> list[str]:
    """把事件中的前值/现值整理成可折行的文本块。"""

    metric_tokens: list[str] = []
    for key in ("prev_a", "prev_b", "curr_a", "curr_b"):
        value = event_dict.get(key)
        if value is None:
            continue
        metric_tokens.append(f"{key}: {normalize_display_scalar(value)}")

    if not metric_tokens:
        return []

    lines: list[str] = []
    current_line = "    "
    for token in metric_tokens:
        candidate = token if current_line.strip() == "" else f"{current_line}   {token}".rstrip()
        if len(candidate) <= BOX_MAX_CONTENT_WIDTH:
            current_line = candidate
            continue
        if current_line.strip():
            lines.append(current_line.rstrip())
        current_line = f"    {token}"
    if current_line.strip():
        lines.append(current_line.rstrip())
    return lines


def render_mapping_lines(mapping: dict[str, Any]) -> list[str]:
    """把字典转换为纵向 key/value 行。"""

    if not mapping:
        return ["<empty>"]
    return [f"{key}: {normalize_display_scalar(value)}" for key, value in mapping.items()]


def render_boxed_section(title: str, lines: Iterable[str] | None) -> str:
    """把若干文本行渲染为规整的 ASCII 外框。"""

    prepared_lines = prepare_box_lines(lines) if lines is not None else []
    content_width = max(
        [len(title), *(len(line) for line in prepared_lines)],
        default=len(title),
    )
    top_bottom = "+" + "-" * (content_width + 2) + "+"
    result = [top_bottom]
    result.append(f"| {title.ljust(content_width)} |")
    result.append(top_bottom)
    if lines is None:
        return "\n".join(result)
    for line in prepared_lines:
        result.append(f"| {line.ljust(content_width)} |")
    result.append(top_bottom)
    return "\n".join(result)


def prepare_box_lines(lines: Iterable[str], width_limit: int = BOX_MAX_CONTENT_WIDTH) -> list[str]:
    """先折行，再返回可安全绘制到外框中的内容行。"""

    prepared: list[str] = []
    for raw_line in lines:
        line = str(raw_line)
        if not line:
            prepared.append("")
            continue
        prepared.extend(wrap_box_line(line, width_limit))
    return prepared or [""]


def wrap_box_line(line: str, width_limit: int) -> list[str]:
    """为单行文本执行稳定折行。"""

    if len(line) <= width_limit:
        return [line]

    indent = len(line) - len(line.lstrip(" "))
    prefix = " " * indent
    content = line[indent:]
    if not content:
        return [""]

    wrapper = textwrap.TextWrapper(
        width=width_limit,
        initial_indent=prefix,
        subsequent_indent=prefix,
        break_long_words=True,
        break_on_hyphens=True,
        replace_whitespace=False,
        drop_whitespace=False,
    )
    return [item.rstrip() for item in wrapper.wrap(content)] or [prefix.rstrip()]


def split_display_tokens(content: str) -> list[str]:
    """按空格与常见分隔符拆分折行 token。"""

    separators = {" ", "_", "-", ",", "/", ":", "|"}
    tokens: list[str] = []
    current = ""
    for char in content:
        current += char
        if char in separators:
            tokens.append(current)
            current = ""
    if current:
        tokens.append(current)
    return tokens or [content]


def observation_to_long_frame(
    payload: ObservationPayload,
    source: str | None = None,
) -> pd.DataFrame:
    """把 observation payload 展平成 long-form DataFrame。"""

    rows: list[dict[str, Any]] = []
    source_value = source or payload.meta.get("code") or payload.meta.get("name")

    for key, value in payload.meta.items():
        rows.append(
            build_long_row(
                source=source_value,
                section="meta",
                item_type="field",
                item_id=key,
                field=key,
                value=value,
            )
        )
    for key, value in payload.latest_quote.items():
        rows.append(
            build_long_row(
                source=source_value,
                section="latest_quote",
                item_type="field",
                item_id=key,
                field=key,
                value=value,
            )
        )
    for key, value in payload.current_metrics.items():
        rows.append(
            build_long_row(
                source=source_value,
                section="current_metrics",
                item_type="metric",
                item_id=key,
                field=key,
                value=value,
            )
        )
    for section in payload.sections:
        for row_index, row in enumerate(section.rows, start=1):
            row_dict = to_serializable(row)
            item_id = f"{section.name}_{row_index}"
            for field, value in row_dict.items():
                rows.append(
                    build_long_row(
                        source=source_value,
                        section=section.name,
                        item_type="section_row",
                        item_id=item_id,
                        field=str(field),
                        value=value,
                    )
                )
    for group in payload.trace_points:
        for point in group.points:
            bar_offset = point.get("bar_offset")
            for field, value in point.items():
                if field == "bar_offset":
                    continue
                rows.append(
                    build_long_row(
                        source=source_value,
                        section="trace_points",
                        item_type="trace_point",
                        item_id=group.name,
                        group=group.name,
                        bar_offset=bar_offset,
                        field=field,
                        value=value,
                    )
                )
    for index, event in enumerate(payload.recent_events, start=1):
        event_dict = to_serializable(event)
        event_id = f"event_{index}"
        for field, value in event_dict.items():
            if value is None:
                continue
            rows.append(
                build_long_row(
                    source=source_value,
                    section="recent_events",
                    item_type="event",
                    item_id=event_id,
                    event_index=index,
                    bars_ago=event_dict.get("bars_ago"),
                    event_key=event_dict.get("event_key"),
                    relation=event_dict.get("relation"),
                    field=field,
                    value=value,
                )
            )
    return pd.DataFrame(rows)


def build_long_row(
    *,
    source: str | None,
    section: str,
    item_type: str,
    item_id: str,
    field: str,
    value: Any,
    group: str | None = None,
    bar_offset: int | None = None,
    event_index: int | None = None,
    event_key: str | None = None,
    relation: str | None = None,
    bars_ago: int | None = None,
) -> dict[str, Any]:
    """构建一行 long-form observation 记录。"""

    return {
        "__source__": source,
        "section": section,
        "item_type": item_type,
        "item_id": item_id,
        "group": group,
        "bar_offset": bar_offset,
        "event_index": event_index,
        "event_key": event_key,
        "relation": relation,
        "bars_ago": bars_ago,
        "field": field,
        "value": normalize_scalar_for_export(value),
    }


def chunk_points(points: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    """按固定块大小切分 trace 点。"""

    return [points[index : index + size] for index in range(0, len(points), size)]


def normalize_display_scalar(value: Any) -> str:
    """把值标准化为适合终端展示的英文字符串。"""

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        text = f"{value:.6f}".rstrip("0").rstrip(".")
        return text if text else "0"
    return str(value)


def normalize_scalar_for_export(value: Any) -> Any:
    """把值标准化为适合 CSV/TSV 导出的基础类型。"""

    if value is None:
        return None
    if isinstance(value, float):
        return float(f"{value:.10f}")
    return value
