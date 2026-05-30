## Context

当前 `efinance-cli` 已具备命令构建、统一执行、增强、观察和渲染等分层，但这些分层的稳定对象仍是 `efinance` 上游函数，而不是面向用户的命令语义或面向系统的能力契约。具体表现为：

- 命令注册中心直接维护 `efinance` 子模块与函数白名单。
- CLI 参数主要从第三方函数签名动态反射生成。
- 执行层调用对象仍是第三方函数或其兼容包装器。
- enrichment 直接回补 `efinance.*.get_quote_history`。
- observation 对字段别名、命令键和历史回补路径存在隐式依赖。

在这个结构下，`akshare` 无法作为一等后端干净接入，未来的 `yfinance` 也无法以稳定方式挂载。更关键的是，当前系统默认假设“命令语义 = 上游函数语义”，这与本次变更的前提冲突：

- 不再以旧版本命令兼容为目标；
- 共享界面应尽可能后端无关；
- 后端能力差异与专属命令是合法且需要被良好建模的；
- 未来可能继续接入 `yfinance`，但不能现在就为了它引入失控抽象。

因此，这次设计不是“在现有 `efinance` CLI 外面再套一个 `akshare` adapter”，而是重建以下稳定对象：

- 命令目录；
- 能力描述；
- 请求契约；
- 结果契约；
- provider 架构；
- 执行骨架。

## Goals / Non-Goals

**Goals:**

- 建立以后端无关命令语义为核心的共享命令层。
- 建立可持续扩展到 `efinance`、`akshare`、未来 `yfinance` 的 provider 架构。
- 显式建模后端能力差异、支持矩阵和 provider-specific 扩展命令。
- 让 enrichment、observation、rendering 优先依赖标准结果契约，而不是具体 provider。
- 用有限、可解释的设计模式管理真实变化点，避免继续把复杂度堆在命令层条件分支中。

**Non-Goals:**

- 不要求所有 provider 都实现完全相同的能力集合。
- 不要求所有共享命令的所有字段在不同 provider 下完全同构。
- 不在本轮引入插件市场、动态远程安装 provider 或复杂 DI 容器。
- 不在本轮实现 `yfinance` provider。
- 不在本轮试图一次性重写所有现有业务能力；首批只要求建立稳定骨架并迁移代表性共享能力。

## Decisions

### 决策一：以显式命令目录替代函数驱动注册模型

系统将引入显式的 `CommandDefinition`，由它定义：

- 稳定命令键，如 `equity.price.history`；
- CLI 路径，如 `equity price history`；
- 命令类别，如 `shared` 或 `provider-extension`；
- 绑定 capability 标识；
- 请求 schema；
- 支持的输出模式；
- 是否允许 watch；
- 支持矩阵提示与帮助元数据。

共享命令的参数定义不再来自第三方函数签名，而来自命令自己的请求 schema。

这样做的原因：

- 命令语义终于可以独立于 `efinance` / `akshare` / `yfinance` 的真实函数签名。
- CLI 变成“声明式命令目录驱动”，而不是“反射上游函数驱动”。
- 可以统一定义参数别名、必填项、默认值、取值域和帮助文本，而不受第三方库不一致的命名风格牵制。

备选方案：

- 继续从 provider handler 的函数签名反射参数。放弃，因为这只是把当前耦合从 `efinance` 挪到另一个对象上，问题本质不变。

### 决策二：采用 `BackendProvider + CapabilityHandler`，而不是全能型 Backend 接口

系统将引入：

- `BackendProvider`：描述一个 provider 的身份、能力集合、扩展命令、配置与 handler 获取方式；
- `CapabilityHandler`：负责单个 capability 或一组紧邻 capability 的请求翻译、上游调用、异常收束和结果标准化；
- `BackendResolver`：按 `--backend`、默认后端策略或命令约束选择 provider；
- `CapabilityRegistry`：管理 capability 描述与 provider 支持矩阵。

这样做的原因：

- 不同 provider 的能力天然不完整，胖接口只会制造大量 `NotImplemented`。
- `akshare` 与未来 `yfinance` 的强项不同，按 capability 拆分更自然。
- 单能力 handler 更易测试，也更容易做合同测试与局部替换。

备选方案：

- 定义一个包含几十个方法的 `MarketBackend` 抽象类。放弃，因为这会把“支持矩阵”伪装成“统一接口”，长期会失真。

### 决策三：共享命令与 provider 扩展命令分离建模

命令目录将分为两类：

- `shared`：后端无关的业务语义命令；
- `provider-extension`：仅由特定 provider 暴露的专属命令组。

共享命令的原则是“语义稳定、结果契约稳定、允许字段与能力存在受控差异”。  
扩展命令的原则是“能力真实、边界清楚、不伪装成共享语义”。

这样做的原因：

- 避免为了统一而强行压缩 provider 独有能力。
- 让用户在帮助页和执行期都能看清“哪些是共享能力，哪些是后端扩展”。
- 让 `akshare` 的宏观、行业、期权等独有价值能正常释放。

备选方案：

- 把所有命令都塞进统一树，只靠帮助文本说明 backend 差异。放弃，因为 discoverability 差，运行时约束也会混乱。

### 决策四：按 capability 建立结果契约，而不是一张全局万能数据表

系统将按能力定义结果契约，例如：

- `HistoryBarsContract`
- `RealtimeQuotesContract`
- `ProfileContract`
- `SearchResultsContract`

每个契约至少包含：

- 必需字段；
- 可选字段；
- 字段类型与语义；
- 原始 provider payload 保留区；
- provider 扩展字段保留区；
- observation / enrichment 可依赖的核心字段集。

标准化层将按 capability 实现，而不是做一个巨大的万能标准化器。

这样做的原因：

- 不同能力的数据形状差异远大于同一能力在不同 provider 之间的差异。
- observation 和 enrichment 真正需要的是“可依赖的核心字段”，不是无限制的全字段统一。
- 允许 provider 保留原始字段和扩展字段，可减少过度裁剪造成的信息损失。

备选方案：

- 设计单一全局标准表头。放弃，因为会把复杂度转移到大量空字段、条件分支和字段语义歧义上。

### 决策五：执行骨架继续保留，但调用对象改为 facade

系统将保留统一执行骨架，并把其稳定步骤固化为：

1. 解析 CLI 命令并生成标准请求对象；
2. 解析目标 backend；
3. 检查命令与 capability 是否被该 backend 支持；
4. 通过 `CommandFacade` 路由到目标 capability handler；
5. 返回标准结果契约；
6. 执行 enrichment；
7. 构建 observation；
8. 执行 rendering 与输出；
9. 在 watch 模式下重复同一骨架。

这对应的模式是：

- `Facade`：屏蔽 provider 细节；
- `Strategy`：运行时后端选择；
- `Template Method`：固定执行步骤；
- `Proxy/Decorator`：能力检查、重试、限流、追踪、缓存等横切逻辑。

备选方案：

- 把 provider 判定和标准化散落到命令回调中。放弃，因为这会重新把复杂度带回命令层。

### 决策六：enrichment 与 observation 只依赖结果契约与补充接口

`enrichment` 不再通过 `module_name` 直接调用某个 provider 的历史函数。  
取而代之，将引入专门的补充接口，例如：

- `history_for_enrichment`
- `history_lookup_key`
- `quote_identity`

这些接口由 capability handler 或共享辅助组件提供，返回标准历史契约。

`observation` 也将优先消费标准字段，而不是维护无边界的 provider 原始字段别名集合。短期允许兼容映射存在，但长期目标是“兼容逻辑下沉到标准化层”。

这样做的原因：

- 不把 `akshare` / `yfinance` 接入后又偷偷回退到 `efinance` 做增强。
- 让增强与观察链真正成为后端无关的共享中间层。

备选方案：

- 为每个 provider 在 observation/enrichment 中继续堆字段特判。放弃，因为这会造成横向耦合失控。

### 决策七：首批迁移不追求覆盖面，而追求闭环代表性

首批实施只要求选出最能验证架构闭环的共享能力：

- 一类历史行情；
- 一类资料信息；
- 一类搜索；
- 可选一类实时行情。

更具体地，建议首批优先级为：

1. `instrument.search`
2. `equity.price.history`
3. `equity.profile`
4. `fund.nav.history`
5. 在前四项稳定后再接 `equity.price.live`

这样做的原因：

- 搜索验证“共享命令 + 请求 schema + 标准结果”的最小闭环；
- 历史行情验证“结果契约 + enrichment + observation”的核心主链；
- 资料信息验证“弱行情字段 + 历史回补”的边界；
- 实时行情最复杂，放在后面更稳。

备选方案：

- 一开始就迁移所有 shared 命令。放弃，因为失败半径过大，难以验证和回退。

## Risks / Trade-offs

- [风险] 这是显式破坏性重构，命令树和帮助页会发生较大变化。 → 缓解：在 proposal、design 和后续 CLI 文档中明确标记 BREAKING，并用能力目录而不是旧函数映射作为新的稳定界面。
- [风险] 如果共享命令抽象过粗，会压扁 provider 差异；抽象过细，又会失去共享价值。 → 缓解：采用“共享命令树 + provider 扩展命令树”的双层结构。
- [风险] capability 过度拆分会导致目录和测试数量快速增长。 → 缓解：按真实数据形状与用户语义分组，不按上游函数数量逐一建 capability。
- [风险] observation / enrichment 从原始字段迁移到契约字段期间，可能出现临时双轨复杂度。 → 缓解：先定义核心字段契约，再逐步把兼容映射下沉，不追求一步到位清空旧逻辑。
- [风险] 未来引入 `yfinance` 时，地域与市场语义差异可能比 `efinance` / `akshare` 更大。 → 缓解：当前只预留 provider 架构与扩展命令机制，不为未知能力预先设计大而全抽象。

## Migration Plan

1. 引入新命令目录、provider 架构、请求契约与结果契约，但先不迁移所有现有能力。
2. 用 `efinance` 实现首批共享 capability handler，验证新骨架在单 provider 下稳定可用。
3. 为同一批 capability 接入 `akshare` handler，并补充合同测试。
4. 改造 enrichment 与 observation，使其通过契约与补充接口工作。
5. 引入 provider 扩展命令目录，先为 `akshare` 建立一组示范性扩展命令。
6. 在共享命令与扩展命令稳定后，再逐步迁移其余命令或删除旧命令注册路径。

回退策略：

- 每个 capability 独立迁移，若某 capability 在新骨架下不稳定，可只回退该 capability 的目录与 handler 绑定，而不是整体回滚。
- 在首批共享能力未完成前，不要求一次性删除所有旧实现，可保留过渡期内部分支；但对外不承诺旧命令兼容。

## Open Questions

- 共享根命令组是否继续采用 `stock/fund/bond/futures` 这一资产类别组织，还是直接升级为更抽象的 `equity/fund/fixed-income/derivatives`？
- 默认 backend 策略是否首版就支持环境变量与配置文件，还是仅保留显式 `--backend`？
- provider 扩展命令是否需要统一前缀，例如 `akshare macro ...`，还是允许 provider 将扩展命令挂到共享树下的扩展分支？
- 结果契约是否需要引入专门的 `completeness` 元信息，以描述某 provider 在某 capability 下的字段完整度？
- `yfinance` 未来接入时，是否允许作为可选依赖按需安装，而不是项目的默认依赖？
