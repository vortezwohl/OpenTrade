## ADDED Requirements

### Requirement: 第二批 observation 扩展必须遵循分阶段优先级
系统 SHALL 以分阶段方式扩展第二批 observation 命令，而不是无差别同时覆盖全部候选命令。

#### Scenario: Multi-history 优先于 realtime-list
- **WHEN** 系统规划第二批 observation 扩展实现顺序
- **THEN** `fund get-quote-history-multi` SHALL 先于 realtime-list 命令接入

#### Scenario: stock/bond/futures realtime 优先于 common/fund 特殊 realtime
- **WHEN** 系统规划 realtime-list observation 扩展顺序
- **THEN** `stock get-realtime-quotes`、`bond get-realtime-quotes`、`futures get-realtime-quotes` SHALL 先于 `common get-realtime-quotes-by-fs` 与 `fund get-realtime-increase-rate`

### Requirement: 弱 latest_quote 命令需要明确语义边界
系统 SHALL 为 single-row base_info 类命令记录 latest_quote 不完整的语义边界。

#### Scenario: 文档中说明弱 latest_quote
- **WHEN** 系统把 `stock get-base-info`、`bond get-base-info` 或 `common get-base-info` 纳入 observation 支持范围
- **THEN** 文档 SHALL 明确这些命令的 `latest_quote` 可能不完整，且 observation 价值主要来自历史回补后的指标与近期事件
