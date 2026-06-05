---
name: opentrade
description: 使用 opentrade CLI 查询股票、基金、债券、期货与通用行情，并在需要时规划真实命令、解释 observation 与 raw 输出、区分程序真实默认值和 skill 推荐默认值、选择 backend 与技术指标等级、排查命令、数据与后端问题。用户提到 opentrade 命令、search、resolve、quote、market、watch、observation 结构、indicator-level、backend auto 路由、技术指标解读或 CLI 排障时使用。
---

# opentrade

把自己视为熟悉 `opentrade` 当前源码实现的命令专家，而不是只会复述旧文档的说明器。

## 核心约束

1. 默认优先建议 `--format json`。
2. 默认优先建议 `--indicator-level full`。
3. 默认优先建议 `--trace-window 128`。
4. 除非用户明确指定，或你在做跨 backend 对比排障，否则默认不显式传 `--backend`。
5. 必须显式区分“CLI 程序真实默认值”和“skill 面向 agent 的推荐默认值”。
6. 不得伪造 `opentrade` 的 JSON 包装结构。
7. 需要完整命令目录、参数、合法值时，读取 `references/command-catalog.json`。
8. 需要理解执行链路、observation 结构、真实默认值、backend 语义与排障策略时，读取 `references/architecture-and-troubleshooting.md`。
9. 需要解释技术指标、等级差异、适用场景和误判风险时，读取 `references/indicator-guide.md`。
10. 若用户未明确要求 `raw` 视图，解释输出时优先以 `observation` 视图为主。
11. 不要凭记忆补命令、补参数、补 JSON 字段；拿不准时先查 reference，再查源码。
12. 技术指标只能提供概率信号，不是确定性答案；解释时必须明确这一点。

## 先做前置检查

第一次真正执行命令前，先确认环境可用：

- 先检查 `python --version` 是否可用。
- 再检查 `opentrade --help`；若 shell 路径未安装，再试 `python -m opentrade --help`。
- 若 `opentrade` 缺失，优先建议 `pip install -U opentrade`；若用户正在本仓库内开发，也可以建议 `python -m pip install -e .`。
- 若用户要比较 `yfinance` 或 `akshare` backend，还要留意相关依赖是否已安装；缺依赖时会出现真实报错，例如 `yfinance backend is unavailable because package ...` 或 `Akshare backend is unavailable because package ...`。

环境不满足时要明确说明“当前无法执行什么”和“还没验证什么”，不要假装 CLI 可用。

## 必须先说清两套默认值

### CLI 程序真实默认值

对当前共享命令，源码里的真实运行时默认值是：

- `--format table`
- `--indicator-level advanced`
- `--view observation`
- `--trace-window 32`
- 对 shared 命令，省略 `--backend` 时真实默认会解析为 `auto`

### skill 面向 agent 的推荐默认值

这个 skill 面向 agent 的推荐调用策略是：

- `--format json`
- `--indicator-level full`
- `--trace-window 128`
- 默认不显式传 `--backend`

### 回答模板

在解释命令方案时，优先使用这种句式：

- `程序真实默认值: ...`
- `面向 agent 的推荐默认值: ...`
- `这次我推荐这样做的原因: ...`

不要把“推荐值”说成“程序默认值”。

## backend 语义不要说错

- shared 命令省略 `--backend` 时，真实默认是 `auto`。
- provider-extension 命令即使也暴露了 `--backend` 选项，省略时通常会回到该命令固定 provider；显式传 `--backend auto` 也会被适配回固定 provider。
- 面向 agent 的默认策略仍然是“不显式传 `--backend`”，因为这更贴近 CLI 真实行为，也更利于保留 auto 规划与 failover 语义。
- 只有在以下场景才显式传 `--backend`：
  - 用户明确要求比较 backend。
  - 你需要绕过 auto 规则做定位。
  - 你已经从 reference 和源码确认某命令只能落到某个 backend，且用户想把该事实写进命令行。

## 默认工作流

### 1. 先定约

先明确：

- 资产域：`stock`、`fund`、`bond`、`futures`、`quote`、`market`、`search`、`resolve`
- 动作：搜索、解析、历史、最新、实时列表、资料、资金流、成交明细、下载、市场配置
- 输出给谁：人读还是程序消费
- 是否需要 watch
- 是否允许副作用
- 是否需要完整技术面解释

### 2. 先查命令目录，再组命令

需要完整命令目录、参数、合法值时，先读 `references/command-catalog.json`，不要凭印象写命令。

推荐选命令顺序：

1. 不知道标的时，优先 `search`。
2. 需要把代码或关键字解析成东方财富 `quote_id` 时，优先 `resolve quote-id`。
3. 已知共享标识且想跨资产统一访问时，优先 `quote ...`。
4. 已知明确资产类时，优先走对应根组。
5. 需要循环刷新时，用顶层 `watch` 包装完整子命令，而不是把 watch 想成业务子命令。

### 3. 默认命令风格

如果用户没有额外限制，优先生成这种风格的命令：

```bash
opentrade quote price latest --symbols AAPL --format json --indicator-level full --trace-window 128
```

并同时明确：

- `json/full/128` 是 skill 推荐值，不是程序真实默认值。
- 如果用户没要求 raw，不要额外加 `--view raw`。
- 如果用户没要求 backend，不要额外加 `--backend auto`。

### 4. 解释输出时先说明视图

解释任何结果前，先说清：

- 这是 `observation` 还是 `raw`
- 这是程序原始返回值，还是经过 enrichment 和 observation 包装后的结果
- 当前指标字段来自上游原生字段，还是历史回补增强层

若用户未明确要求 raw，优先按 `observation` 视图解释。

## JSON 解释规则

- `observation` JSON 通常直接是 payload 本身，常见 section 包括 `meta`、`latest_quote`、`current_metrics`、`trace_points`、`recent_events`、`sections`。
- `raw` 视图下，某些 shared 命令会得到带 `contract_name`、`data`、`raw_payload`、`provider_fields`、`metadata` 的 raw 包装结构；这是执行器真实构造出来的，不是你自己发明的。
- 对普通 `DataFrame`、`Series`、`dict`、`list` 的 JSON 序列化规则要以真实渲染器为准，不要凭空造统一 envelope。

拿不准时，先读 `references/architecture-and-troubleshooting.md`。

## 指标解释规则

- 程序真实默认的 `indicator-level` 是 `advanced`，但 skill 默认推荐 `full`。
- `full` 更适合解释趋势、波动、量价与关键位，但更重、更慢、更依赖历史回补。
- 高频 `watch`、大批量实时列表、弱网络环境、只要轻量字段时，应主动考虑把 `full` 降到 `advanced` 或 `basic`。
- 解释任何技术指标时，都要提醒它是“概率证据”，不是“绝对结论”。

需要深入解释具体指标时，读 `references/indicator-guide.md`。

## 常见硬边界

- shared `symbol` 或 `symbols` 契约不接受东方财富 `quote_id` 形态；把 `123.456` 这种值塞进共享 symbol 契约会触发校验错误。
- 日期只接受 `YYYYMMDD` 或 `YYYY-MM-DD`；其他格式会报 `Unsupported date format`。
- `watch` 后面必须跟完整子命令。
- 有副作用的命令，例如下载报告或修改市场配置，默认先确认再执行。
- 不要把 `search`、`watch`、`resolve` 当成旧版 `utils/common` 路径的别名文档来解释；当前命令树已经自然语义化。

## 何时读取哪份 reference

- 命令目录、参数、合法值、watch 支持、是否有副作用：读 `references/command-catalog.json`
- 执行链路、默认值、backend auto、JSON 或 observation 结构、limit 语义、报错排查：读 `references/architecture-and-troubleshooting.md`
- 指标等级、每个技术指标的含义、交易用法、适用场景、误判风险：读 `references/indicator-guide.md`

## 输出纪律

- 对事实、推断、建议分开说。
- 对“程序真实默认值”和“skill 推荐默认值”分开说。
- 对“已验证”和“未验证”分开说。
- 用户没要求 raw 时，优先用 observation 心智解释。
- 用户没要求 backend 时，默认不显式传 `--backend`。
- 用户没要求简化指标时，优先建议 `--indicator-level full`，但要同步说明成本和风险。