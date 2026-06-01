# efinance-cli 设计与使用说明

## 1. 文档定位

本文档说明当前版本 `efinance-cli` 的命令组织方式、后端选择语义与运行时边界。
当前版本已经不再把 CLI 视为 `efinance` 上游函数的自然语言包装，而是以：

- 后端无关的共享命令；
- provider 扩展命令；
- 统一请求 schema、统一结果契约和统一执行骨架；

作为面向用户和维护者的稳定对象。

## 2. 当前命令模型

当前 CLI 只保留两类命令：

1. 共享命令  
   面向稳定业务语义，命令入口和参数定义尽量与具体后端解耦。
2. Provider 扩展命令  
   保留后端专属能力，不强行压成共享最小公分母。

旧函数驱动命令树已经下线，不再作为当前版本的用户入口。

## 3. 顶层命令树

当前用户可见的顶层入口包含：

```text
efinance
├── search
├── watch
├── stock
├── fund
├── bond
├── futures
├── quote
├── market
└── resolve
```

说明：

- `search` 是共享命令 `instrument.search` 的顶层快捷入口；
- `stock`、`fund`、`bond`、`futures` 是正式资产域；
- `quote`、`market`、`resolve` 是 utility 入口；
- provider 扩展命令会挂入业务语义命令树，而不是额外暴露 provider 根组；
- `watch` 是统一的循环刷新包装命令，会复用同一条请求解析与执行链路。

## 4. 共享命令与 Provider 扩展命令

### 4.1 共享命令

共享命令的目标是为相同业务能力提供稳定入口。当前版本中，只有真实支持多个 backend 的命令才属于 shared。下面只列出当前仍在 shared catalog 中的代表性命令：

| 命令键 | CLI 路径 | 说明 | 支持后端 |
| --- | --- | --- | --- |
| `instrument.search` | `search` | 搜索证券候选项 | `efinance`、`akshare`、`yfinance` |
| `stock.price.history` | `stock price history` | 股票历史行情 | `efinance`、`akshare`、`yfinance` |
| `stock.price.live` | `stock price live` | 股票实时行情列表 | `efinance`、`akshare` |
| `stock.profile` | `stock profile` | 股票基础资料 | `efinance`、`akshare`、`yfinance` |
| `fund.nav.history` | `fund nav history` | 基金净值历史 | `efinance`、`akshare`、`yfinance` |
| `quote.price.history` / `quote.price.latest` / `quote.profile` | `quote ...` | 通用行情历史、最新价与资料 | `efinance`、`yfinance` |
| `fund.profile` | `fund profile` | 基金资料 | `efinance`、`yfinance` |

共享命令的共同特征：

- 参数来自显式 request schema，而不是第三方函数签名反射；
- 帮助页会显示命令键、能力标识、支持后端与命令类别；
- 非 raw 视图会进入统一的标准化、增强、observation 与渲染管线；
- raw 视图会保留 `raw_payload`、`provider_fields`、`metadata` 等 provider 原始上下文。

### 4.2 Provider 扩展命令

provider 扩展命令用于保留特定后端独有能力。只要某个命令当前只支持单一 backend，它在内部就必须被归类为 provider-extension，即使它仍挂在 `bond`、`quote`、`market`、`resolve` 这类业务语义路径下。当前已经落地的示例包括：

```bash
efinance bond catalog
efinance quote price latest --quote-ids 1.000001
efinance search local --query 贵州茅台
efinance stock industry boards
```

这类命令表示：

- 单 backend 命令不会再伪装成 shared；
- 命令会显式绑定所属 provider；
- 命令路径位于业务语义树中，而不是位于 provider 根组下；
- 仍然复用统一执行骨架与结果契约；
- 错误地显式指定其它 backend 时，会明确失败，而不是静默降级。

`yfinance` 当前已经按同样规则接入扩展命令，例如：

```bash
efinance quote news --quote-id AAPL --result-count 5
```

补充说明：

- `quote news` 是首个 Yahoo 专属扩展命令，仍复用统一执行骨架、标准化输出与错误 backend 约束；
- 这里的 `quote-id` 实际上遵循 Yahoo ticker / symbol 语义，典型输入是 `AAPL`、`MSFT`、`0700.HK`、`9988.HK`；
- `--result-count` 表示业务返回的新闻条数，避免与统一 watch 运行时的 `--count` 刷新次数语义混淆。

## 5. `--backend` 语义

`--backend` 是共享命令和 provider 扩展命令的统一后端选择参数。

### 5.1 共享命令

共享命令支持显式传入 `--backend`：

```bash
efinance stock price history --symbols 600519 --backend efinance
efinance stock price history --symbols 600519 --backend akshare
efinance fund nav history --symbol 161725 --backend akshare
```

规则如下：

- 不传 `--backend` 时，默认按 `auto` 语义解析，并按 `akshare -> yfinance -> efinance` 的固定顺序尝试可用 backend；
- 显式传入的 backend 必须在该命令的支持矩阵内；
- 不受支持的 backend 会直接报错，不会回退到默认后端。
- 当命令支持 `yfinance` 时，帮助页会额外提示 Yahoo ticker / symbol 语义与限流边界。
- 对 `yfinance` 来说，`market` 与 `symbol` 的历史习惯只会做最小映射；跨市场场景应优先直接传 Yahoo ticker，而不要假设所有本地代码都能被自动翻译。

### 5.2 Provider 扩展命令

provider 扩展命令也接受 `--backend`，但其默认行为不同：

```bash
efinance stock industry boards
efinance stock industry boards --backend akshare
```

规则如下：

- 不传 `--backend` 时，默认解析到所属 provider；
- 显式传入 `--backend auto` 时，也会直接自动适配到所属 provider，而不是参与共享命令的多 backend 降级链；
- 显式传入相同 provider 允许执行；
- 显式传入其它 provider 会明确失败，并提示该命令默认会路由到所属 provider。

## 6. 统一运行时参数

共享命令与 provider 扩展命令统一支持以下运行时参数：

- `--backend`
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

- `--view raw` 适合调试 provider 差异、核对原始字段和扩展字段；
- `--view observation` 适合统一阅读结构化观察结果；
- 顶层 `watch` 与命令内 `--watch` 复用同一请求对象和同一 backend 解析逻辑；当共享命令走 `auto` 时，每轮刷新都会重新按相同候选链顺序执行；
- `--count` 仅表示刷新次数，不表示业务记录数量。

## 7. 当前推荐用法

### 7.1 共享搜索

```bash
efinance search --query 贵州茅台
efinance search --query 腾讯 --backend akshare --format json
```

`search local` 仍可继续使用，但它属于 `efinance` 单 backend 的 provider-extension，而不是共享搜索命令面的一部分。

### 7.2 股票、债券与期货行情

```bash
efinance stock price history --symbols 600519 --start-date 20250101 --end-date 20250501
efinance stock price history --symbols 600519 --backend akshare --view raw --format json
efinance stock price live
efinance bond price history --symbols 113519
efinance futures price live
efinance watch --interval 3 stock price live --backend akshare
```

### 7.3 股票资料、基金净值与 utility 入口

```bash
efinance stock profile --symbols 000001
efinance stock profile --symbols 000001 --backend akshare --view raw
efinance fund nav history --symbol 161725
efinance fund nav history --symbol 161725 --backend akshare --format json
efinance quote price latest --quote-ids 1.000001
efinance market price live --market m:105+t:3
efinance resolve quote-id --symbol 000001
```

### 7.4 Provider 扩展能力

```bash
efinance bond catalog
efinance quote price latest --quote-ids 1.000001
efinance search local --query 贵州茅台
efinance stock industry boards
efinance quote news --quote-id AAPL --result-count 5
```

### 7.5 `yfinance` 可选 live smoke 验证

`yfinance` 的自动化主验证应继续以 mock / contract tests 为主；如果需要做人工 live smoke，建议只做小样本、显式 backend 的快速检查，例如：

```bash
efinance search --query AAPL --backend yfinance --format json
efinance stock price history --symbols AAPL --backend yfinance --start-date 20250102 --end-date 20250501 --format json
efinance quote news --quote-id AAPL --backend yfinance --result-count 3 --format json
```

说明：

- 这些 smoke 仅用于确认显式 `--backend yfinance` 的真实网络路径可工作；
- Yahoo 可能因为限流、地区网络差异或上游字段波动直接失败，因此不应把 live smoke 当成稳定 CI 前提；
- 若 live smoke 失败，应优先结合单元测试、合同测试与报错内容判断是限流边界还是实现回归。

## 8. BREAKING 变化

当前版本相对于旧的函数驱动 CLI，有以下重要变化：

1. 命令稳定对象已经从“第三方函数”转为“命令键 + capability + request schema”。
2. 共享命令的参数定义不再承诺与上游 provider 函数签名一一对应。
3. 同一业务命令在不同后端下允许存在字段完整度差异，但会努力满足相同核心结果契约。
4. provider 特有能力不再伪装成通用命令，但也不再直接暴露 provider 顶层根组，而是挂到业务语义命令树。
5. `--backend` 选择失败时会显式报错，不再依赖隐式兼容或静默回退。

## 8.1 完整支持判定

当前文档中的“支持某个 backend”不再等价于“命令能被路由到某个 handler”。判断一个命令是否已完整支持，必须同时满足：

- 命令在 CLI 中可见，且请求参数能通过显式 schema 校验；
- provider 侧存在真实 handler，并返回稳定标准结果契约；
- 非 `raw` 输出会进入统一 enrichment / observation / rendering 主链；
- 测试中的支持矩阵与运行时真实实现保持一致。

### 8.2 当前关键支持矩阵

下列关键命令已经进入一等运行时主链：

| 命令键 | 说明 | 标准结果契约 | observation / enrichment |
| --- | --- | --- | --- |
| `stock.price.history` | 股票历史行情 | `history-bars` | 历史序列主链 |
| `bond.price.history` | 债券历史行情 | `history-bars` | 历史序列主链 |
| `futures.price.history` | 期货历史行情 | `history-bars` | 历史序列主链 |
| `quote.price.history` | 通用行情历史 | `history-bars` | 历史序列主链 |
| `fund.nav.history` | 基金净值历史 | `fund-nav-history` | 净值序列主链 |
| `fund.nav.history-batch` | 基金批量净值历史 | `fund-nav-history` | 多 source 净值序列主链 |
| `stock.profile` / `fund.profile` / `bond.profile` / `quote.profile` | 基础资料 | `profile-info` | 单标的回补主链 |
| `stock.price.live` / `bond.price.live` / `futures.price.live` / `quote.price.latest` | 实时行情 | `realtime-quotes` | 多 source 回补主链 |

仍未进入专用 observation 模板的记录类命令，例如 `flow` / `trades` / `catalog`，会继续使用受约束的 `provider-records` 契约和 generic observation 兜底，而不是无约束原始对象。

## 9. 当前边界

当前版本的主要边界如下：

- 已下线旧函数驱动命令树，新增用户能力应继续走 shared / provider-extension 模型；
- `yfinance` 已正式接入搜索、历史、最新价 / 快照、股票 / 基金 / quote 资料与 `quote news` 扩展命令；
- `yfinance` 以 Yahoo ticker / symbol 语义为主，对 bond / futures / 国内市场专属命令面并不承诺支持；
- Yahoo 侧可能触发显式限流错误，当前实现会直接返回可读失败，而不是静默回退或伪造空结果；
- observation 与 enrichment 会优先消费标准契约与标准补充接口，不应重新引入旧式 provider 回补分支。

如果你在扩展新命令，应优先判断它属于：

- 共享能力；
- provider 专属扩展。

不要再把新的用户能力直接绑定到第三方函数名上。
