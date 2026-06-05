# 架构与排障参考

## 1. 先分清两套默认值

### 1.1 CLI 程序真实默认值

当前源码中的运行时默认值是：

- `--format table`
- `--indicator-level advanced`
- `--view observation`
- `--trace-window 32`
- `--interval 2.0`
- `--encoding utf-8`
- shared 命令省略 `--backend` 时，真实默认路由到 `auto`

### 1.2 skill 面向 agent 的推荐默认值

本 skill 对 agent 的推荐值是：

- `--format json`
- `--indicator-level full`
- `--trace-window 128`
- 默认不显式传 `--backend`

### 1.3 必须怎么回答

- 用户问“默认是什么”时，回答程序真实默认值。
- 用户问“你建议怎么调”时，可以回答 skill 推荐值，但必须明确说明这是推荐值而不是程序默认值。
- 不要把 `json/full/128` 伪装成 CLI 默认行为。

## 2. 真实执行链路

### 2.1 主链路

当前 CLI 主链路是：

1. `opentrade.main` / `opentrade.__main__`
2. `opentrade.app.create_cli`
3. `opentrade.commands.create_root_command`
4. `opentrade.command_catalog`
5. `opentrade.request_schema`
6. `opentrade.executor.CommandExecutor`
7. `opentrade.facade.CommandFacade`
8. `opentrade.backends.*`
9. `opentrade.enrichment.service`
10. `opentrade.observation`
11. `opentrade.rendering`

### 2.2 每层职责

- `commands.py`: 负责组装 Click 命令树，并追加统一运行时参数。
- `command_catalog.py`: 维护 shared 命令定义、provider-extension 命令定义、backend 支持矩阵与 limit 策略。
- `request_schema.py`: 做参数归一化、日期校验、shared symbol 契约校验、market 枚举校验。
- `executor.py`: 串起 backend 调用、observation 增强、raw 与 observation 分流、watch 循环、文件输出。
- `facade.py`: 负责 auto candidate 链执行和 failover 判定。
- `enrichment.service`: 对支持的命令做历史回补和指标增强。
- `observation.py`: 把增强后的结果组装成 observation payload。
- `rendering.py`: 决定 table、json、csv、tsv 的最终输出结构。

## 3. 当前真实命令树

### 3.1 顶层命令

当前顶层根组是：

- `stock`
- `fund`
- `bond`
- `futures`
- `quote`
- `market`
- `resolve`
- `search`
- `watch`

### 3.2 特殊顶层命令

#### `search`

- 顶层 `search` 不是普通动态 provider 命令，而是手写包装的默认搜索入口。
- 它内部仍然走共享命令能力 `instrument.search`。
- 默认也走 `observation` 视图；`--format json` 时通常直接输出候选项 observation payload。

#### `watch`

- 顶层 `watch` 不是业务查询命令，而是参数转发包装器。
- 它接收 `--interval`、`--count`、`--clear/--no-clear`，然后把这些参数追加到后面的完整子命令。
- `watch` 自己不会查询行情数据。

#### `resolve`

- `resolve quote-id` 用于把 symbol 或关键字解析成东方财富 `quote_id`。
- 它是 provider-extension 命令，不是 shared 命令。

## 4. backend 解析与 auto 语义

### 4.1 shared 命令

- shared 命令省略 `--backend` 时，`resolver.py` 会把 backend 解析成 `auto`。
- 真正的 auto candidate 链在 `executor.py` 调 `plan_auto_backend_candidates()` 后才产生。
- 当前默认 auto 候选顺序基线是：`efinance -> yfinance -> akshare`。
- 但真实顺序还会被 `market`、symbol 形状、command key 和“是否能真实消费请求”共同影响。

### 4.2 provider-extension 命令

- provider-extension 命令省略 `--backend` 时，真实会回到命令自带的固定 provider。
- 如果用户显式写 `--backend auto`，对 provider-extension 命令会被改写回固定 provider，而不是继续保持 auto。

### 4.3 何时不该显式传 `--backend`

默认不显式传 `--backend`，因为：

- shared 命令可以保留真实 auto 语义。
- provider-extension 命令本来就有固定 provider。
- 对多数普通用户场景，显式写 `--backend auto` 只会增加噪音，不会提升可靠性。

### 4.4 何时应该显式传 `--backend`

- 用户明确要求对比 backend。
- 你在做 auto failover 排障。
- 你需要证明某个命令不支持某 backend。
- 你要复现 backend 特有 bug。

## 5. observation 与 raw 的真实结构

### 5.1 默认视图其实已经是 observation

当前 CLI 默认值是：

```bash
--view observation
```

因此：

- 用户不显式传 `--view raw` 时，默认应预期结构化 observation 输出。
- 向用户解释结果时，默认以 observation 心智为主。

### 5.2 observation payload 常见结构

典型 observation payload 会包含：

- `meta`
- `latest_quote`
- `current_metrics`
- `trace_points`
- `recent_events`
- `sections`

其中：

- `meta` 会带 `module`、`function`、`view`、`indicator_level`、`trace_window`、`row_count`，以及 backend 可见信息。
- `latest_quote` 是当前主行情字段。
- `current_metrics` 是关键技术指标快照。
- `trace_points` 是近若干 bar 的轨迹块。
- `recent_events` 是客观事件检测结果，例如均线金叉、RSI 穿阈值、价格触碰布林带。
- `sections` 是 generic observation 兜底补充区域。

### 5.3 observation table 行为

table 模式下，observation 不是传统单宽表，而是 boxed ASCII section：

- `meta`
- `latest_quote`
- `current_metrics`
- `trace_points.<group>`
- `recent_events`
- `result.*` 或 `source.*`

### 5.4 observation JSON 行为

`--format json` 下，observation 通常直接输出 payload 本身，不会额外套统一 envelope。

多 source observation 时，常见形态类似：

```json
{
  "AAPL": {"meta": {}, "latest_quote": {}, "current_metrics": {}},
  "MSFT": {"meta": {}, "latest_quote": {}, "current_metrics": {}}
}
```

## 6. raw JSON 的真实序列化规则

`rendering.py` 里的真实序列化规则是：

- `DataFrame -> records 数组`
- `Series -> object`
- `dict -> 递归 object`
- `list/tuple/set -> array`
- dataclass -> `asdict`
- namedtuple -> `_asdict`
- `ObservationPayload -> 显式拆成 meta、latest_quote、current_metrics、trace_points、recent_events、sections`
- 其他值保持原值；`json.dumps(..., default=str)` 会在最后兜底

### 6.1 raw 视图下 shared 命令的附加包装

shared 命令在 `raw` 模式下，`executor.py` 会把结果包装成带这些字段的对象：

- `contract_name`
- `data`
- `raw_payload`
- `provider_fields`
- `metadata`

而 `metadata` 里还会补充：

- `requested_backend`
- `resolved_backend`
- `planned_candidates`
- `attempted_candidates`
- `final_backend`
- `fallback_used`
- `limit_strategy`
- `limit_value`
- `limit_effect`
- `display_limit_applied`
- `execution_limit_applied`

这是真实代码行为。不要发明另一套统一 schema 覆盖它。

## 7. 指标等级与 trace 行为

### 7.1 指标等级真实窗口

`enrichment/levels.py` 当前定义：

- `basic`: `history_window=60`, `realtime_limit=50`
- `advanced`: `history_window=120`, `realtime_limit=80`
- `full`: `history_window=200`, `realtime_limit=120`

### 7.2 level 别名

以下别名会被正规化：

- `1 -> basic`
- `2 -> advanced`
- `3 -> full`

### 7.3 trace-window

- 程序真实默认值是 `32`。
- skill 推荐值是 `128`。
- 当 `trace_window <= 0` 时，observation 层会回退到 `32`。

## 8. request_schema 的真实校验边界

### 8.1 日期

- 只接受 `YYYYMMDD` 或 `YYYY-MM-DD`。
- 其他格式会报 `Unsupported date format: ...`。

### 8.2 market

- shared market 会校验到 `MARKET_CHOICES`。
- 常见别名例如 `us`、`hk`、`ashare` 会被规范化。
- 非法枚举会报 `Unknown market enum: ...`。

### 8.3 shared symbol 契约

- shared `symbol` 或 `symbols` 不接受东方财富 `quote_id` 形状。
- 看起来像 `123.456` 的值会命中 `Shared symbol contract does not accept Eastmoney quote_id: ...`。
- 这条规则主要影响 `quote.*`、`stock.*`、`fund.*` 等 shared 契约，不影响 provider-extension 原生 `quote_id` 参数。

## 9. watch 真实边界

- `watch` 后必须跟完整子命令，否则报 `watch must be followed by a full subcommand.`
- 如果目标命令 `allow_watch=False`，执行器会报 `... does not support watch mode.`
- 当前典型不支持 watch 的命令包括有副作用的命令，例如 `fund reports download` 和 `market add`。

## 10. auto failover 的真实停止条件

### 10.1 会继续 failover 的错误

`facade.py` 当前允许 auto 继续切换 backend 的典型错误：

- `ProviderFailure`
- `BackendRateLimitError`
- `OSError`

### 10.2 不会继续 failover 的错误

以下错误会立即停止，而不是切换下一个 backend：

- `click.ClickException`
- `ProviderContractError`
- `ValueError`
- `TypeError`
- `KeyError`

### 10.3 auto 全部失败时的真实报错

若候选链全部失败，会抛出：

- `auto backend 候选全部执行失败`
- 后面逐条列出 `- backend: 异常信息`

如果你看到这类报错，不要只盯着第一个 backend，要看整个 candidate 链与最终尝试结果。

## 11. 网络重试边界

`retry_utils.py` 的职责非常窄：

- 只负责“后端无关的原子网络调用重试”。
- 当前最大重试次数是 `8`。
- 默认网络异常集合包括：`urllib3` HTTP 错误、`OSError`、`IncompleteRead`、`BadStatusLine`。
- 它不负责 multi-backend auto failover，也不负责参数错误、渲染错误、契约错误。

因此：

- 参数报错不要怀疑 retry。
- backend 契约不匹配不要怀疑 retry。
- 真正的“换 backend”是在 `facade.py`，不是在 `retry_utils.py`。

## 12. limit 的真实语义

`--limit` 不是所有命令都等价。

真实语义由 `limit_strategy` 决定，当前常见值包括：

- `display-only`: 主要在渲染阶段裁前 N 行。
- `provider-request`: 可以下推到 provider 请求层。
- `adapter-lightweight`: 适配层轻量控制。

raw 模式下可以从 `metadata.limit_effect` 等字段看到真实执行情况。

## 13. 常见异常现象与排查方案

### 13.1 `Unknown backend: ...`

含义：

- `--backend` 传入了未知值。

排查：

1. 先核对是否只使用 `auto`、`efinance`、`yfinance`、`akshare`。
2. 再确认有没有大小写或拼写错误。

### 13.2 `命令 '...' 不支持 backend '...'`

含义：

- 你显式指定了一个该命令不支持的 backend。

排查：

1. 先查 `command-catalog.json` 里的 `backends`。
2. 再区分是 shared 命令还是 provider-extension 命令。

### 13.3 `命令 '...' 仅支持 backend: ...`

含义：

- 这是 provider-extension 命令，只支持固定 provider。

排查：

1. 去掉显式 `--backend`。
2. 若必须显式写，改成提示里给出的固定 backend。

### 13.4 `没有可用的 auto backend 候选`

含义：

- 当前 shared 请求经过真实性过滤后，没有任何 backend 候选能真实消费。

排查：

1. 看 symbol、market 组合是否合理。
2. 看是不是把东方财富 `quote_id` 塞进 shared symbol 契约。
3. 看 command key 是否属于特殊受限命令，例如某些单标的命令。

### 13.5 `yfinance backend is unavailable because package ...`

含义：

- 本地没装 `yfinance` 依赖。

排查：

1. 安装对应依赖。
2. 或临时切回 `efinance` 或 `akshare`。

### 13.6 `Akshare backend is unavailable because package ...`

含义：

- 本地没装 `akshare` 依赖。

排查：

1. 安装对应依赖。
2. 或切回其他 backend。

### 13.7 observation 有结果，但指标缺失

常见原因：

- 历史回补不够。
- `indicator-level` 太低。
- 命令不在 observation 主模板支持链路里。
- 实时列表只回补了有限窗口。

排查：

1. 先把 `indicator-level` 提到 `full`。
2. 再把 `trace-window` 拉高到 128。
3. 若是高频 watch，检查是否因为成本考虑而降级了 level。

### 13.8 JSON 结构和你预期不一样

常见原因：

- 你把 observation payload 当成 raw。
- 你把 raw 包装当成统一固定 schema。
- 你假设 DataFrame、Series、dict 都会被包成同一种顶层对象。

排查：

1. 先确认 `--view`。
2. 再确认命令最终返回的是 `ObservationPayload`、`DataFrame`、`Series` 还是 raw shared wrapper。
3. 再回到 `rendering.py` 的真实序列化规则解释。

## 14. 对 agent 的推荐排障顺序

1. 先确认命令路径和参数是否真实存在。
2. 再确认这是不是 shared 命令。
3. 再确认程序真实默认值与本次推荐值有没有被混淆。
4. 再确认 symbol、market、quote_id 契约有没有错位。
5. 再确认 backend 是缺依赖、不可用，还是只是 auto 规划选错。
6. 最后才看 observation 或 rendering 层。

先把错误分层，再修，不要一上来盲目改参数组合。