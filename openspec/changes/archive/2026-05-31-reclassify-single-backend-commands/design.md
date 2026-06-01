## Context

当前多后端架构已经完成三件关键工作：

- 命令树已经从“第三方函数驱动”迁到显式 command catalog；
- backend 解析已经支持共享命令默认 backend 与 provider-extension 命令默认 provider；
- 扩展命令也已经可以挂到稳定业务语义路径，而不是必须暴露 provider 顶层根组。

但命令分类仍存在一个明显不一致点：`shared` 里混入了大量只有 `efinance` 支持的命令。现状可以直接在 `command_catalog.py` 中看到：

- `stock.price.history`、`stock.price.live`、`stock.profile`、`fund.nav.history` 和 `instrument.search` 被视为多 backend 共享命令；
- 其余大部分 `stock` / `fund` / `bond` / `futures` / `quote` / `market` / `resolve` 命令虽然只有 `efinance` 支持，仍然被注册为 `CommandKind.SHARED`。

这会带来三个问题：

1. `shared` 不再等于“真正可切换 backend 的命令”，语义失真；
2. provider-extension 只覆盖极少数命令，无法真实表达单 provider 命令面的规模；
3. 后续接入 `yfinance` 时，无法仅凭命令分类判断哪些命令应该扩大支持矩阵，哪些应该继续作为 provider-extension 存在。

用户已经明确给出新的硬规则：所有单后端支持的命令全部都是 `provider-extension`。因此，这次 change 的目标不是新增命令，而是重整内部命令分类边界。

## Goals / Non-Goals

**Goals:**

- 让 `shared` 恢复为“多 backend 共享命令”的严格语义。
- 把所有单 backend 命令统一归类为 `provider-extension`。
- 尽量在不打散业务语义命令树的前提下完成内部重分类。
- 让 resolver、provider registry、执行主链、测试和文档都围绕同一分类规则收敛。

**Non-Goals:**

- 不要求这次 change 同时扩大任何命令的 backend 支持矩阵。
- 不要求所有迁移命令都改 CLI 路径或改帮助文案到完全不同的用户入口。
- 不在本轮重新设计结果契约或 enrichment / observation 数据结构。
- 不在本轮实现 `yfinance` provider，本 change 只负责先把命令分类边界理顺。

## Decisions

### 决策一：`shared` 的判断标准改为“支持矩阵至少包含两个 backend”

今后的命令分类规则将明确为：

- `supported_backends` 数量大于 1 的命令，才允许归类为 `CommandKind.SHARED`
- `supported_backends` 数量等于 1 的命令，必须归类为 `CommandKind.PROVIDER_EXTENSION`

这条规则不再按资产域、utility 入口或用户是否常用来做例外。

原因：

- 它把分类规则从“命令长什么样”收敛为“能力是否真的多后端共享”；
- 这比维护人工白名单更稳定、更可测试；
- 也能直接给后续 provider 扩展提供清晰边界。

备选方案：

- 继续允许某些单 backend 命令留在 shared，只要它们未来“可能”变成多 backend。放弃，因为这正是当前语义漂移的根源。

### 决策二：重分类优先改变内部归属，不强制改变用户业务路径

迁出的单 backend 命令不必都改成 `efinance ...` 顶层路径，而是可以继续挂在现有业务语义路径下，例如：

- `bond catalog`
- `quote profile`
- `market add`

但它们在内部必须变成某个 provider 的 extension command。

原因：

- 你的新规则针对的是“命令类别”，不是“用户一定要看到 provider 名称前缀”；
- 现有命令树已经完成了一轮去 provider 顶层暴露的收敛；
- 维持业务路径稳定，可以避免这次 change 演变成不必要的大规模 CLI 改名。

备选方案：

- 所有 provider-extension 都必须搬到 `efinance ...` 或 `akshare ...` 根组。放弃，因为这会与既有 `unify-backend-command-surface` 的方向冲突。

### 决策三：批量迁移 `efinance` 单 backend 命令到 provider registry

当前大部分单 backend 命令都来自 `efinance`，因此实现上会：

- 缩小 `SHARED_COMMANDS`，只保留真正双 backend 命令；
- 为 `efinance` provider 批量注册这些原先的单 backend 命令为 extension_commands；
- 保持它们原有的 capability、request schema 和 result contract 绑定，避免无关行为变化。

原因：

- 这是最小变更路径；
- 命令语义、schema 和执行逻辑本来就已经存在，问题只在分类和装配位置；
- 可以把风险集中在 catalog / registry / help / 测试，而不是 handler 实现。

备选方案：

- 为单 backend 命令再设计一层“semi-shared”类别。放弃，因为这会直接违背用户刚确认的新硬规则。

当前盘点得到的单 backend 基线命令清单如下，后续新增仅支持单 backend 的命令也必须遵循同样归类：

- `search.local`
- `stock.constituents`
- `stock.flow.history`
- `stock.flow.today`
- `stock.holders.latest-count`
- `stock.holders.top10`
- `stock.ipo.latest`
- `stock.leaderboard.daily`
- `stock.performance.quarterly`
- `stock.price.latest`
- `stock.price.snapshot`
- `stock.report-dates`
- `stock.sector`
- `stock.trades`
- `fund.allocation.industry`
- `fund.allocation.position`
- `fund.allocation.types`
- `fund.catalog`
- `fund.disclosure.dates`
- `fund.estimate.live`
- `fund.managers`
- `fund.nav.history-batch`
- `fund.performance.period`
- `fund.profile`
- `fund.reports.download`
- `bond.catalog`
- `bond.flow.history`
- `bond.flow.today`
- `bond.price.history`
- `bond.price.live`
- `bond.profile`
- `bond.trades`
- `futures.catalog`
- `futures.price.history`
- `futures.price.live`
- `futures.trades`
- `quote.flow.history`
- `quote.flow.today`
- `quote.price.history`
- `quote.price.latest`
- `quote.profile`
- `quote.trades`
- `market.add`
- `market.price.live`
- `resolve.quote-id`

### 决策四：resolver 继续保留 provider-extension 默认 backend 路由

单 backend 命令迁成 provider-extension 后，默认路由语义继续是：

- 用户未显式传入 `--backend` 时，自动解析到该 extension 所属 provider；
- 用户显式传入错误 backend 时，执行前直接报错。

原因：

- 现有 resolver 已经具备这条语义；
- 重分类后，这反而会成为大量单 backend 命令的统一运行时行为；
- 用户不需要为“实际上只有一个 backend 的命令”重复传入同样的 backend。

备选方案：

- 要求所有 provider-extension 命令都显式传 `--backend`。放弃，因为会增加样板调用成本，且没有额外信息价值。

### 决策五：测试与文档必须把“单 backend 命令即 provider-extension”固化下来

这次 change 不能只改实现，还需要把新规则转成可守护约束：

- 测试中检查 shared catalog 只包含多 backend 命令；
- 测试中检查单 backend 命令全部能从所属 provider 的 extension_commands 找到；
- 文档中不再把单 backend 命令描述为 shared；
- 后续新增命令时，分类错误应能被测试直接拦住。

原因：

- 否则这条规则很快又会退化成“约定俗成但没人守”；
- 这是命令面治理规则，最适合用测试和 spec 双重固化。

## Risks / Trade-offs

- [风险] 虽然 CLI 路径可保持稳定，但内部重分类会影响大量测试和装配逻辑。 → 缓解：优先保持 capability、schema、路径和 handler 不变，只调整 catalog / registry / 断言。
- [风险] 如果某些命令未来会扩展到多 backend，先迁成 provider-extension 可能需要再次迁回 shared。 → 缓解：接受这种可逆迁移成本，优先保证当前语义正确。
- [风险] 现有文档可能默认把很多业务路径视为 shared。 → 缓解：在本轮同步更新架构说明与 CLI 使用说明，避免文档继续放大旧语义。
- [风险] 与刚创建的 `add-yfinance-backend-support` 提案存在依赖关系。 → 缓解：明确这次 change 先于 `yfinance` 接入实现，后者按新分类规则继续推进。

## Migration Plan

1. 先收窄 shared catalog，仅保留当前真正双 backend 命令。
2. 把其余单 backend 命令迁入所属 provider 的 extension_commands。
3. 调整命令装配逻辑，确保这些 extension 仍挂到原有业务语义路径。
4. 更新 resolver / help / regression tests / scaffold tests，固化新规则。
5. 最后更新文档，并让后续 `yfinance` 接入提案按新分类边界继续实施。

回退策略：

- 如果批量迁移导致命令挂载异常，可以暂时回退部分命令到旧 catalog，但不能回退“shared 允许单 backend”的规则结论；
- 更安全的回退方式是分组迁移，如先迁 utility，再迁 bond / futures，再迁 quote / fund。

## Open Questions

- `search local` 是否保留为顶层 `search` 组下的 provider-extension，还是进一步并入 `instrument.search` 旁支？
- 对于未来新接入的 `yfinance` 单 backend 命令，是否要求命令定义阶段就禁止进入 shared builder，而不是靠测试事后发现？
- 是否需要在帮助文本中显式展示“该命令虽然走业务语义路径，但内部属于 provider-extension”？
