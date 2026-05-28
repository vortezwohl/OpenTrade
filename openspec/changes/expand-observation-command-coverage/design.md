## Context

当前 observation 实现只识别两类命令：

- `HISTORY_COMMANDS`
- `LATEST_COMMANDS`

分派入口在 `build_observation_output()`，仅根据命令键判断是否走历史 observation 组装或最新行情 observation 组装。与此同时，增强层实际上已经具备更宽的适配面：

- `HISTORY_COMMANDS`
- `SINGLE_ROW_COMMANDS`
- `LATEST_COMMANDS`
- `REALTIME_LIST_COMMANDS`

这说明 observation 当前的限制主要不是技术指标能力不足，而是 observation 还没有把 single-row 和 realtime-list 两类输入形状纳入正式分派和契约设计。

第二批扩展范围可自然拆成三条路线：

1. 多标的历史：`fund get-quote-history-multi`
2. 单标的单行：`stock get-quote-snapshot`、`stock/common/bond get-base-info`
3. 多标的实时列表：`stock/bond/futures get-realtime-quotes`、`common get-realtime-quotes-by-fs`、`fund get-realtime-increase-rate`

其中第一条路线基本复用现有 history payload 与 rendering，第二条路线需要新增 single-row assembler，第三条路线需要解决多 source observation 的 grouped table 与 long-form 导出契约。

## Goals / Non-Goals

**Goals:**

- 让 observation 命令覆盖范围扩展到 second-batch 候选命令，而不只限于第一批 history/latest。
- 为 single-row 结果建立稳定的 observation assembler。
- 为 multi-source realtime list 结果建立稳定的 observation assembler 与多格式输出契约。
- 明确第二批命令的优先级和默认约束，尤其是 realtime list 的 `limit`、性能和输出长度控制。
- 保持 observation 输出仍然只陈列事实，不引入主观 bullish/bearish 结论。

**Non-Goals:**

- 不把 observation 直接扩到成交明细、资金流明细、榜单、持仓、报告下载等非行情序列型命令。
- 不把第二批命令默认切换为 observation 输出。
- 不在这一轮里重做指标家族本身，只扩 observation 适配面。
- 不在这一轮里引入新的 UI 风格或第三方终端组件。

## Decisions

### 决策一：按结果形状而不是按命令名散乱扩展 observation

第二批扩展应把 observation 分派从当前两类：

- history
- latest

扩展为四类：

- history
- multi-history
- single-row
- realtime-list

原因：

- 未来新增命令时，更容易复用“形状分派”而不是继续堆命令特判。
- `fund get-quote-history-multi` 与 `get-quote-history` 的差异主要是“单 DataFrame vs dict[str, DataFrame]”。
- `get-quote-snapshot` 与 `get-base-info` 的共同点是“单行且能提 code，可回补历史”。
- 各类 realtime quotes 的共同点是“多行、每行可尝试回补历史、输出需按 source 分组”。

备选方案：

- 继续只按命令名手工 if/else 扩展。放弃，因为复杂度会快速失控。

### 决策二：`fund get-quote-history-multi` 作为第二批第一优先级

该命令的 observation 扩展应最先落地。

原因：

- 上游返回 `dict[str, DataFrame]`；
- 当前 `build_history_observation_output()` 已支持这种结构；
- 当前渲染层也已支持 `dict[str, ObservationPayload]` 的 table/json/csv/tsv 路径；
- 风险主要只剩命令接入和回归测试。

备选方案：

- 优先做 realtime list。放弃，因为多 source 输出契约更复杂。

### 决策三：为 single-row 引入“弱 latest_quote”策略

对 `stock get-quote-snapshot`、`stock/common/bond get-base-info` 这类单行结果，observation 应允许 `latest_quote` 区块不完整，但仍输出：

- `meta`
- `latest_quote`（尽量提取）
- `current_metrics`
- `trace_points`
- `recent_events`

原因：

- `get-quote-snapshot` 的行情字段较完整，适合几乎完整的 observation；
- `get-base-info` 天然缺少时间、最新价、成交量等字段，但仍可通过 code 回补历史并输出当前指标与近期事件；
- 如果要求 latest_quote 必须完整，就会把这些高价值命令排除掉。

备选方案：

- 要求 single-row 命令必须具备完整 latest_quote 才能支持。放弃，因为会错失大量低成本扩展机会。

### 决策四：realtime-list observation 必须采用多 source 契约

对 realtime list，不应尝试把全部标的压成单个 observation payload，而应输出 `dict[str, ObservationPayload]` 或等价多 source 结构。

原因：

- 每个标的都有独立的 trace 与 recent events；
- 单 payload 无法自然容纳多个标的的完整 observation；
- 当前 long-form 导出已经有 `__source__` 设计，可以自然支撑。

备选方案：

- 把所有标的压成一个超大 payload。放弃，因为 schema 会失真。

### 决策五：realtime-list observation 需要默认限流约束

realtime-list 命令扩展 observation 时，必须对“默认处理多少行”有显式约束。

建议策略：

- 若用户未指定 `--limit`，则按 enrichment 当前的 realtime limit 或更保守的 observation limit 执行；
- table 输出按 source 分块；
- csv/tsv 始终输出 long-form。

原因：

- 每行都要历史回补，代价高；
- 每个标的都会生成 trace + events，表格会急剧膨胀；
- 不限流会导致性能和可读性同时失控。

备选方案：

- 让 observation 无条件处理整个 realtime list。放弃，因为风险过高。

### 决策六：`common get-realtime-quotes-by-fs` 与 `fund get-realtime-increase-rate` 后于 stock/bond/futures realtime

这两个命令应属于 second-batch 中的后序项。

原因：

- `common get-realtime-quotes-by-fs` 的市场异构性最强，可能混入不适合同一历史回补路径的 source；
- `fund get-realtime-increase-rate` 的原始字段缺少 OHLCV，只能形成“弱 latest_quote + 强历史回补”的 observation；
- 相比之下，stock/bond/futures realtime 的行情字段更完整，风险更低。

备选方案：

- 按注册顺序扩展全部 realtime list。放弃，因为收益/风险比不均衡。

## Risks / Trade-offs

- [风险] single-row base_info 的 latest_quote 信息不完整，用户可能误以为它等价于 latest quote。 → 缓解：文档中明确这是“弱 latest_quote”命令族，不保证区块完整度。
- [风险] realtime-list observation 的 table 输出会非常长。 → 缓解：默认限流，并要求 grouped table 分块输出。
- [风险] `common get-realtime-quotes-by-fs` 的市场异构性可能导致部分 code 回补历史失败。 → 缓解：首批 realtime-list 优先 stock/bond/futures，common 延后。
- [风险] `fund get-realtime-increase-rate` 虽然可接 observation，但原始字段与标准 quote 语义不同。 → 缓解：明确其 latest_quote 为估算视图，不与标准实时行情等同。
- [风险] 第二批覆盖会引入更多命令特判。 → 缓解：按结果形状建立统一 assembler，而不是按命令逐条散写逻辑。

## Migration Plan

1. 先扩展 multi-history：`fund get-quote-history-multi`。
2. 再扩展 single-row：`stock get-quote-snapshot`、`stock/common/bond get-base-info`。
3. 再扩展第一优先级 realtime-list：`stock/bond/futures get-realtime-quotes`。
4. 最后评估并扩展第二优先级 realtime-list：`fund get-realtime-increase-rate`、`common get-realtime-quotes-by-fs`。
5. 每一阶段都补 table/json/csv/tsv 回归测试和 CLI 命令级测试。
6. 保持 `--view raw` 为默认回退路径；如果 observation 扩展不稳定，用户移除 `--view observation` 即可回退。

## Open Questions

- realtime-list observation 是否需要独立于 enrichment 的更保守默认 `observation_limit`？
- single-row `base_info` 是否需要在 meta 中额外标明 `quote_completeness`，还是仅靠文档说明？
- `common get-realtime-quotes-by-fs` 是否应限制在部分 `fs` 场景先启用，而不是全量启用？
- `fund get-realtime-increase-rate` 是否需要单独的 latest_quote 字段映射扩展，例如把“估算涨跌幅”映射为专门字段，而不是混入标准 quote 语义？
