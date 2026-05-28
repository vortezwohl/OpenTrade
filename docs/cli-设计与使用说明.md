# efinance-cli 设计与使用说明

## 1. 项目定位

`efinance-cli` 是一个面向 Agent 的金融数据命令行终端。

它的目标不是把第三方 `efinance` 包重新抽象成“更易用”的人类命令，而是：

- 尽量完整暴露 `efinance` 已有公开能力；
- 为所有查询结果提供统一的表格输出；
- 为适合实时观察的命令提供循环刷新能力；
- 让 Agent 可以用稳定、可预测的方式把 Python API 映射为 CLI 命令。

命令入口有两个：

- `efinance`
- `efi`

两者行为完全一致。

## 2. 命令组织方式

命令树直接对应 `efinance` 的模块结构：

```text
efinance
├─ search
├─ watch
├─ stock
├─ fund
├─ bond
├─ futures
├─ common
└─ utils
```

模块下的函数命令名采用“函数名下划线转中划线”的规则。

例如：

- `efinance.stock.get_quote_history` 对应 `efinance stock get-quote-history`
- `efinance.fund.get_realtime_increase_rate` 对应 `efinance fund get-realtime-increase-rate`
- `efinance.common.get_realtime_quotes_by_fs` 对应 `efinance common get-realtime-quotes-by-fs`

这种做法的优点是：

- Agent 可以直接从源码/API 名称反推命令；
- 新增公开函数时，命令树天然可扩展；
- 不需要维护一套与第三方包脱节的“人工命名层”。

## 3. 输出约定

所有命令默认使用表格输出，尽量模拟数据库控制台查表体验。

通用输出参数：

- `--format table|json|csv|tsv`
- `--full`
- `--transpose`
- `--no-index`
- `--limit N`
- `--output PATH`
- `--encoding utf-8`
- `--indicator-level basic|advanced|full`

说明：

- `table`：默认控制台表格输出
- `json`：适合 Agent 继续做结构化处理
- `csv/tsv`：适合保存或后续导入其他工具
- `--full`：不压缩列和长文本
- `--transpose`：适合单行结果转置后查看
- `--limit`：只打印前 N 行
- `--indicator-level`：技术指标丰富度等级，默认 `advanced`

### 3.1 结构化 observation 视图

当前首批支持以下命令切换到结构化 observation 输出：

- `common get-quote-history`
- `common get-latest-quote`
- `stock get-quote-history`
- `stock get-latest-quote`
- `bond get-quote-history`
- `futures get-quote-history`
- `fund get-quote-history`
- `fund get-quote-history-multi`
- `stock get-quote-snapshot`
- `stock get-base-info`
- `bond get-base-info`
- `common get-base-info`
- `stock get-realtime-quotes`
- `bond get-realtime-quotes`
- `futures get-realtime-quotes`

当前仍未纳入本批支持范围：

- `fund get-realtime-increase-rate`
- `common get-realtime-quotes-by-fs`

新增运行时参数：

- `--view raw|observation`
- `--trace-window N`

说明：

- `raw`：保持现有原始/增强后结果渲染路径；
- `observation`：输出结构化观察结果；
- `trace_window` 默认值为 `32`；
- `trace_window` 只控制 observation 展示窗口，不改变指标计算所需历史窗口。

### 3.2 observation 输出契约

observation 模式的核心 section 固定为：

- `meta`
- `latest_quote`
- `current_metrics`
- `trace_points`
- `recent_events`

其中：

- `trace_points` 始终位于 `recent_events` 之前；
- 默认只陈列观测事实，不输出 bullish、bearish、confidence、regime 一类预判性总结；
- 新路径中的字段名、section 名和事件描述统一使用英文。
- 多 source observation 会按 source 分组输出，而不是压成单个 observation payload。

### 3.3 table / json / csv / tsv 形态差异

- `table`：使用统一 ASCII boxed section 风格，除 `trace_points` 外优先纵向排列；
- `json`：直接输出结构化 observation payload；
- `csv` / `tsv`：输出 long-form 长表，和 table/json 保持等价信息量。

对于多 source observation：

- `table` 会按 `source.<key>` 分组，再在组内输出该 source 的 observation sections；
- `json` 会保留 `source -> payload` 的映射结构；
- `csv` / `tsv` 会在 long-form 行中保留 `__source__`。

`csv` / `tsv` 长表的关键列包括：

- `__source__`
- `section`
- `item_type`
- `item_id`
- `group`
- `bar_offset`
- `event_index`
- `event_key`
- `relation`
- `bars_ago`
- `field`
- `value`

### 3.4 boxed table 风格约束

observation 的 `table` 输出不再依赖 `DataFrame.to_string()` 直接宽表展示，而是使用独立 boxed renderer。约束如下：

- 所有 section 使用统一 ASCII 外框；
- 事件列表使用“一个总外框内列出多条事件”的形式；
- `trace_points` 允许横向浮点数块，但不用字符图；
- 超长内容会先折行，再按折行后最长行动态计算宽度；
- 任意可见内容都不允许穿出右边框。

### 3.5 上线与回退说明

当前 observation 模式采用增量接入策略：

- 仅对首批支持命令生效；
- 默认使用 `observation` 视图；如需既有宽表结果，可显式传入 `--view raw`；
- 用户显式传入 `--view observation` 时才进入新路径。

single-row 命令说明：

- `stock get-quote-snapshot` 的 `latest_quote` 较完整，接近标准最新行情 observation；
- `stock get-base-info`、`bond get-base-info`、`common get-base-info` 属于“弱 latest_quote”命令；
- 这类命令的核心价值在于通过 code 回补历史后输出 `current_metrics`、`trace_points` 与 `recent_events`，而不是提供完整即时行情字段。

realtime-list 命令说明：

- `stock get-realtime-quotes`、`bond get-realtime-quotes`、`futures get-realtime-quotes` 已支持 observation；
- 这类命令会为每个可识别标的生成独立 observation；
- 若用户显式传入 `--limit`，observation 只处理前 N 行；
- 若用户未传 `--limit`，observation 默认按当前 `indicator-level` 对应的 realtime limit 处理，避免无上限扩张输出和历史回补成本。

兼容性预期：

- 原有 `table / json / csv / tsv` 在 `raw` 视图下保持既有行为；
- observation 视图中的 CLI labels 与字段名统一切换为英文；
- observation 的 `csv / tsv` 契约为 long-form，不再保证“一行一个标的”的宽表形态。

回退策略：

- 若调用方尚未适配 observation 结构，可直接移除 `--view observation`；
- 若只想保留增强指标而不使用结构化事件与 trace，可继续使用现有 raw/enriched 路径；
- 结构化 observation 的支持命令范围之外，系统会自动回退为既有结果渲染。

第二批扩展顺序说明：

1. 已先接入 `fund get-quote-history-multi`
2. 已接入 single-row：`stock get-quote-snapshot`、`stock/common/bond get-base-info`
3. 已接入第一优先级 realtime-list：`stock/bond/futures get-realtime-quotes`
4. `fund get-realtime-increase-rate` 与 `common get-realtime-quotes-by-fs` 仍保留为后续评估项，原因是 latest quote 语义更弱或市场异构性更高

## 4. 刷新模式

### 4.1 命令内刷新

几乎所有查询型命令都支持：

```bash
efinance stock get-realtime-quotes --watch --interval 2
```

通用刷新参数：

- `--watch`
- `--interval FLOAT`
- `--count INT`
- `--clear/--no-clear`

### 4.2 顶层 watch 包装

也可以直接包裹任意子命令：

```bash
efinance watch --interval 2 stock get-realtime-quotes
efinance watch --interval 5 fund get-realtime-increase-rate 161725 005827
```

这个模式更接近 `top` 的工作方式，适合统一刷新任意命令。

## 5. 顶层命令

### 5.1 `search`

用于按关键字搜索证券候选项。

示例：

```bash
efinance search 贵州茅台
efinance search PG --count 10 --format json
efinance search 腾讯 --market Hongkong
```

### 5.2 `watch`

用于为任意子命令开启循环刷新。

示例：

```bash
efinance watch --interval 2 stock get-realtime-quotes
```

## 6. 各模块主要命令

### 6.1 股票 `stock`

- `get-base-info`
- `get-realtime-quotes`
- `get-latest-quote`
- `get-quote-snapshot`
- `get-quote-history`
- `get-deal-detail`
- `get-history-bill`
- `get-today-bill`
- `get-top10-stock-holder-info`
- `get-all-report-dates`
- `get-all-company-performance`
- `get-latest-holder-number`
- `get-daily-billboard`
- `get-members`
- `get-latest-ipo-info`
- `get-belong-board`

示例：

```bash
efinance stock get-base-info 600519
efinance stock get-quote-history 600519 --beg 20250101 --end 20250501 --full
efinance stock get-realtime-quotes --fs ETF --limit 20
```

### 6.2 基金 `fund`

- `get-fund-codes`
- `get-base-info`
- `get-quote-history`
- `get-quote-history-multi`
- `get-realtime-increase-rate`
- `get-invest-position`
- `get-types-percentage`
- `get-industry-distribution`
- `get-period-change`
- `get-public-dates`
- `get-fund-manager`
- `get-pdf-reports`

示例：

```bash
efinance fund get-base-info 161725
efinance fund get-realtime-increase-rate 161725 005827 --watch --interval 10
efinance fund get-pdf-reports 161725 --save-dir reports
```

### 6.3 债券 `bond`

- `get-all-base-info`
- `get-base-info`
- `get-realtime-quotes`
- `get-quote-history`
- `get-history-bill`
- `get-today-bill`
- `get-deal-detail`

### 6.4 期货 `futures`

- `get-futures-base-info`
- `get-realtime-quotes`
- `get-quote-history`
- `get-deal-detail`

说明：

期货历史 K 线命令通常直接接收 `quote_id`。

### 6.5 通用 `common`

- `get-base-info`
- `get-realtime-quotes-by-fs`
- `get-latest-quote`
- `get-quote-history`
- `get-history-bill`
- `get-today-bill`
- `get-deal-detail`

这组命令更贴近底层，适合 Agent 在已知 `quote_id` 或 `fs` 分类串时直接访问。

### 6.6 工具 `utils`

- `search-quote`
- `search-quote-locally`
- `get-quote-id`
- `add-market`

## 7. 面向 Agent 的使用建议

### 7.1 优先使用稳定命令链

推荐链路：

1. `search`
2. `utils get-quote-id`
3. `stock/common/futures ...`

这样可以减少由于关键字歧义带来的误查。

### 7.2 查询前接受外部数据源可能失败

`efinance` 依赖外部数据源，实时查询可能出现：

- 连接断开
- 限流
- 临时空结果

因此建议 Agent：

- 对失败命令做重试；
- 在实时刷新时设置合理间隔；
- 对下载类命令和高频查询命令分开处理。

## 8. 当前实现边界

当前版本优先完成：

- 模块命令树自动暴露
- 统一输出层
- 循环刷新
- 中文文档

未额外实现：

- 更智能的参数别名系统
- 更复杂的表格宽度自适应
- 对外部网络错误的统一重试封装
- 更细粒度的命令语义别名

这些能力后续可以继续补强，但不影响当前版本作为面向 Agent 的全量 CLI 骨架使用。
