## ADDED Requirements

### Requirement: Multi-Source observation table 采用 source 分组布局
系统 SHALL 在 table 模式下把多 source observation 结果按 source 分组渲染，而不是输出无法区分边界的单块文本。

#### Scenario: 多 source table 输出保留 source 边界
- **WHEN** 用户以 table 格式渲染多 source observation 结果
- **THEN** 系统 SHALL 为每个 source 提供明确的分组边界，并在组内输出该 source 的 boxed observation section

### Requirement: Multi-Source observation JSON 与 long-form 导出保留 source 标识
系统 SHALL 在 json/csv/tsv 下保留 source 标识，确保多 source observation 可被程序化消费。

#### Scenario: json 输出保留 source -> payload 映射
- **WHEN** 用户以 json 格式渲染多 source observation 结果
- **THEN** 系统 SHALL 输出 source 到 observation payload 的稳定映射结构

#### Scenario: csv/tsv 输出保留 `__source__`
- **WHEN** 用户以 csv 或 tsv 格式渲染多 source observation 结果
- **THEN** 系统 SHALL 在 long-form 行中保留 `__source__` 字段，以标识该行属于哪个 observation source

### Requirement: Multi-Source observation 与单 source observation 保持等价信息量
系统 SHALL 让多 source observation 的每个 source 都保有与单 source observation 相同的信息密度。

#### Scenario: 单个 source 不因 grouped 输出而丢失 section
- **WHEN** 系统渲染多 source observation 结果中的某个 source
- **THEN** 该 source SHALL 仍包含 `meta`、`latest_quote`、`current_metrics`、`trace_points` 和 `recent_events` 中适用的 section
