## Context

当前仓库的多 backend 结构在方向上已经引入了 BackendProvider、CapabilityHandler、CommandFacade、auto planner 这些分层，但关键边界仍然不干净。

第一，opentrade/backends/providers.py 目前同时承担了至少五类职责：
- efinance / akshare / yfinance 三个 backend 的 provider 构建；
- shared request 到 provider kwargs 的输入翻译；
- provider 返回到标准契约的结果标准化；
- backend-specific 的搜索、profile、history、realtime handler；
- provider 公共工具函数、错误护栏、market/identifier 辅助逻辑。

这直接把本应彼此独立变化的 backend 行为绑进一个 80KB 模块里，导致任何一个 provider 的局部调整都需要触碰整份文件，review 半径过大，也让“公共逻辑”和“某 backend 特例”越来越难区分。

第二，shared 命令层仍然存在多种假统一：
- quote_id 在 efinance 和 yfinance 下不是同一种标识符，却被放进同一 shared 字段；
- stock.price.history、quote.price.history、fund.profile 等命令在 schema 上允许多值，但部分 backend 适配只支持单值；
- market 枚举在 shared 层合法，不代表所有 backend 实际支持该 market；
- yfinance 对 A 股 shared symbol 没有翻译，只是把输入原样大写后透给 Yahoo ticker。

第三，现有 factory.py 直接从巨型 providers.py 导入三个 build_*_provider()。这虽然能工作，但意味着 provider 模块拆分时，工厂和包导出也必须一起收敛成新的稳定结构。

本次设计既服务于用户要求的“把巨型 provider.py 拆成不同 backend 模块”，也服务于更本质的 shared contract 收敛。按设计模式语言说，这次设计的主模式是：
- Adapter：shared 输入/输出与 provider 原生契约之间的翻译边界；
- Strategy：backend 选择与 provider 差异策略；
- Facade：CLI 不直接感知 provider 细节；
- Factory Method：provider 注册与构建集中管理。

## Goals / Non-Goals

**Goals:**
- 把 providers.py 拆成按 backend 和公共职责分离的多个模块，保留在 opentrade/backends 包下。
- 让公共适配工具、contract 标准化、错误护栏与 backend-specific handler 分层清晰。
- 把 shared command 的支持矩阵、identifier 语义、单值/多值限制从“隐式适配结果”收敛成显式契约。
- 让 auto 路由、facade 和测试以后依赖真实能力边界，而不是依赖“某 provider 看起来大概能跑”。
- 为后续实现阶段提供可操作的模块落点和迁移顺序，避免一次性大爆炸改动。

**Non-Goals:**
- 不在本次 design 中直接展开所有实现细节或代码补丁。
- 不重写整个 backend 基础抽象，BackendProvider / CapabilityHandler 继续沿用现有主干。
- 不在本轮解决所有真实网络不稳定、超时治理或上游数据漂移问题；这些只在与 shared contract 直接相关时纳入边界。
- 不把所有 helper 都抽成高度通用框架，避免为了抽象而抽象。

## Decisions

### 决策 1：按 backend + common helper 拆分 providers.py

**选择**：将当前巨型 opentrade/backends/providers.py 拆成至少四类模块，全部保留在 opentrade/backends 包下：
- efinance_provider.py：只放 efinance 的 handler、适配和 provider 构建。
- akshare_provider.py：只放 akshare 的 handler、适配和 provider 构建。
- yfinance_provider.py：只放 yfinance 的 handler、适配和 provider 构建。
- providers_common.py：只放跨 backend 共享的 contract 标准化、request helper、market/identifier 辅助、通用 payload materialization 等。

factory.py 改为从这几个模块导入 build_*_provider()，而不再依赖单一巨型模块。

**理由**：
- provider-specific 变化点应该在各自模块内部闭合；
- 公共 helper 与 backend-specific 特例分离后，review 和测试半径显著缩小；
- 这种拆分与当前抽象兼容，不需要推翻已有 BackendProvider 结构；
- 这是用户明确要求，也与 Adapter 模式的边界治理一致。

**替代方案与否决原因**：
- 只把 providers.py 拆成前后两个大文件：仍然不能解决 backend 变化点耦合，不采用。
- 保持单文件，只在文件内加更多 section/comment：对结构没有本质改善，不采用。

### 决策 2：共享 helper 必须是“common”，不是“默认 efinance 语义”

**选择**：迁移到 providers_common.py 的工具只能保留真正跨 backend 共享的职责，例如：
- 
ormalize_contract_mapping 相关调用辅助；
- dataframe / mapping / sequence 的通用 materialize；
- 通用 request value 读取与 list coercion；
- 跨 backend 结果标准化骨架。

凡是明显带 backend 语义的逻辑，例如 efinance 的 market_type/fs 映射、yfinance 的 ticker 翻译、akshare 的目录列名解释，都必须留在各自 provider 模块。

**理由**：
- 否则“common”模块会再次变成新的巨型 provider.py；
- 很多现有 helper 名义上通用，实际上埋了 efinance/yfinance 特定假设，需要借这次拆分清洗边界；
- 只有严格限制 common 职责，后续才能稳定维护。

**替代方案与否决原因**：
- 先把所有函数机械迁出，再以后慢慢清理：高风险，会把坏边界复制到新文件，不采用。

### 决策 3：shared identifier 语义必须显式分层，不能继续复用模糊字段

**选择**：为 shared 命令建立明确的 identifier 规则：
- stock.* shared 命令的输入语义默认是 provider-neutral 的股票代码；
- quote.* shared 命令的输入必须明确声明是“统一 quote 标识”还是“provider-native identifier passthrough”；
- 若当前无法提供真实 backend-neutral 的 quote 标识，就必须在契约层收紧支持面，而不是继续允许“Eastmoney quote_id 或 Yahoo ticker”混放。

同时，yfinance 对 A 股 symbol 的映射必须被视为 provider adapter 职责，而不是调用方职责。

**理由**：
- 当前最大契约问题不是代码组织，而是 shared 字段名在不同 backend 下含义漂移；
- 不先定义 identifier 语义，拆模块只会把问题分散到多个文件；
- 这与文章里“先识别变化点，再决定结构”的原则一致，identifier 就是核心变化点之一。

**替代方案与否决原因**：
- 保留现状，在文档里提示用户自己区分：shared contract 仍然不成立，不采用。

### 决策 4：支持矩阵必须反映真实能力，而不是理想能力

**选择**：shared command 的 supported_backends、单值/多值支持、market 支持面，必须围绕真实 provider adapter 能力收敛。若某 backend 仅支持单标的或仅支持部分 market：
- 要么在 schema/adapter 层显式限制；
- 要么补足真实 adapter 翻译；
- 不能继续让 schema 过度承诺，再由运行时隐式失败。

**理由**：
- 这类“表面支持”是当前大量静态违约的来源；
- auto 路由、测试和文档都依赖支持矩阵，如果矩阵本身不真，就没有上层可以可信；
- 明确能力真相后，失败语义会更早、更可解释。

**替代方案与否决原因**：
- 继续让 adapter 在运行时抛 ProviderContractError 兜底：虽然比崩溃好，但 shared contract 仍然是假的，不采用。

### 决策 5：factory.py 继续做 Facade 风格注册表，不让 CLI 感知模块拆分细节

**选择**：无论 provider 模块怎么拆，外部仍通过 opentrade/backends/factory.py 获取 provider。工厂层维持稳定接口：
- list_backend_providers()
- get_backend_provider()
- list_provider_extension_commands()

模块拆分是 backends 包内部重构，不把新文件结构泄漏给上层执行链。

**理由**：
- 这保持 Facade 边界稳定；
- 可以让实现阶段先做内部搬迁，再做 shared contract 收紧，降低改动半径；
- 上层 executor/facade/tests 不需要感知 provider 文件布局。

**替代方案与否决原因**：
- 让上层直接 import 新 provider 模块：会扩大迁移影响面，不采用。

### 决策 6：按“先迁模块，再收紧契约，再更新路由/测试”的顺序落地

**选择**：实现顺序遵循最小闭环：
1. 先拆 providers.py，确保行为不变；
2. 再在新模块结构上收紧 shared contract 和 identifier 语义；
3. 再调整 auto 路由和支持矩阵；
4. 最后更新测试与回归样本。

**理由**：
- 如果把模块拆分和契约收紧同时做，定位成本太高；
- 先保行为搬迁，能把“结构重构”与“行为改变”分开验证；
- 符合项目 AGENTS.md 要求的最小切片与可验证闭环。

**替代方案与否决原因**：
- 一次性重写 provider 层：风险过大，不采用。

## Risks / Trade-offs

- [风险] 模块拆分阶段可能引入 import 循环或 helper 归属不清。 -> 缓解：先定义 common 可放与不可放的边界，并保持工厂入口不变。
- [风险] 先搬文件再改行为，短期内会出现“新结构承载旧契约问题”。 -> 缓解：这是刻意分阶段，先控制 diff 半径，再做行为收紧。
- [风险] 收紧 shared 支持矩阵后，部分原本“勉强可跑”或“文案声称支持”的路径会变成显式失败。 -> 缓解：把这类变化定义为契约修正，并在 spec 与回归测试中明确。
- [风险] quote.* identifier 语义可能牵动文档、测试和 auto 路由多个层次。 -> 缓解：优先把语义定义清楚，再决定实现时是翻译、降级还是收紧支持。
- [风险] common helper 拆分不当，会形成第二个巨型工具文件。 -> 缓解：严格限制 common 只保留跨 backend 真共享的工具，backend-specific helper 一律留在各自模块。

## Migration Plan

1. 设计并确认新的 backends 模块布局与文件职责。
2. 迁移 providers.py 中的公共 helper 到 providers_common.py，并为 provider-specific 代码创建独立模块。
3. 更新 factory.py 和 __init__.py，保持对上层的稳定导出。
4. 在新模块结构上逐项收敛 efinance / akshare / yfinance 的 shared identifier、market 和 cardinality 适配边界。
5. 更新 command_catalog.py、request_schema.py、auto_planner.py 和相关测试，使支持矩阵与真实能力一致。
6. 重跑单元测试与回归测试，区分“模块拆分行为未变”和“契约收紧的预期变化”。

## Open Questions

- quote.* shared 命令最终是收敛成真正统一标识，还是明确降级为 provider-sensitive 入口？
- A 股到 Yahoo ticker 的映射是否完全由本地 adapter 维护，还是只覆盖可判定的主流形态？
- providers_common.py 是否还需要进一步拆成 request_utils.py / 
esult_standardizers.py 一类更细文件，还是先维持单个 common 模块即可？
- 对 fund.profile、stock.price.history 这类多值 schema 但单值 backend 的命令，是优先补 backend 翻译能力，还是先收紧 shared 语义？