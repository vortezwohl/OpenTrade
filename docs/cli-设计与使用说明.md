# efinance-cli 设计与使用说明

## 1. 项目定位

`efinance-cli` 是一个面向人类用户与 Agent 的金融数据命令行工具。

当前版本的核心设计目标有两条：

1. 参数语义化  
   不再让 CLI 用户直接记忆底层 Python API 的缩写和命名习惯。

2. 命令自然化  
   不再把上游函数名简单改成短横线，而是按“任务名”组织命令树。

因此，CLI 的目标不是做一个“API 浏览器”，而是做一套：

- 易猜
- 易记
- 低歧义
- 可扩展

的任务导向命令体系。

---

## 2. 顶层命令树

当前用户可见的顶层入口如下：

```text
efinance
├─ search
├─ watch
├─ stock
├─ fund
├─ bond
├─ futures
├─ quote
├─ market
└─ resolve
```

说明：

- `search`：按关键字搜索证券；
- `watch`：为任意子命令开启循环刷新；
- `stock` / `fund` / `bond` / `futures`：面向普通用户的业务域命令；
- `quote`：高级通用入口，适合已知 `quote_id` 的场景；
- `market`：市场级扫描与市场扩展；
- `resolve`：把关键字或代码解析为内部行情标识。

已不再把 `common` / `utils` 暴露为默认用户入口。

---

## 3. 命令组织原则

## 3.1 命令按任务组织

命令路径优先表达用户任务，而不是底层函数名。

例如：

- `stock price history`
- `stock price latest`
- `stock flow today`
- `fund reports download`
- `resolve quote-id`

而不是：

- `stock get-quote-history`
- `stock get-latest-quote`
- `stock get-today-bill`
- `fund get-pdf-reports`
- `utils get-quote-id`

## 3.2 同类能力共享同一骨架

行情类统一为：

- `price latest`
- `price history`
- `price live`
- `price snapshot`

资金流类统一为：

- `flow today`
- `flow history`

成交类统一为：

- `trades`

基础资料类统一为：

- `profile`

---

## 4. 通用运行时参数

所有查询型命令默认支持以下运行时参数：

- `--format table|json|csv|tsv`
- `--full`
- `--transpose`
- `--no-index`
- `--limit N`
- `--output PATH`
- `--encoding utf-8`
- `--indicator-level basic|advanced|full`
- `--view raw|observation`
- `--trace-window N`
- `--watch`
- `--interval FLOAT`
- `--count INT`
- `--clear/--no-clear`

说明：

- `table`：默认控制台表格输出；
- `json`：适合 Agent 或脚本继续处理；
- `csv/tsv`：适合导出或二次分析；
- `--indicator-level`：控制技术指标丰富度；
- `--view observation`：输出结构化观察视图；
- `--count`：统一只表示刷新次数，不表示业务数量。

---

## 5. 顶层命令

## 5.1 `search`

用于按关键字搜索证券候选项。

示例：

```bash
efinance search --query 贵州茅台
efinance search --query PG --result-count 10 --format json
efinance search --query 腾讯 --market Hongkong
```

### 5.1.1 `search local`

用于仅依赖本地缓存进行搜索。

示例：

```bash
efinance search local --query 苹果 --market US_stock
```

## 5.2 `watch`

用于为任意子命令开启循环刷新。

示例：

```bash
efinance watch --interval 2 stock price live
efinance watch --interval 5 fund estimate live --symbols 161725 --symbols 005827
```

---

## 6. 各业务域命令

## 6.1 股票 `stock`

主要命令：

- `profile`
- `price latest`
- `price history`
- `price live`
- `price snapshot`
- `flow today`
- `flow history`
- `trades`
- `holders latest-count`
- `holders top10`
- `ipo latest`
- `leaderboard daily`
- `performance quarterly`
- `report-dates`
- `constituents`
- `sector`

示例：

```bash
efinance stock profile --symbols 600519
efinance stock price history --symbols 600519 --start-date 20250101 --end-date 20250501 --full
efinance stock price live --market ETF --limit 20
efinance stock flow today --symbol 600519
efinance stock constituents --symbol 000300
```

## 6.2 基金 `fund`

主要命令：

- `catalog`
- `profile`
- `nav history`
- `nav history-batch`
- `estimate live`
- `allocation industry`
- `allocation position`
- `allocation types`
- `performance period`
- `disclosure dates`
- `managers`
- `reports download`

示例：

```bash
efinance fund profile --symbol 161725
efinance fund nav history --symbol 161725 --max-pages 200
efinance fund nav history-batch --symbols 161725 --symbols 005827
efinance fund estimate live --symbols 161725 --symbols 005827 --watch --interval 10
efinance fund reports download --symbol 161725 --output-dir reports
```

## 6.3 债券 `bond`

主要命令：

- `catalog`
- `profile`
- `price live`
- `price history`
- `flow today`
- `flow history`
- `trades`

示例：

```bash
efinance bond profile --symbol 123107
efinance bond price history --symbol 123107 --start-date 20250101 --end-date 20250501
efinance bond flow today --symbol 123107
```

## 6.4 期货 `futures`

主要命令：

- `catalog`
- `price live`
- `price history`
- `trades`

示例：

```bash
efinance futures catalog
efinance futures price history --quote-id 东方财富期货行情ID
efinance futures price live
```

说明：

- 期货历史行情通常更依赖 `quote_id` 访问。

## 6.5 高级通用入口 `quote`

主要命令：

- `profile`
- `price latest`
- `price history`
- `flow today`
- `flow history`
- `trades`

适用场景：

- 已知 `quote_id`；
- 跨品类统一访问；
- 需要绕过具体业务域直接调通用行情入口。

示例：

```bash
efinance quote price latest --quote-ids 105.AAPL
efinance quote price history --symbols 105.AAPL --start-date 20250101 --end-date 20250501
efinance quote flow history --symbol 105.AAPL
```

## 6.6 市场入口 `market`

主要命令：

- `price live`
- `add`

说明：

- `market price live` 是按市场过滤串进行的大盘级扫描入口；
- `market add` 用于扩展本地市场分类映射，属于高级/带副作用能力。

示例：

```bash
efinance market price live --market "m:105+t:3"
efinance market add --market-category custom --market-id 999 --market-name my_market
```

## 6.7 解析入口 `resolve`

主要命令：

- `quote-id`

示例：

```bash
efinance resolve quote-id --symbol AAPL --market US_stock
```

---

## 7. Observation 视图

当前 observation 视图支持以下类型的命令：

- 历史行情类：
  - `quote price history`
  - `stock price history`
  - `bond price history`
  - `futures price history`
  - `fund nav history`
  - `fund nav history-batch`
- 最新/快照/基础资料类：
  - `quote price latest`
  - `stock price latest`
  - `stock price snapshot`
  - `stock profile`
  - `bond profile`
  - `quote profile`
- 实时列表类：
  - `stock price live`
  - `bond price live`
  - `futures price live`

当前暂未纳入首批 observation 深度支持：

- `fund estimate live`
- `market price live`

### 7.1 Observation 结构

observation 模式的核心 section 固定为：

- `meta`
- `latest_quote`
- `current_metrics`
- `trace_points`
- `recent_events`

### 7.2 输出差异

- `table`：使用统一 boxed section 风格；
- `json`：直接输出结构化 observation payload；
- `csv/tsv`：输出 long-form 长表，保留与 `table/json` 等价的信息量。

---

## 8. 面向 Agent 的使用建议

推荐默认查询链路：

1. `search`
2. `resolve quote-id`
3. 各领域命令或 `quote` 高级入口

推荐策略：

- 需要用户可理解的查询时，优先走 `stock/fund/bond/futures`；
- 已知 `quote_id` 或要做跨品类统一处理时，再走 `quote`；
- 需要做市场扫描时，走 `market`；
- 尽量优先使用 `--format json` 供后续程序消费。

---

## 9. 当前实现边界

当前版本已经完成：

- 语义化命令树；
- 语义化参数命名；
- 统一输出层；
- observation 视图；
- 循环刷新；
- 顶层 `search` / `watch` / `resolve` / `market` 入口。

后续仍可继续增强：

- 更多命令接入 observation 深度支持；
- 更细粒度的帮助文本与命令别名策略；
- 更智能的市场枚举提示与自动补全；
- 更完善的外部数据源重试与降级策略。
