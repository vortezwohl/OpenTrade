## ADDED Requirements

### Requirement: Multi-History 命令支持结构化 observation
系统 SHALL 为多标的历史行情命令提供结构化 observation 输出模式，并对每个 source 产出独立 observation payload。

#### Scenario: `fund get-quote-history-multi` 输出多 source observation
- **WHEN** 用户对 `fund get-quote-history-multi` 请求 observation 输出
- **THEN** 系统 SHALL 为每个基金代码输出独立的 observation payload，而不是把多标的历史压缩为单个 payload

### Requirement: Single-Row 命令支持结构化 observation
系统 SHALL 为可回补历史的 single-row 命令提供结构化 observation 输出模式。

#### Scenario: `stock get-quote-snapshot` 输出 observation
- **WHEN** 用户对 `stock get-quote-snapshot` 请求 observation 输出
- **THEN** 系统 SHALL 输出 `meta`、`latest_quote`、`current_metrics`、`trace_points` 和 `recent_events`

#### Scenario: `base_info` 类命令输出弱 latest_quote
- **WHEN** 用户对 `stock get-base-info`、`bond get-base-info` 或 `common get-base-info` 请求 observation 输出
- **THEN** 系统 SHALL 允许 `latest_quote` 仅包含可提取字段，同时仍输出回补历史后的 `current_metrics`、`trace_points` 和 `recent_events`

### Requirement: Realtime-List 命令支持多 source observation
系统 SHALL 为可回补历史的 realtime-list 命令提供多 source observation 输出模式。

#### Scenario: 实时列表命令输出多标的 observation
- **WHEN** 用户对支持的 realtime-list 命令请求 observation 输出
- **THEN** 系统 SHALL 为每一行可识别 code 的结果输出独立 observation payload，并保留 source 标识

#### Scenario: realtime-list observation 受默认处理上限约束
- **WHEN** 用户未为支持的 realtime-list observation 请求显式指定 `limit`
- **THEN** 系统 SHALL 使用预定义的 observation 处理上限，而 SHALL NOT 无上限处理整个实时列表
