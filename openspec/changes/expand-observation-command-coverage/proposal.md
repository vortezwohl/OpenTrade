## Why

第一批 observation 已经覆盖 `get-quote-history` 与 `get-latest-quote`，但当前命令面里仍有多类与行情观察高度相关的命令没有接入，包括多标的历史、单标的快照/基础信息，以及实时列表类命令。现在继续推进的原因是：增强层已经具备这些命令所需的历史回补和指标补齐能力，剩余问题主要集中在 observation 分派策略、payload 组装和多标的输出契约，属于顺势扩展的窗口期。

如果不在这一阶段把支持范围继续拉开，CLI 会形成“同样能补指标、但只有少数命令能看 observation”的割裂体验。尤其对 agent 和批量分析场景而言，`fund get-quote-history-multi`、`stock get-quote-snapshot`、`stock get-realtime-quotes` 这类命令的观察视图价值很高，应该尽快形成第二批覆盖计划。

## What Changes

- 扩展 observation 命令覆盖范围，从当前的 history/latest 两类，扩展到多标的历史、单标的静态/快照、以及多标的实时列表三类结果形状。
- 把 `fund get-quote-history-multi` 纳入 observation 支持范围，复用现有 `dict[str, DataFrame] -> dict[str, ObservationPayload]` 组装和多标的渲染路径。
- 为 `stock get-quote-snapshot`、`stock get-base-info`、`bond get-base-info`、`common get-base-info` 设计 single-row observation 组装路径，在不引入主观判断的前提下输出最近窗口、当前指标与近期事件。
- 为 `stock get-realtime-quotes`、`bond get-realtime-quotes`、`futures get-realtime-quotes`、`common get-realtime-quotes-by-fs`、`fund get-realtime-increase-rate` 设计 realtime-list observation 组装与导出契约。
- 明确多标的 observation 的 table/json/csv/tsv 输出策略，包括 source 分组、默认限流、long-form 契约与 table 分块形式。
- 明确哪些命令虽然技术上可接 observation，但在语义上只能产出“弱 latest_quote”，并据此排序实施优先级。
- 为第二批命令覆盖补充回归测试、文档说明和上线/回退策略。

## Capabilities

### New Capabilities
- `observation-command-expansion`: 为多标的历史、single-row 和 realtime-list 命令扩展 observation 覆盖范围，并定义对应的 payload 组装契约。
- `multi-source-observation-rendering`: 为多 source observation 结果定义统一的 table/json/csv/tsv 表达方式，覆盖 grouped table 与 long-form 导出。
- `observation-command-prioritization`: 明确第二批命令扩展的优先级、默认约束和回退行为，避免无边界扩张。

### Modified Capabilities
- `structured-signal-output`: 将“支持的结构化 observation 输出命令”从第一批 history/latest 扩展到 single-row、multi-history 与 realtime-list。
- `vertical-multi-format-rendering`: 扩展多 source observation 结果在 table/json/csv/tsv 下的渲染约束，尤其是 grouped table 与 long-form 导出。

## Impact

- 受影响代码包括：
  - `efinance_cli/observation.py`
  - `efinance_cli/enrichment/service.py`
  - `efinance_cli/rendering.py`
  - `efinance_cli/commands.py`
  - `efinance_cli/models.py`
  - 相关 observation / CLI 回归测试
- 会影响 observation 模式下支持命令的分派集合，以及多 source 结果在 `table/json/csv/tsv` 下的契约。
- 不需要新增第三方依赖，但会扩大 observation 的适用面，并引入新的 single-row 与 realtime-list 组装分支。
