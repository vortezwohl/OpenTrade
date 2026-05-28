# 架构与排障参考

## 1. 真实执行链路

当前真实链路是：

1. `efinance_cli.main`
2. `efinance_cli.app.create_cli`
3. `efinance_cli.commands`
4. `efinance_cli.registry`
5. `efinance_cli.introspection`
6. `efinance_cli.executor.CommandExecutor`
7. `efinance_cli.retry_utils`
8. `efinance_cli.enrichment.service`
9. `efinance_cli.observation`
10. `efinance_cli.rendering`
11. 上游 `efinance.*`

理解重点：

- `registry.py` 决定命令树暴露什么能力，以及自然语义化路径长什么样。
- `introspection.py` 把上游签名改写成统一 option 风格，而不是继续照搬原始函数命名。
- `retry_utils.py` 只包网络相关异常，不负责整条 CLI 流程重试。
- `observation.py` 位于增强层与渲染层之间，负责把可支持的结果组装成 observation payload。
- `rendering.py` 负责 boxed table、JSON、CSV、TSV 的最终输出。

## 2. 真实默认值 vs skill 推荐值

### CLI 程序真实默认值

- `--format table`
- `--indicator-level advanced`
- `--view observation`
- `--trace-window 32`

### skill 面向 agent 的推荐值

- `--format json`
- `--indicator-level full`
- `--trace-window 128`

结论：

- 如果用户问“默认是什么”，必须回答真实默认值。
- 如果用户问“agent 最稳妥怎么调用”，可以推荐 `json + full + 128`，但必须注明是 skill 推荐值。

## 3. 当前真实命令树

当前顶层是：

- `stock`
- `fund`
- `bond`
- `futures`
- `quote`
- `market`
- `resolve`
- `search`
- `watch`

关键变化：

- 旧 `common` 命令已折叠进 `quote` / `market`
- 旧 `utils get-quote-id` 已变成 `resolve quote-id`
- 顶层 `search` 是手写包装命令
- 顶层 `watch` 是参数转发包装器

## 4. observation 契约

### 4.1 默认视图已是 observation

当前命令默认就是：

```bash
--view observation
```

因此：

- 如果不显式传 `--view raw`，终端默认看到的是结构化 observation。
- README、skill、样例和排障都应优先按 observation 心智理解。

### 4.2 observation payload 结构

典型 observation payload 包含：

- `meta`
- `latest_quote`
- `current_metrics`
- `trace_points`
- `recent_events`
- `sections`

其中：

- `meta` 记录模块、函数、视图、指标等级、trace window、标的与时间点
- `latest_quote` 是当前主行情字段
- `current_metrics` 是增强后的关键指标快照
- `trace_points` 是近若干 bar 的轨迹块
- `recent_events` 是多指标事件检测结果
- `sections` 是通用 observation 的补充结果

### 4.3 observation table 行为

table 模式下不会渲染成单个宽 DataFrame，而是 boxed section：

- `meta`
- `latest_quote`
- `current_metrics`
- `trace_points.<group>`
- `recent_events`
- `result[n]`
- `source.<key>`

### 4.4 observation JSON 行为

JSON 模式直接输出 payload 本身，不会外包统一 envelope。

如果是多 source observation，例如 `fund nav history-batch`，JSON 形态通常是：

```json
{
  "161725": { "...payload..." },
  "005827": { "...payload..." }
}
```

## 5. JSON 真实序列化规则

`--format json` 的真实规则是：

- `DataFrame -> records 数组`
- `Series -> object`
- `dict -> 递归 object`
- `list/tuple/set -> array`
- dataclass -> `asdict`
- namedtuple -> `_asdict`
- `None -> null`
- 其他类型 -> `default=str`

因此：

- 不要发明固定顶层 schema
- 不要假设所有命令都返回统一字段集合
- observation payload 只是一类返回值形态，不是所有命令的统一包裹层

## 6. search 与 watch 的特殊性

### 6.1 search

顶层 `search` 不是普通动态命令，而是手写包装：

- 业务调用核心仍是 `efinance.utils.search_quote`
- 结果会优先转成 `DataFrame`
- 默认也会走 observation 渲染
- `--result-count` 是业务参数，不是 watch 刷新次数

所以：

- `search --format json` 的真实输出更接近“候选项 observation payload”
- 不能把它解释成旧 `utils search-quote` 的原始 namedtuple 直出

### 6.2 watch

`watch` 是顶层参数转发器：

- 接收 `--interval` / `--count` / `--clear`
- 后面必须跟完整子命令
- 它会把这些参数追加到目标子命令，再交给根命令重跑

## 7. 网络重试边界

当前 `retry_utils.py` 的要点：

- 只针对网络相关异常
- 当前上限是 `8` 次重试
- 典型覆盖异常：`urllib3` HTTP 错误、`OSError`、`IncompleteRead`、`BadStatusLine`
- 不会把参数错误、渲染错误、Click 解析错误纳入重试

排障判断：

- 如果报错发生在参数解析阶段，不属于重试范围
- 如果报错是上游远端波动或底层连接异常，优先怀疑网络层
- 如果 observation 有结果但指标缺失，先看增强层，不要先怀疑 retry

## 8. 常见失败分层

### 8.1 参数层

现象：

- 未知参数
- 缺少必填参数
- 枚举值错误
- `watch` 后没跟完整子命令

优先动作：

- 先查 `command-catalog.json`
- 再核对当前帮助页

### 8.2 命令树层

现象：

- 用户还在用旧命令，如 `common get-latest-quote`
- 旧参数名仍在被使用，如旧式位置参数或旧别名

优先动作：

- 先把旧命令映射到当前自然语义路径
- 再核对 `registry.py` 的真实 `cli_path`

### 8.3 上游数据源层

现象：

- 超时
- 限流
- 空结果
- 字段变动

优先动作：

1. 原命令重试 1 到 3 次
2. 拉长 watch 间隔
3. 把 `indicator-level` 从 `full` 降到 `advanced` 或 `basic`
4. 若用户只需要解析标的，先退回 `search -> resolve quote-id`

### 8.4 observation / 增强层

现象：

- 原始结果有，但 observation 某个 section 为空
- `current_metrics` 字段不全
- `trace_points` 比预期短
- `recent_events` 为空

优先动作：

1. 确认命令是否在 observation 支持范围内
2. 确认 `trace-window` 是否设得过小
3. 确认历史回补是否成功
4. 确认指标等级是否足够

### 8.5 渲染层

现象：

- 文件输出失败
- CSV/TSV 列结构与预期不同
- JSON 结构与调用方想象不符

优先动作：

- 按真实序列化规则解释
- 不要拿假定 schema 硬套
- 若调用方要稳定字段，优先建议 observation JSON 而不是 raw table

## 9. 兼容层说明

`fund profile` 走的是本地兼容封装，不完全等于直接调用上游原始函数。

原因：

- 为了处理 pandas / dtype 兼容性问题

结论：

- 看到该命令行为与上游函数略有差异时，先怀疑兼容层，而不是误判为命令文档写错。
