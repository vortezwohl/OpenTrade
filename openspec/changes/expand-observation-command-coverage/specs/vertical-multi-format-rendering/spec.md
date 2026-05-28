## MODIFIED Requirements

### Requirement: 各输出格式必须具备等价信息量
系统 SHALL 在支持的命令上，通过 `table`、`json`、`csv`、`tsv` 暴露等价的结构化观察信息。

#### Scenario: JSON 与 table 拥有相同 observation section
- **WHEN** 用户对同一结构化观察请求分别使用 `json` 和 `table` 输出
- **THEN** 两种输出 SHALL 包含等价的 observation section，差异仅体现在展示形式

#### Scenario: CSV 与 TSV 保留完整 observation 信息
- **WHEN** 用户对同一结构化观察请求使用 `csv` 或 `tsv` 输出
- **THEN** 导出结果 SHALL 通过规范化长表表示保留相同 observation 信息

### Requirement: Table 渲染采用统一 boxed section 风格
系统 SHALL 使用统一的 ASCII boxed section 风格渲染结构化观察输出，而不是输出单个横向宽表。

#### Scenario: 所有 section 使用统一外框风格
- **WHEN** 用户以 `table` 格式渲染结构化观察输出
- **THEN** 渲染器 SHALL 使用统一的 ASCII 矩形外框风格渲染各个 section

#### Scenario: 除 trace 外其余内容优先纵向排列
- **WHEN** 渲染器输出 `meta`、`latest_quote`、`current_metrics` 与 `recent_events`
- **THEN** 这些 section SHALL 以内聚的纵向条目方式呈现，而不是展开成宽横表

### Requirement: Trace points 以 boxed 横向浮点数块展示
系统 SHALL 在 `table` 输出中把 `trace_points` 渲染为 boxed 横向数值块，并且只使用浮点数值，不使用字符图。

#### Scenario: Trace block 横向展示最近连续数值
- **WHEN** 渲染器输出 `trace_points`
- **THEN** 系统 SHALL 使用一个或多个 boxed block 横向展示最近连续 bar 的浮点数值

#### Scenario: Trace block 不使用字符图
- **WHEN** 渲染器输出 `trace_points`
- **THEN** 系统 SHALL NOT 使用 `....---====`、sparkline 或其他字符型轨迹图代替浮点数序列

### Requirement: Recent events 以单外框多事件形式展示
系统 SHALL 在 `table` 输出中把 `recent_events` 渲染为单个总外框，并在框内列出多条事件。

#### Scenario: Recent events 不是一事件一外框
- **WHEN** 渲染器输出多个 recent event
- **THEN** 系统 SHALL 使用一个总外框包围整个 recent event 列表，而 SHALL NOT 为每个事件单独绘制一个完整外框

### Requirement: Boxed 渲染必须保证内容不会穿墙
系统 SHALL 先对超长内容执行折行，再根据折行后的内容动态计算最终外框宽度，并保证任何可见行都不会超出边框。

#### Scenario: 超长 description 被先折行再绘制外框
- **WHEN** section 中存在超长 description、event key 或其他长字符串
- **THEN** 系统 SHALL 先对内容进行折行，再根据折行后的最长行计算外框宽度

#### Scenario: 任意可见内容不会顶出右边框
- **WHEN** 渲染器输出 boxed section
- **THEN** 任意一行实际显示内容的长度 SHALL NOT 超过该 section 的内部宽度

### Requirement: 结构化观察 CLI 输出语言统一为英文
系统 SHALL 在新的结构化观察输出路径中统一使用英文 labels、section names、serialized keys、event relations 和 factual descriptions。

#### Scenario: Table labels 为英文
- **WHEN** 结构化观察输出以 `table` 渲染
- **THEN** section 名、字段名和事件描述 SHALL 使用英文

#### Scenario: Serialized keys 为英文
- **WHEN** 结构化观察输出以 `json`、`csv` 或 `tsv` 渲染
- **THEN** 顶层 key、字段名和长表列名 SHALL 使用英文

### Requirement: CSV 与 TSV 采用纵向归一化长表
系统 SHALL 将结构化观察输出序列化为纵向归一化长表，而不是尝试保留横向 cross-tab 形态。

#### Scenario: Trace points 在 CSV 中输出为长表行
- **WHEN** 结构化观察输出以 `csv` 渲染
- **THEN** trace points SHALL 以标识 section、item type、item id、trace group、bar offset、field、value 的长表行形式输出

## ADDED Requirements

### Requirement: Multi-Source observation table 保留 source 分组
系统 SHALL 在 table 模式下为多 source observation 结果保留明确的 source 分组边界。

#### Scenario: grouped table 渲染多个 source observation
- **WHEN** 用户以 table 格式渲染多 source observation 结果
- **THEN** 系统 SHALL 先标识 source，再在该 source 组内输出其 boxed observation section

### Requirement: Multi-Source observation CSV / TSV 保留 source 列
系统 SHALL 在多 source observation 的 long-form 导出中保留 source 列。

#### Scenario: long-form 行保留 `__source__`
- **WHEN** 多 source observation 以 csv 或 tsv 导出
- **THEN** 每一行 SHALL 包含 `__source__` 字段，以标识所属 observation source
