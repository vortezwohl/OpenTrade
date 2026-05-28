---
name: efinance-cli
description: 使用 efinance-cli 查询股票、基金、债券、期货与通用行情，并在需要时解释真实命令树、observation 输出、JSON 结构、重试边界、指标含义与排障路径。
---

# efinance-cli

使用这个 skill 时，把自己视为熟悉 `efinance-cli` 当前代码实现的命令专家，而不是只会背旧版 README 的说明器。

## 核心规则

1. 默认优先建议 `--format json`。
2. 默认优先建议 `--indicator-level full`。
3. 默认优先建议 `--trace-window 128`。
4. 必须显式区分“CLI 程序真实默认值”和“skill 面向 agent 的推荐默认值”。
5. 不得伪造 `efinance-cli` 的 JSON 包装结构。
6. 需要完整命令目录、参数、合法值时，读取 `references/command-catalog.json`。
7. 需要理解执行链路、observation 结构、真实默认值与排障策略时，读取 `references/architecture-and-troubleshooting.md`。
8. 需要解释技术指标、等级差异和适用场景时，读取 `references/indicator-guide.md`。
9. 对用户展示命令时，优先使用当前自然语义化命令树，不得退回旧式 `common` / `utils` 命名体系。
10. 若用户未明确要求 raw 视图，解释输出时优先以 `observation` 视图为主。

## 使用前置检查

在第一次真正调用命令前，先检查：

1. 系统里是否有 `python`
2. 系统里是否有 `efinance` 或 `efinance-cli`

处理规则：

- 如果没有 `python`，先说明环境不满足，不要假设 CLI 可用。
- 如果有 `python` 但没有 `efinance` / `efinance-cli`，优先建议：

```bash
pip install -U the-efinance-cli
```

- 安装来源可参考 [vortezwohl/efinance-cli](https://github.com/vortezwohl/efinance-cli)。
- 若两个命令都存在，优先使用当前环境里真实可执行的那个命令名。

## 先说明两套默认值

### 1. CLI 程序真实默认值

当前代码里的真实默认值是：

- `--format table`
- `--indicator-level advanced`
- `--view observation`
- `--trace-window 32`

### 2. skill 面向 agent 的推荐默认值

这个 skill 面向 agent 的推荐策略是：

- `--format json`
- `--indicator-level full`
- `--trace-window 128`

原因：

- `json` 更适合后续程序消费与结构化分析。
- `full` 更适合一次性拿到更完整的量化上下文。
- `trace-window 128` 更适合 agent 做近期轨迹比较、事件回溯和多指标联读。

不要把这两套默认值说反。

## 当前真实命令树

当前顶层命令是：

- `stock`
- `fund`
- `bond`
- `futures`
- `quote`
- `market`
- `resolve`
- `search`
- `watch`

要点：

- `quote` 是旧 `common` 的自然语义化入口。
- `market` 承接市场级实时扫描和市场配置。
- `resolve` 承接 `get_quote_id` 这类标识解析能力。
- `search` 是顶层手写包装命令，不是普通动态命令。
- `watch` 是顶层刷新包装器，不是普通业务查询命令。

## 真实输出模型

### 1. `observation` 已是默认视图

当前 CLI 默认就是：

```bash
--view observation
```

因此：

- 用户不显式传 `--view raw` 时，应默认预期结构化 observation 输出。
- README、示例、解释都应优先围绕 observation 组织，而不是旧版宽表心智。

### 2. 真实 JSON 规则

`--format json` 输出的是返回值本身的序列化结果，不会额外包一层统一响应对象。

序列化规则：

- `DataFrame` 输出 `records` 数组
- `Series` 输出 `object`
- `dict` 递归输出 `object`
- `list` / `tuple` / `set` 输出 `array`
- dataclass 走 `asdict`
- namedtuple 走 `_asdict`
- `None` 输出 `null`
- 其他类型走 `default=str`

如果是 observation payload，则 JSON 会直接包含这些 section：

- `meta`
- `latest_quote`
- `current_metrics`
- `trace_points`
- `recent_events`
- `sections`

### 3. observation table 规则

table 模式下的 observation 不是传统 DataFrame 宽表，而是 boxed ASCII section 布局。

常见 section：

- `meta`
- `latest_quote`
- `current_metrics`
- `trace_points.<group>`
- `recent_events`
- `result[n]` 或 `source.<key>`

## 默认工作流

### 1. 先定约

先明确：

- 目标市场：`stock` / `fund` / `bond` / `futures` / `quote` / `market`
- 目标动作：搜索、解析、历史、最新、实时列表、成交、资金流、资料、下载
- 是否允许副作用：例如 `fund reports download`、`market add`
- 输出是给人读还是给程序消费
- 是否需要 watch
- 是否需要 full 指标

### 2. 选命令

推荐顺序：

1. 不知道标的时，先 `search`
2. 知道代码但不确定 quote id 时，走 `resolve quote-id`
3. 已知 quote id 且要跨品类统一访问时，走 `quote ...`
4. 只关心某个市场实时扫描时，走 `market price live`
5. 已知明确资产类别时，优先走对应模块命令

### 3. 组命令

若用户没有别的限制，agent 推荐命令通常是：

```bash
efinance quote price latest --quote-ids 105.AAPL --format json --indicator-level full --trace-window 128
```

但要同时说明：

- `json/full/128` 是 skill 推荐值
- 程序真实默认值仍是 `table/advanced/32`

### 4. 解释结果

解释结果时先说清：

- 这是 observation 视图还是 raw 视图
- 这是原始返回值还是带历史回补和指标增强的 observation payload
- `current_metrics` 里的指标来自增强层，不一定是上游实时接口原生字段

## watch 规则

- 不是所有命令都支持 watch
- `fund reports download` 不支持 watch
- `market add` 不支持 watch
- 高频 watch + `full` + 大 `trace-window` 会明显增加请求和渲染成本
- 如果用户要高频轮询，优先建议把 `indicator-level` 从 `full` 降到 `advanced` 或 `basic`
- 如果用户要程序消费，优先建议 `--format json`

## 何时读取参考文件

- 命令目录、参数、合法值、副作用、watch 支持：`references/command-catalog.json`
- 执行链路、真实默认值、observation 契约、网络重试、失败分层：`references/architecture-and-troubleshooting.md`
- 指标等级、适用场景、误读风险：`references/indicator-guide.md`

## 直接可用的命令风格

### 搜索

```bash
efinance search --query AAPL --market US_stock --result-count 5 --format json --trace-window 128
```

### 标识解析

```bash
efinance resolve quote-id --symbol AAPL --market us_stock --format json
```

### 通用最新行情

```bash
efinance quote price latest --quote-ids 105.AAPL --format json --indicator-level full --trace-window 128
```

### 股票历史

```bash
efinance stock price history --symbols AAPL --market us_stock --start-date 20250102 --end-date 20250501 --format json --indicator-level full --trace-window 128
```

### 市场实时扫描

```bash
efinance market price live --market m:105+t:3 --format json --indicator-level advanced
```

### watch 包装

```bash
efinance watch --interval 5 quote price latest --quote-ids 105.AAPL --format json
```
