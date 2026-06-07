## Context

当前仓库已经具备统一的 CLI 命令目录、请求 schema、backend 解析、执行器、结果物化、observation/enrichment 链路。CLI 入口主要由 `opentrade.commands` 构建，业务执行由 `opentrade.executor.CommandExecutor` 和 `opentrade.facade.CommandFacade` 完成，技术指标则集中在 `opentrade.indicators` 子包中。

现状问题不是“缺少业务能力”，而是“缺少一套对外稳定、易发现、易补全的 Python SDK 入口”。外部 Python 程序如果想复用 OpenTrade，只能直接 import 内部实现模块或退回 subprocess 调 CLI，这两种方式都不适合作为长期公共接口。

本次设计还需要满足几个明确约束：

- 顶层程序入口不做 `watch`。
- 新增 API 模块不平铺在根目录，要收敛到新的 package 中。
- 不引入懒导入、动态导出或其他弱化 IDE 体验的机制。
- `from opentrade import ...` 只保留最核心、最稳定、最清晰的入口。
- 技术指标维持子包导入边界，不混入顶层对象式 API。

## Goals / Non-Goals

**Goals:**

- 提供 `from opentrade import OpenTrade` 的稳定程序化入口。
- 让 `OpenTrade` 通过对象式命名空间覆盖现有 CLI 的主要业务能力域，如 `stock`、`fund`、`quote`、`search` 等。
- 程序化 API 复用当前 shared command 定义、schema 校验、backend 路由、执行和 enrichment 逻辑，保证语义与 CLI 等价。
- API 导出保持显式、直接，增强 IDE 自动补全与静态推理表现。
- 保持 `opentrade.indicators` 继续作为技术指标的专用导入子包。

**Non-Goals:**

- 不把 CLI 的 `watch` 包装层变成程序化 API。
- 不把 `format`、`output`、`transpose`、`no-index` 这类主要面向终端展示的参数继续暴露成核心程序接口。
- 不在本次引入插件化 SDK、动态命令发现、代码生成导出或多层抽象工厂。
- 不重新设计 provider 能力分层，也不重写现有 command catalog。

## Decisions

### 决策 1：新增 `opentrade.api` package，而不是把程序化 API 平铺到根包

采用 `opentrade.api` 作为新入口包，内部再按业务域拆分子模块，例如 `search.py`、`quote.py`、`stock.py`、`fund.py`、`bond.py`、`futures.py`、`market.py`、`resolve.py`。

理由：

- 与现有 `indicators`、`backends`、`enrichment` 的结构一致，便于维护。
- 避免把根包目录继续堆成杂糅入口层。
- 可以把内部运行时桥接逻辑收敛在 `api/_runtime.py`，不污染公共模块。

备选方案：

- 方案 A：直接在 `opentrade/` 根下新增大量 `api_*.py` 模块。
  - 放弃原因：根包会迅速失控，且不利于形成稳定公共接口边界。
- 方案 B：直接把已有 `commands.py` / `facade.py` 对外暴露。
  - 放弃原因：这些模块是 CLI/内部执行语义，不是面向 SDK 用户设计的 API。

### 决策 2：顶层只导出 `OpenTrade`，不提供函数式入口

`opentrade.__init__` 只显式 re-export `OpenTrade` 和版本等极少量稳定符号，不新增大批平铺函数。

理由：

- 顶层命名空间更干净，IDE 补全更聚焦。
- 避免未来命令数量扩张后顶层 API 失控。
- 与用户明确要求一致：不要函数式入口。

备选方案：

- 方案 A：同时提供 `OpenTrade` 和 `get_stock_price_history()` 这类函数式入口。
  - 放弃原因：会形成双轨 API，增加维护和文档负担。

### 决策 3：`OpenTrade` 使用对象式命名空间组织能力域

`OpenTrade` 作为根门面对象，暴露只读命名空间属性，例如：

- `OpenTrade.search`
- `OpenTrade.quote`
- `OpenTrade.stock`
- `OpenTrade.fund`
- `OpenTrade.bond`
- `OpenTrade.futures`
- `OpenTrade.market`
- `OpenTrade.resolve`

每个命名空间模块提供与 CLI 语义一一对应的方法，例如：

- `ot.search.instruments(...)`
- `ot.stock.price_history(...)`
- `ot.quote.price_latest(...)`
- `ot.resolve.quote_id(...)`

理由：

- 与 CLI 现有命令树自然对齐，迁移成本低。
- IDE 可通过对象层级逐步探索能力，比大批平铺函数更友好。
- 未来新增能力域时只需扩展一个命名空间，不影响顶层稳定性。

备选方案：

- 方案 A：一个 `OpenTrade.invoke("stock.price.history", ...)` 的字符串分发接口。
  - 放弃原因：虽然内部实现可用，但对调用方不够直观，也削弱类型提示与补全体验。

### 决策 4：程序化 API 复用执行链，但过滤掉 CLI 专属展示参数

程序化 API 的内部桥接层复用：

- `get_command_definition` / `get_shared_command_definition`
- `resolve_backend_selection`
- `validate_request_data`
- `CommandExecutor.invoke`

但对外方法签名只暴露真正影响业务结果的参数，例如：

- 业务请求字段
- `backend`
- `view`
- `indicator_level`
- `trace_window`
- `limit`

默认不把以下 CLI 专属展示能力作为 SDK 主接口：

- `watch`
- `format`
- `output_path`
- `encoding`
- `transpose`
- `no_index`
- `clear_screen`
- `count` / `interval`（watch 相关）

理由：

- 程序化 API 的职责是返回 Python 对象，而不是模拟终端输出行为。
- 这样可以减少调用方心智负担，并保持对象接口语义稳定。

备选方案：

- 方案 A：完整复制 CLI 运行时选项到每个程序化方法。
  - 放弃原因：会把展示层细节泄漏到 SDK，形成难维护、难理解的宽接口。

### 决策 5：技术指标继续留在 `opentrade.indicators` 子包，不并入 `OpenTrade`

`OpenTrade` 专注命令等价的数据访问与业务查询能力；技术指标继续通过：

- `from opentrade.indicators import macd`
- `from opentrade.indicators.trend import macd`

理由：

- 技术指标本质上是纯计算函数集合，与远程数据获取 API 的职责不同。
- 现有测试和导出结构已经围绕 `opentrade.indicators` 建立，不值得打散。
- 这也符合用户要求：指标放在 sub package 导入。

## Risks / Trade-offs

- [风险] API/CLI 结果语义看似等价，但程序化入口若绕过某些运行时默认值，可能导致返回形态与 CLI 不一致。  
  → 缓解：内部桥接统一走 `CommandExecutor.invoke`，并为关键命令补 API/CLI 对齐测试。

- [风险] 现有 command catalog 同时包含 shared command 和 provider extension，若一次性全量暴露，首版任务量会偏大。  
  → 缓解：设计上要求“覆盖 CLI 能力”，实现时按 shared command 优先，再有序补齐 provider extension。

- [风险] 顶层只暴露 `OpenTrade` 虽然清晰，但会让个别用户觉得少了快捷入口。  
  → 缓解：在 README 和 docstring 中强化对象式入口的 discoverability。

- [风险] 部分现有文件的中文编码展示存在历史异常，新增 API 文档和注释若处理不当可能继续放大编码问题。  
  → 缓解：所有新增文件统一使用 UTF-8 without BOM，并在实现阶段做编码校验。

- [权衡] 不暴露 `format` / `output` 等 CLI 参数会让程序化 API 与 CLI 参数表不完全一一映射。  
  → 这是有意为之，因为 import API 追求的是“能力等价”，不是“参数表逐字克隆”。
