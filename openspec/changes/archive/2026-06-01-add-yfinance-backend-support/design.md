## Context

当前代码库已经完成“多后端能力骨架”建设：

- `BackendName` 枚举已经包含 `YFINANCE`；
- `list_optional_provider_names()` 已把 `yfinance` 标记为预留 provider；
- `CommandExecutor -> CommandFacade -> BackendProvider -> CapabilityHandler` 的执行主链已经稳定；
- 共享命令的 schema、结果契约、observation 和 rendering 已经围绕标准结果工作；
- 现有正式 provider 仍只有 `efinance` 与 `akshare`；
- 单 backend 命令重分类已经归档完成，后续新增仅由 `yfinance` 支持的命令必须直接建模为 `provider-extension`。

这也意味着本 change 的起点已经比最早提案时更清晰：

- 命令分类边界已经稳定，不需要再讨论“是否允许单 backend 命令继续挂在 shared catalog”；
- `add-auto-backend-routing` 仍未实现，因此首轮 `yfinance` 接入必须先围绕显式 `--backend yfinance` 路径闭环；
- 只要 `yfinance` 还未正式注册，未来的 `auto` 候选链就应该跳过它，而不是假设它已经可执行。

本轮调研基于项目 `.venv` 中已安装的 `yfinance==1.4.1` 源码完成，重点事实如下：

- 搜索入口是 `yfinance.search.Search`，返回 `quotes/news/lists/research/nav` 多类结果；
- 历史行情入口是 `Ticker.history()` 与批量 `download()`，底层统一走 `PriceHistory`；
- 快照与资料面分成 `FastInfo`、`Quote.info`、`history_metadata` 等不同对象；
- 基金画像走 `FundsData`，能提供概览、费率、资产配置、前十大持仓、债券评级、行业权重；
- 实时流走 `live.WebSocket` / `AsyncWebSocket`，与当前 CLI 的同步轮询式 `watch` 不是一回事；
- 真实运行验证中，`Search`、`Ticker.history()`、`FastInfo`、`FundsData` 都可能直接抛出 `YFRateLimitError`，说明 Yahoo 限流必须被视作一等设计约束。

## Goals / Non-Goals

**Goals:**

- 让 `yfinance` 成为当前架构下的正式 backend，而不是文档里的 future placeholder。
- 为共享命令建立一组“真实可维护”的 `yfinance` 支持面，而不是名义支持。
- 把 `yfinance` 的历史、快照、资料面、基金资料与搜索能力映射到现有标准结果契约。
- 为 Yahoo 限流、字段缺失和市场语义差异建立显式 guardrails。
- 把不适合共享抽象的 Yahoo 能力收敛到 provider-extension 命令组。
- 严格遵循“单 backend 命令必须是 provider-extension”的现行命令分类规则。

**Non-Goals:**

- 不要求 `yfinance` 覆盖当前所有共享命令。
- 不在本轮把 WebSocket 流式订阅重构进现有 `watch` 主链。
- 不承诺所有 `yfinance` 支持的 Yahoo 页面能力都被 CLI 暴露。
- 不为了 `yfinance` 牺牲现有共享 schema 的稳定性，去把整个命令面重写成 Yahoo 原生参数语义。
- 不以“静默回退到其他 backend”作为 `yfinance` 不支持场景的兼容策略。
- 不在本轮顺手实现 `auto` 默认路由或多 backend failover，那属于 `add-auto-backend-routing` 的范围。

## Decisions

### 决策一：共享命令支持按“最小稳定闭环”分层接入

`yfinance` 的共享支持不会一次性铺满所有命令，而是分三层：

1. 第一层，必须接入：
   - `instrument.search`
   - `stock.price.history`
   - `stock.profile`
   - `fund.nav.history`
   - `fund.profile`
   - `quote.price.history`
   - `quote.price.latest`
   - `quote.profile`
2. 第二层，条件接入：
   - `fund.nav.history-batch`
   - `stock.price.latest`
   - `stock.price.snapshot`
3. 第三层，明确不纳入首轮共享支持：
   - `bond.*`
   - `futures.*`
   - `market.price.live`
   - 国内市场专属 flow / trades / report-dates / disclosure 等 Yahoo 无稳定对应的数据面

### 决策二：历史类能力统一优先走 `Ticker.history()`，批量历史按受控方式使用 `download()`

设计上将优先把单标的历史统一到 `Ticker.history()`：

- `stock.price.history`
- `quote.price.history`
- `fund.nav.history`

只有在共享命令已经天然是批量语义、且验证过返回 shape 可稳定物化时，才允许受控引入 `download()`。

### 决策三：最新价 / 快照能力拆成 `FastInfo` 优先，`Quote.info` 兜底

`yfinance` 的实时近似能力不应直接等同于 `live.WebSocket`。共享命令中的 `quote.price.latest`、可能的 `stock.price.latest` / `snapshot` 将采用：

- 首选 `FastInfo` 的 `lastPrice/open/dayHigh/dayLow/lastVolume/marketCap/...`
- 必要时从 `history_metadata` 与 `Quote.info` 补 `currency/market/exchange/quoteType/shortName`
- 明确把其语义定义为“最近一次 Yahoo 提供的快照”，而不是强实时 streaming

### 决策四：资料面分成股票资料与基金资料两条标准化路径

`stock.profile` / `quote.profile` 与 `fund.profile` 不能复用一套粗糙映射：

- 股票 / 普通 quote 资料面来自 `Quote.info`、`history_metadata`、必要时补 `FastInfo`
- 基金资料面来自 `FundsData`，优先暴露 fund overview、operations、asset classes、top holdings、bond ratings、sector weightings

### 决策五：Yahoo 专属高价值能力进入 provider-extension，而不是继续扩张共享命令

以下类型能力优先定义为 `yfinance` 扩展命令：

- 新闻 `Ticker.news`
- 期权链 `Ticker.option_chain()`
- 基金前十大持仓 / 资产配置 / 债券评级 / 行业权重的细分视图
- 后续可能的 earnings calendar、recommendations、analyst targets

补充约束：

- 若某个新增命令当前仅由 `yfinance` 单独支持，它必须直接定义为 provider-extension；
- 只有真实支持至少两个 backend 的命令，才允许进入 shared catalog；
- 不允许为了“未来也许会多 backend”而先把单 backend 命令挂成 shared 占位。

### 决策六：限流与不完整市场覆盖必须进入运行时 guardrails，而不是藏在重试里

本轮会显式定义 `yfinance` runtime guardrails：

- 识别并保留 `YFRateLimitError` 语义；
- 在结果或错误信息中指明“Yahoo rate limited”，而不是只报通用网络错误；
- 对共享命令帮助与文档补充“全球市场更友好，中国本地数据能力有限”的说明；
- 对未支持命令返回明确 backend 不支持错误，不走 fallback；
- 对字段缺失走“契约级最小成功 + provider_fields 保留 + observation 降级”，而不是伪造字段。

## Risks / Trade-offs

- [风险] Yahoo 限流会让自动化测试和手工验证不稳定。 → 缓解：provider 层主测 contract/unit tests，以 mock/fake payload 为主；少量 live smoke test 标记为可选或手工。
- [风险] `yfinance` 的全球 symbol 语义与现有 `market_type` / 国内代码习惯不一致。 → 缓解：新增 `yfinance` 专属请求归一化层，明确哪些共享参数可映射、哪些命令只接受 Yahoo ticker / quote id。
- [风险] 基金资料面比现有 `profile-info` 契约 richer，直接压平会丢信息。 → 缓解：扩展结果契约或允许 provider_fields 挂载结构化子块，并让 raw / observation 都可见。
- [风险] 如果过早把 WebSocket 纳入共享实时链，会把执行模型复杂化。 → 缓解：首轮只承诺快照式 latest/quote 支持，把 streaming 放到扩展命令或后续变更。
- [风险] 用户可能期待 `yfinance` 覆盖 bond / futures / 中国市场专属命令。 → 缓解：在支持矩阵、帮助文本、错误信息和文档中显式标记不支持范围。

## Migration Plan

1. 在 provider 注册表中正式接入 `yfinance`，补齐依赖探测、backend 解析和帮助展示。
2. 先实现搜索、历史、股票资料、基金历史、基金资料、quote latest/profile 这组最小闭环 handler。
3. 为 `yfinance` 增加契约测试与标准化测试，确保输出能进入现有 enrichment / observation / rendering 主链。
4. 增加 Yahoo 专属扩展命令组，把新闻 / 期权链 / 基金画像等高差异能力从共享命令面隔离出来。
5. 最后再视稳定性评估是否扩大 `stock.price.latest`、`snapshot`、`history-batch` 等条件支持面。

实施顺序补充：

- 第一步必须先让 `--backend yfinance` 在 provider 注册、解析、执行、标准化和错误处理链路上闭环；
- 只有在显式 backend 路径稳定后，后续 `add-auto-backend-routing` 才能把 `yfinance` 纳入默认候选链。

回退策略：

- 若 `yfinance` 正式 provider 不稳定，可在不影响 `efinance` / `akshare` 的前提下，仅回退其 provider 注册与命令支持矩阵声明；
- 若某个共享 capability 标准化失败，可单独撤回该 capability 对 `yfinance` 的支持，而不必整体删除 `yfinance` backend。

## Open Questions

- `fund.profile` 是否应扩展出新的共享结果契约，还是先通过 `profile-info + provider_fields` 过渡？
- `quote.price.latest` 在 `yfinance` 下是否要接受批量 symbol 输入，还是首轮只保证单标的稳定输出？
- `instrument.search` 是否需要新增 `classify -> market` 的 Yahoo 专属映射表，来改善搜索结果到后续命令的衔接？
- provider-extension 命令树是挂到 `quote` / `fund` / `stock` 现有根组下，还是为 `yfinance` 定义一组更显式的扩展子路径？
