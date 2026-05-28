"""结构化观察输出的组装与事件检测。

该模块位于指标增强层与渲染层之间，负责把增强后的行情结果整理为统一的 observation
payload。当前阶段优先支持：

- `get-quote-history`
- `get-latest-quote`

模块同时提供：

- 最近 N 根 trace 提取
- 多指标家族的客观事件检测
- 英文字段名的结构化 observation 数据
"""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

from efinance_cli.enrichment.indicators import enrich_history_frame
from efinance_cli.enrichment.levels import LEVELS, normalize_indicator_level
from efinance_cli.enrichment.service import (
    HISTORY_COMMANDS,
    LATEST_COMMANDS,
    SINGLE_ROW_COMMANDS,
    extract_code_from_series,
    fetch_history_for_code,
)
from efinance_cli.models import (
    ObservationEvent,
    ObservationPayload,
    ObservationSection,
    ObservationTraceGroup,
)


RAW_FIELD_ALIASES: dict[str, list[str]] = {
    "code": ["股票代码", "债券代码", "期货代码", "基金代码", "代码", "行情ID"],
    "name": ["股票名称", "债券名称", "期货名称", "基金名称", "名称"],
    "date": ["日期", "时间"],
    "close": ["收盘", "最新价", "单位净值", "close"],
    "open": ["开盘", "今开", "open"],
    "high": ["最高", "high"],
    "low": ["最低", "low"],
    "volume": ["成交量", "volume"],
    "turnover": ["成交额", "turnover"],
    "change_pct": ["涨跌幅", "change_pct"],
    "change_amount": ["涨跌额", "change_amount"],
    "amplitude": ["振幅", "amplitude"],
    "turnover_rate": ["换手率", "turnover_rate"],
}

SERIES_ALIASES: dict[str, list[str]] = {
    **RAW_FIELD_ALIASES,
    "ma5": ["ma5"],
    "ma10": ["ma10"],
    "ma20": ["ma20"],
    "ema12": ["ema12"],
    "ema26": ["ema26"],
    "macd_dif": ["macd_dif"],
    "macd_dea": ["macd_dea"],
    "macd_histogram": ["macd_histogram"],
    "rsi14": ["rsi14"],
    "kdj_k": ["kdj_k"],
    "kdj_d": ["kdj_d"],
    "kdj_j": ["kdj_j"],
    "boll_upper": ["boll_upper"],
    "boll_lower": ["boll_lower"],
    "boll_middle": ["boll_middle"],
    "atr14": ["atr14"],
    "roc12": ["roc12"],
    "bias6": ["bias6"],
    "bbi": ["bbi"],
    "ppo": ["ppo"],
    "ppo_signal": ["ppo_signal"],
    "trix": ["trix"],
    "tsi": ["tsi"],
    "cci14": ["cci14"],
    "williams_r14": ["williams_r14"],
    "plus_di": ["plus_di"],
    "minus_di": ["minus_di"],
    "adx": ["adx"],
    "donchian_upper": ["donchian_upper"],
    "donchian_lower": ["donchian_lower"],
    "keltner_upper": ["keltner_upper"],
    "keltner_lower": ["keltner_lower"],
    "natr14": ["natr14"],
    "supertrend": ["supertrend"],
    "supertrend_direction": ["supertrend_direction"],
    "mfi14": ["mfi14"],
    "pvt": ["pvt"],
    "cmf20": ["cmf20"],
    "force_index13": ["force_index13"],
    "vwap": ["vwap"],
    "vr": ["vr"],
    "psy": ["psy"],
    "obv": ["obv"],
    "volume_ratio_5": ["volume_ratio_5"],
}

CURRENT_METRIC_FIELDS: list[str] = [
    "close",
    "open",
    "high",
    "low",
    "volume",
    "ma5",
    "ma10",
    "ma20",
    "ema12",
    "ema26",
    "macd_dif",
    "macd_dea",
    "macd_histogram",
    "rsi14",
    "kdj_k",
    "kdj_d",
    "kdj_j",
    "ppo",
    "ppo_signal",
    "atr14",
    "boll_upper",
    "boll_lower",
    "obv",
    "volume_ratio_5",
    "mfi14",
    "cmf20",
    "supertrend",
    "plus_di",
    "minus_di",
    "adx",
]

TRACE_GROUPS: dict[str, list[str]] = {
    "price_ma": ["close", "ma5", "ma10", "ma20", "ema12", "ema26"],
    "macd_osc": ["macd_dif", "macd_dea", "macd_histogram", "rsi14", "kdj_k", "kdj_d", "kdj_j", "ppo", "ppo_signal"],
    "volume_flow": ["volume", "obv", "volume_ratio_5", "mfi14", "cmf20", "force_index13", "vwap", "vr"],
}

OBSERVATION_MULTI_HISTORY_COMMANDS: set[tuple[str, str]] = {
    ("fund", "get_quote_history_multi"),
}

OBSERVATION_SINGLE_ROW_COMMANDS: set[tuple[str, str]] = set(SINGLE_ROW_COMMANDS)

OBSERVATION_REALTIME_LIST_COMMANDS: set[tuple[str, str]] = {
    ("stock", "get_realtime_quotes"),
    ("bond", "get_realtime_quotes"),
    ("futures", "get_realtime_quotes"),
}


def build_observation_output(request: Any, value: Any) -> Any:
    """根据命令与结果构建 observation 输出。

    如果当前命令不在首批支持范围内，或用户未选择 observation 视图，则原样返回。
    """

    if getattr(request.output, "view_mode", "raw") != "observation":
        return value

    command_key = (request.spec.module_name, request.spec.function_name)
    if command_key in HISTORY_COMMANDS or command_key in OBSERVATION_MULTI_HISTORY_COMMANDS:
        return build_history_observation_output(request, value)
    if command_key in LATEST_COMMANDS:
        return build_latest_observation_output(request, value)
    if command_key in OBSERVATION_SINGLE_ROW_COMMANDS:
        return build_single_row_observation_output(request, value)
    if command_key in OBSERVATION_REALTIME_LIST_COMMANDS:
        return build_realtime_list_observation_output(request, value)
    return build_generic_observation_output(request, value)


def build_generic_observation_output(request: Any, value: Any) -> ObservationPayload:
    """把未纳入行情 observation 契约的结果包装为通用 observation。"""

    meta = build_generic_meta(request, value)
    sections = build_generic_sections(value)
    return ObservationPayload(
        meta=meta,
        latest_quote={},
        current_metrics={},
        trace_points=[],
        recent_events=[],
        sections=sections,
    )


def build_history_observation_output(request: Any, value: Any) -> Any:
    """把历史行情结果转换为 observation payload。"""

    if isinstance(value, pd.DataFrame):
        return build_payload_from_history_frame(request, value)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, frame in value.items():
            if isinstance(frame, pd.DataFrame):
                result[str(key)] = build_payload_from_history_frame(request, frame)
            else:
                result[str(key)] = frame
        return result
    return value


def build_latest_observation_output(request: Any, value: Any) -> Any:
    """把最新行情结果转换为 observation payload。"""

    if not isinstance(value, pd.DataFrame):
        return value

    payloads: dict[str, ObservationPayload] = {}
    for idx, row in value.iterrows():
        payload = build_payload_from_latest_row(request, row)
        if payload is None:
            continue
        key = payload.meta.get("code") or payload.meta.get("row_id") or str(idx)
        payloads[str(key)] = payload

    if not payloads:
        return value
    if len(payloads) == 1:
        return next(iter(payloads.values()))
    return payloads


def build_single_row_observation_output(request: Any, value: Any) -> Any:
    """把单行结果转换为 observation payload。"""

    if isinstance(value, pd.Series):
        payload = build_payload_from_single_row(request, value)
        return payload or value
    if isinstance(value, pd.DataFrame):
        return build_mapping_payloads_from_rows(request, value, builder=build_payload_from_single_row)
    return value


def build_realtime_list_observation_output(request: Any, value: Any) -> Any:
    """把实时列表结果转换为多 source observation。"""

    if not isinstance(value, pd.DataFrame):
        return value

    limited = limit_realtime_observation_frame(request, value)
    result = build_mapping_payloads_from_rows(request, limited, builder=build_payload_from_single_row)
    return result if result else value


def build_payload_from_history_frame(request: Any, frame: pd.DataFrame) -> ObservationPayload:
    """根据增强后的历史行情表构建 observation payload。"""

    trace_window = normalize_trace_window(getattr(request.output, "trace_window", 32))
    recent_frame = frame.tail(trace_window).reset_index(drop=True)
    latest_row = recent_frame.iloc[-1] if not recent_frame.empty else pd.Series(dtype="object")
    latest_quote = extract_latest_quote_fields(latest_row)
    series_map = build_series_map(recent_frame)

    meta = build_meta(request, recent_frame, latest_quote)
    current_metrics = extract_current_metrics(latest_row)
    trace_points = build_trace_groups(recent_frame, series_map)
    recent_events = detect_recent_events(recent_frame, series_map)
    return ObservationPayload(
        meta=meta,
        latest_quote=latest_quote,
        current_metrics=current_metrics,
        trace_points=trace_points,
        recent_events=recent_events,
        sections=[],
    )


def build_payload_from_latest_row(request: Any, row: pd.Series) -> ObservationPayload | None:
    """根据最新行情行回补历史后构建 observation payload。"""

    code = resolve_history_lookup_code(request, row)
    if not code:
        return None

    level = normalize_indicator_level(request.output.indicator_level)
    history = fetch_history_for_code(request.spec.module_name, code, level)
    if history is None or history.empty:
        return None

    enriched = enrich_history_frame(history, level)
    payload = build_payload_from_history_frame(request, enriched)
    payload.latest_quote = extract_latest_quote_fields(row)
    if "code" not in payload.meta:
        payload.meta["code"] = code
    return payload


def build_payload_from_single_row(request: Any, row: pd.Series) -> ObservationPayload | None:
    """根据单行结果回补历史后构建 observation payload。"""

    code = resolve_history_lookup_code(request, row)
    if not code:
        return None

    level = normalize_indicator_level(request.output.indicator_level)
    history = fetch_history_for_code(request.spec.module_name, code, level)
    if history is None or history.empty:
        return None

    enriched = enrich_history_frame(history, level)
    payload = build_payload_from_history_frame(request, enriched)
    latest_quote = extract_latest_quote_fields(row)
    payload.latest_quote = latest_quote
    payload.current_metrics = merge_current_metrics(payload.current_metrics, extract_current_metrics(row))
    payload.meta = merge_meta_with_latest_quote(payload.meta, latest_quote)
    payload.meta["code"] = code
    return payload


def build_mapping_payloads_from_rows(
    request: Any,
    frame: pd.DataFrame,
    builder: Any,
) -> dict[str, ObservationPayload]:
    """把多行结果转换为 source -> observation payload 映射。"""

    payloads: dict[str, ObservationPayload] = {}
    for idx, row in frame.iterrows():
        payload = builder(request, row)
        if payload is None:
            continue
        key = resolve_payload_key(payload, row, idx)
        payloads[str(key)] = payload
    return payloads


def resolve_payload_key(payload: ObservationPayload, row: pd.Series, idx: Any) -> str:
    """为多 source observation 结果生成稳定 key。"""

    return str(
        payload.meta.get("code")
        or payload.meta.get("name")
        or find_first_present_value(row, ["行情ID", "代码", "股票代码", "债券代码", "期货代码", "基金代码", "名称"])
        or idx
    )


def resolve_history_lookup_code(request: Any, row: pd.Series) -> str | None:
    """根据命令上下文解析用于历史回补的标的标识。"""

    module_name = request.spec.module_name
    if module_name == "common":
        quote_id = request.kwargs.get("quote_id")
        if quote_id:
            return str(quote_id)
        quote_id_from_row = find_first_present_value(row, ["行情ID"])
        if quote_id_from_row is not None:
            return str(quote_id_from_row)
    if module_name == "futures":
        quote_id = find_first_present_value(row, ["行情ID"])
        if quote_id is not None:
            return str(quote_id)
    return extract_code_from_series(row)


def limit_realtime_observation_frame(request: Any, frame: pd.DataFrame) -> pd.DataFrame:
    """对 realtime-list observation 应用默认处理上限。"""

    if request.output.limit is not None:
        return frame.head(request.output.limit)
    level = normalize_indicator_level(request.output.indicator_level)
    return frame.head(LEVELS[level].realtime_limit)


def merge_current_metrics(base_metrics: dict[str, Any], row_metrics: dict[str, Any]) -> dict[str, Any]:
    """合并历史回补指标与单行结果中的即时指标。"""

    merged = dict(base_metrics)
    merged.update({key: value for key, value in row_metrics.items() if value is not None})
    return merged


def merge_meta_with_latest_quote(meta: dict[str, Any], latest_quote: dict[str, Any]) -> dict[str, Any]:
    """用 latest quote 中可提取的信息补齐 meta。"""

    merged = dict(meta)
    for key in ("name",):
        if latest_quote.get(key) is not None:
            merged[key] = latest_quote[key]
    if latest_quote.get("date") is not None:
        merged["as_of"] = latest_quote["date"]
    return merged


def normalize_trace_window(trace_window: int) -> int:
    """规范 trace window，避免非法值。"""

    if trace_window <= 0:
        return 32
    return trace_window


def build_meta(request: Any, frame: pd.DataFrame, latest_quote: dict[str, Any]) -> dict[str, Any]:
    """构建 observation payload 的元信息。"""

    meta = {
        "module": request.spec.module_name,
        "function": request.spec.function_name,
        "view": "observation",
        "indicator_level": normalize_indicator_level(request.output.indicator_level),
        "trace_window": normalize_trace_window(request.output.trace_window),
        "row_count": int(len(frame)),
    }
    for key in ("code", "name", "date"):
        if key in latest_quote:
            meta[key] = latest_quote[key]
    if "date" in meta:
        meta["as_of"] = meta.pop("date")
    return meta


def build_generic_meta(request: Any, value: Any) -> dict[str, Any]:
    """构建通用 observation payload 的元信息。"""

    meta = {
        "module": request.spec.module_name,
        "function": request.spec.function_name,
        "view": "observation",
        "indicator_level": normalize_indicator_level(request.output.indicator_level),
        "trace_window": normalize_trace_window(request.output.trace_window),
        "result_type": type(value).__name__,
    }
    if isinstance(value, pd.DataFrame):
        meta["row_count"] = int(len(value))
        meta["column_count"] = int(len(value.columns))
    elif isinstance(value, pd.Series):
        meta["row_count"] = 1
        meta["column_count"] = int(len(value.index))
    elif isinstance(value, dict):
        meta["item_count"] = int(len(value))
    elif isinstance(value, (list, tuple, set)):
        meta["item_count"] = int(len(value))
    return meta


def build_generic_sections(value: Any) -> list[ObservationSection]:
    """根据结果类型构建通用 observation sections。"""

    if isinstance(value, pd.DataFrame):
        return [ObservationSection(name="result", rows=normalize_dataframe_rows(value), render_hint="records")]
    if isinstance(value, pd.Series):
        return [ObservationSection(name="result", rows=[normalize_mapping(value.to_dict())], render_hint="kv")]
    if isinstance(value, dict):
        sections: list[ObservationSection] = []
        for key, item in value.items():
            section_name = f"result.{key}"
            if isinstance(item, pd.DataFrame):
                sections.append(
                    ObservationSection(
                        name=section_name,
                        rows=normalize_dataframe_rows(item),
                        render_hint="records",
                    )
                )
                continue
            if isinstance(item, pd.Series):
                sections.append(
                    ObservationSection(
                        name=section_name,
                        rows=[normalize_mapping(item.to_dict())],
                        render_hint="kv",
                    )
                )
                continue
            if isinstance(item, dict):
                sections.append(
                    ObservationSection(
                        name=section_name,
                        rows=[normalize_mapping(item)],
                        render_hint="kv",
                    )
                )
                continue
            if isinstance(item, (list, tuple, set)):
                sections.append(
                    ObservationSection(
                        name=section_name,
                        rows=normalize_sequence_rows(item),
                        render_hint="records",
                    )
                )
                continue
            sections.append(
                ObservationSection(
                    name=section_name,
                    rows=[{"value": normalize_scalar(item)}],
                    render_hint="kv",
                )
            )
        return sections or [ObservationSection(name="result", rows=[], render_hint="records")]
    if isinstance(value, (list, tuple, set)):
        return [ObservationSection(name="result", rows=normalize_sequence_rows(value), render_hint="records")]
    return [ObservationSection(name="result", rows=[{"value": normalize_scalar(value)}], render_hint="kv")]


def normalize_dataframe_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """把 DataFrame 统一转换为 observation section 行。"""

    if frame.empty:
        return []
    records = frame.to_dict(orient="records")
    return [normalize_mapping(record) for record in records]


def normalize_sequence_rows(value: Any) -> list[dict[str, Any]]:
    """把顺序结果统一转换为 observation section 行。"""

    rows: list[dict[str, Any]] = []
    for item in list(value):
        if isinstance(item, dict):
            rows.append(normalize_mapping(item))
        elif hasattr(item, "_asdict"):
            rows.append(normalize_mapping(item._asdict()))
        else:
            rows.append({"value": normalize_scalar(item)})
    return rows


def normalize_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    """把映射结果递归标准化为基础标量。"""

    return {str(key): normalize_scalar(value) for key, value in mapping.items()}


def extract_latest_quote_fields(row: pd.Series) -> dict[str, Any]:
    """从结果行中提取英文 latest quote 字段。"""

    result: dict[str, Any] = {}
    if row.empty:
        return result

    for field_name, candidates in RAW_FIELD_ALIASES.items():
        value = find_first_present_value(row, candidates)
        if value is not None:
            result[field_name] = normalize_scalar(value)
    return result


def extract_current_metrics(row: pd.Series) -> dict[str, Any]:
    """提取当前 bar 的关键指标值。"""

    result: dict[str, Any] = {}
    if row.empty:
        return result

    for field_name in CURRENT_METRIC_FIELDS:
        value = find_first_present_value(row, SERIES_ALIASES.get(field_name, [field_name]))
        if value is not None:
            result[field_name] = normalize_scalar(value)
    return result


def find_first_present_value(row: pd.Series, candidates: Iterable[str]) -> Any | None:
    """从多个候选列名中取第一个非空值。"""

    for candidate in candidates:
        if candidate in row.index and pd.notna(row[candidate]):
            return row[candidate]
    return None


def build_series_map(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """把 DataFrame 中的可用字段整理为英文命名的数值序列。"""

    series_map: dict[str, pd.Series] = {}
    if frame.empty:
        return series_map

    for field_name, candidates in SERIES_ALIASES.items():
        for candidate in candidates:
            if candidate in frame.columns:
                series_map[field_name] = pd.to_numeric(frame[candidate], errors="coerce")
                break
    return series_map


def build_trace_groups(frame: pd.DataFrame, series_map: dict[str, pd.Series]) -> list[ObservationTraceGroup]:
    """根据最近窗口构建 trace group 列表。"""

    trace_groups: list[ObservationTraceGroup] = []
    if frame.empty:
        return trace_groups

    count = len(frame)
    offsets = list(range(-count + 1, 1))
    for group_name, fields in TRACE_GROUPS.items():
        available_fields = [field for field in fields if field in series_map]
        if not available_fields:
            continue
        points: list[dict[str, Any]] = []
        for idx, bar_offset in enumerate(offsets):
            point: dict[str, Any] = {"bar_offset": bar_offset}
            for field_name in available_fields:
                point[field_name] = normalize_scalar(series_map[field_name].iloc[idx])
            points.append(point)
        trace_groups.append(ObservationTraceGroup(name=group_name, points=points))
    return trace_groups


def detect_recent_events(frame: pd.DataFrame, series_map: dict[str, pd.Series]) -> list[ObservationEvent]:
    """识别最近窗口内的客观近期事件。"""

    events: list[ObservationEvent] = []
    if frame.empty or len(frame) < 2:
        return events

    append_cross_events(events, series_map, "ma5", "ma10")
    append_cross_events(events, series_map, "ma10", "ma20")
    append_cross_events(events, series_map, "macd_dif", "macd_dea")
    append_cross_events(events, series_map, "kdj_k", "kdj_d")
    append_cross_events(events, series_map, "ppo", "ppo_signal")
    append_cross_events(events, series_map, "plus_di", "minus_di")

    append_series_cross_threshold_events(events, series_map, "rsi14", 50.0)
    append_series_cross_threshold_events(events, series_map, "cmf20", 0.0)
    append_series_cross_threshold_events(events, series_map, "cci14", 100.0)
    append_series_cross_threshold_events(events, series_map, "cci14", -100.0)
    append_series_cross_threshold_events(events, series_map, "volume_ratio_5", 1.0)

    append_series_cross_events(events, series_map, "close", "ma20")
    append_series_cross_events(events, series_map, "close", "supertrend")

    append_band_touch_events(events, series_map, "close", "boll_upper", "touched_upper_band")
    append_band_touch_events(events, series_map, "close", "boll_lower", "touched_lower_band")
    append_sign_change_events(events, series_map, "supertrend_direction")
    append_consecutive_direction_events(events, series_map, "obv", streak=3)

    events.sort(key=lambda item: item.bars_ago, reverse=True)
    return events


def append_cross_events(events: list[ObservationEvent], series_map: dict[str, pd.Series], left: str, right: str) -> None:
    """检测两条序列之间的 crossing 事件。"""

    if left not in series_map or right not in series_map:
        return

    append_pairwise_events(
        events=events,
        left_name=left,
        right_name=right,
        left_series=series_map[left],
        right_series=series_map[right],
    )


def append_series_cross_events(events: list[ObservationEvent], series_map: dict[str, pd.Series], left: str, right: str) -> None:
    """检测价格或指标与另一条序列的 crossing 事件。"""

    append_cross_events(events, series_map, left, right)


def append_pairwise_events(
    events: list[ObservationEvent],
    left_name: str,
    right_name: str,
    left_series: pd.Series,
    right_series: pd.Series,
) -> None:
    """按窗口遍历并记录 crossing 事件。"""

    for idx in range(1, len(left_series)):
        prev_left = left_series.iloc[idx - 1]
        prev_right = right_series.iloc[idx - 1]
        curr_left = left_series.iloc[idx]
        curr_right = right_series.iloc[idx]
        if not all(pd.notna(value) for value in [prev_left, prev_right, curr_left, curr_right]):
            continue

        bars_ago = idx - len(left_series) + 1
        if prev_left <= prev_right and curr_left > curr_right:
            events.append(
                ObservationEvent(
                    bars_ago=bars_ago,
                    event_key=f"{left_name}_crossed_above_{right_name}",
                    subject_a=left_name,
                    relation="crossed_above",
                    subject_b=right_name,
                    prev_a=float(prev_left),
                    prev_b=float(prev_right),
                    curr_a=float(curr_left),
                    curr_b=float(curr_right),
                    description=f"{left_name} moved from below to above {right_name}",
                )
            )
        elif prev_left >= prev_right and curr_left < curr_right:
            events.append(
                ObservationEvent(
                    bars_ago=bars_ago,
                    event_key=f"{left_name}_crossed_below_{right_name}",
                    subject_a=left_name,
                    relation="crossed_below",
                    subject_b=right_name,
                    prev_a=float(prev_left),
                    prev_b=float(prev_right),
                    curr_a=float(curr_left),
                    curr_b=float(curr_right),
                    description=f"{left_name} moved from above to below {right_name}",
                )
            )


def append_series_cross_threshold_events(
    events: list[ObservationEvent],
    series_map: dict[str, pd.Series],
    field_name: str,
    threshold: float,
) -> None:
    """检测序列穿越固定阈值的事件。"""

    series = series_map.get(field_name)
    if series is None:
        return

    threshold_label = normalize_threshold_label(threshold)
    for idx in range(1, len(series)):
        prev_value = series.iloc[idx - 1]
        curr_value = series.iloc[idx]
        if not all(pd.notna(value) for value in [prev_value, curr_value]):
            continue

        bars_ago = idx - len(series) + 1
        if prev_value <= threshold and curr_value > threshold:
            events.append(
                ObservationEvent(
                    bars_ago=bars_ago,
                    event_key=f"{field_name}_crossed_above_{threshold_label}",
                    subject_a=field_name,
                    relation="crossed_above",
                    subject_b=str(threshold),
                    prev_a=float(prev_value),
                    prev_b=threshold,
                    curr_a=float(curr_value),
                    curr_b=threshold,
                    description=f"{field_name} moved from at-or-below to above {threshold_label}",
                )
            )
        elif prev_value >= threshold and curr_value < threshold:
            events.append(
                ObservationEvent(
                    bars_ago=bars_ago,
                    event_key=f"{field_name}_crossed_below_{threshold_label}",
                    subject_a=field_name,
                    relation="crossed_below",
                    subject_b=str(threshold),
                    prev_a=float(prev_value),
                    prev_b=threshold,
                    curr_a=float(curr_value),
                    curr_b=threshold,
                    description=f"{field_name} moved from at-or-above to below {threshold_label}",
                )
            )


def append_band_touch_events(
    events: list[ObservationEvent],
    series_map: dict[str, pd.Series],
    price_name: str,
    boundary_name: str,
    relation: str,
) -> None:
    """检测价格触碰上下轨的事件。"""

    price_series = series_map.get(price_name)
    boundary_series = series_map.get(boundary_name)
    if price_series is None or boundary_series is None:
        return

    comparator = (lambda price, boundary: price >= boundary) if relation == "touched_upper_band" else (lambda price, boundary: price <= boundary)
    for idx in range(1, len(price_series)):
        prev_price = price_series.iloc[idx - 1]
        prev_boundary = boundary_series.iloc[idx - 1]
        curr_price = price_series.iloc[idx]
        curr_boundary = boundary_series.iloc[idx]
        if not all(pd.notna(value) for value in [prev_price, prev_boundary, curr_price, curr_boundary]):
            continue

        if comparator(curr_price, curr_boundary) and not comparator(prev_price, prev_boundary):
            bars_ago = idx - len(price_series) + 1
            events.append(
                ObservationEvent(
                    bars_ago=bars_ago,
                    event_key=f"{price_name}_{relation}_{boundary_name}",
                    subject_a=price_name,
                    relation=relation,
                    subject_b=boundary_name,
                    prev_a=float(prev_price),
                    prev_b=float(prev_boundary),
                    curr_a=float(curr_price),
                    curr_b=float(curr_boundary),
                    description=f"{price_name} {relation.replace('_', ' ')} {boundary_name}",
                )
            )


def append_sign_change_events(events: list[ObservationEvent], series_map: dict[str, pd.Series], field_name: str) -> None:
    """检测正负号切换或方向切换事件。"""

    series = series_map.get(field_name)
    if series is None:
        return

    for idx in range(1, len(series)):
        prev_value = series.iloc[idx - 1]
        curr_value = series.iloc[idx]
        if not all(pd.notna(value) for value in [prev_value, curr_value]):
            continue
        if prev_value == curr_value:
            continue

        if (prev_value < 0 <= curr_value) or (prev_value <= 0 < curr_value):
            relation = "changed_positive"
            description = f"{field_name} changed from non-positive to positive"
        elif (prev_value > 0 >= curr_value) or (prev_value >= 0 > curr_value):
            relation = "changed_negative"
            description = f"{field_name} changed from non-negative to negative"
        else:
            relation = "changed_direction"
            description = f"{field_name} changed direction"

        bars_ago = idx - len(series) + 1
        events.append(
            ObservationEvent(
                bars_ago=bars_ago,
                event_key=f"{field_name}_{relation}",
                subject_a=field_name,
                relation=relation,
                prev_a=float(prev_value),
                curr_a=float(curr_value),
                description=description,
            )
        )


def append_consecutive_direction_events(
    events: list[ObservationEvent],
    series_map: dict[str, pd.Series],
    field_name: str,
    streak: int,
) -> None:
    """检测连续上涨或连续下跌事件。"""

    series = series_map.get(field_name)
    if series is None or len(series) <= streak:
        return

    diffs = series.diff()
    for idx in range(streak, len(series)):
        window = diffs.iloc[idx - streak + 1 : idx + 1]
        if window.isna().any():
            continue

        bars_ago = idx - len(series) + 1
        if (window > 0).all():
            events.append(
                ObservationEvent(
                    bars_ago=bars_ago,
                    event_key=f"{field_name}_rose_{streak}_bars",
                    subject_a=field_name,
                    relation=f"rose_{streak}_bars",
                    curr_a=float(series.iloc[idx]),
                    description=f"{field_name} rose for {streak} consecutive bars",
                )
            )
        elif (window < 0).all():
            events.append(
                ObservationEvent(
                    bars_ago=bars_ago,
                    event_key=f"{field_name}_fell_{streak}_bars",
                    subject_a=field_name,
                    relation=f"fell_{streak}_bars",
                    curr_a=float(series.iloc[idx]),
                    description=f"{field_name} fell for {streak} consecutive bars",
                )
            )


def normalize_threshold_label(threshold: float) -> str:
    """把阈值转成稳定的英文标识片段。"""

    if float(threshold).is_integer():
        return str(int(threshold))
    return str(threshold).replace(".", "_")


def normalize_scalar(value: Any) -> Any:
    """把标量值转成适合 observation payload 的基础类型。"""

    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float, str, bool)):
        return value
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return str(value)
