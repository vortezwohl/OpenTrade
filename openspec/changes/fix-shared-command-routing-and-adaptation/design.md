## Context

当前仓库的 shared 命令链路已经收敛为 `request_schema -> backend resolver -> facade -> provider -> rendering` 的统一执行骨架，但这套骨架仍保留了一批不适合继续固化的历史假设。

第一，shared 命令的内部请求字段并不真正 backend-agnostic。`command_catalog.py` 仍直接从外部 `.skill` 目录读取命令参考数据，很多 shared 命令的内部字段名还是 provider 原生参数，如 `beg`、`end`、`klt`、`fqt`、`fs`。这让 shared schema 表面统一，实际却把 provider 细节泄漏到了内部执行契约。

第二，`auto` backend 仍是静态候选顺序。当前 resolver 在看不到请求语义的情况下就固定生成 `akshare -> yfinance -> efinance` 候选链，这与真实回归数据和用户直觉都不一致，也无法根据 A 股、美股、quote-id 形态或命令类型做更合理的候选排序。

第三，provider 适配层仍然不足。`EfinanceGenericHandler` 这类入口大量依赖 `callback(**request_data)` 直通，导致日期格式、`market/fs` 语义、多值/单值约束等都落在“上游碰巧兼容”上，而不是由本地适配层显式治理。

第四，执行层和展示层的 `limit` 语义混在一起。现在 `--limit` 主要在 rendering 层裁剪输出，对重路径命令的真实抓取成本几乎没有影响，但命令表面又会给人“请求已减载”的错觉。

第五，真实回归脚本已经成为重要的工程反馈来源，但脚本结果仍把样本错配、适配缺口、产品缺陷和上游不稳定混在同一类失败池中，降低了报告解释力，也让测试集在若干地方继续固化旧候选顺序和旧抽象。

## Goals / Non-Goals

**Goals:**

- 建立 repo 内可维护的 shared 命令真相源，不再依赖外部 `.skill` 目录作为运行时契约来源。
- 为 multi-backend shared 命令定义 provider-neutral 的内部请求契约，并统一日期、symbol、quote-id、market 等核心输入语义。
- 将 `auto` backend 改造成请求感知的候选规划，而不是静态全局顺序。
- 为 history、realtime、profile、search、resolve 等关键命令簇建立显式 provider 请求适配，减少 generic passthrough。
- 收敛 `market` 与 `fs` 的语义边界，让 shared 命令不再直接暴露 provider 原生过滤参数。
- 区分显示裁剪与执行减载，让 `--limit` 的真实行为可解释、可验证。
- 重构真实回归结果分类和测试断言，使测试验证正确行为，而不是固化当前错误实现。

**Non-Goals:**

- 不在本轮重写所有 single-backend provider-extension 命令的业务实现；本轮优先处理 shared 命令和它们直接依赖的适配路径。
- 不在本轮引入新的后端或新的命令面。
- 不把所有重路径命令都抽象成统一分页框架；只对当前已经暴露问题的命令簇建立最小可行减载策略。
- 不为了统一而强行把每个 provider 的特殊过滤能力都塞进 shared 语义；无法共享的能力仍保留为显式 extension 语义。

## Decisions

### 决策一：shared 命令的真相源迁回仓库内，而不是继续读取 `.skill`

运行时命令目录、字段名和支持矩阵必须由仓库自身维护，而不是由外部 skill 参考文件隐式驱动。实现上应把 shared 命令元数据迁移到 repo 内的稳定位置，由 `command_catalog.py` 直接读取 repo 自身数据。

这样做的原因是：

- 外部 `.skill` 文件不是受版本化约束的运行时真相源；
- 当前很多错误字段名和参数语义就是被外部参考持续放大；
- 把真相源迁回仓库后，spec、代码、测试和回归脚本才能围绕同一套数据收敛。

替代方案：

- 保留 `.skill` 为运行时来源，只在测试里绕开它。这个方案会继续让生产代码依赖不可信元数据，不采用。
- 把所有命令定义硬编码到 Python 常量。这个方案虽可行，但维护成本过高，不采用。

### 决策二：shared 请求契约使用 provider-neutral 内部字段名，provider 原生参数只存在于适配层

对于 multi-backend shared 命令，内部请求字段不再沿用 `beg/end/klt/fqt/fs` 这类 provider 原生名字，而是统一使用 provider-neutral 语义字段，例如 `symbols`、`start_date`、`end_date`、`timeframe`、`adjustment`、`market`、`quote_ids` 等。provider 适配层负责把统一字段翻译为上游真实 kwargs。

这样做的原因是：

- shared schema 的职责是表达稳定业务语义，而不是复用某个 provider 的入参拼写；
- provider-neutral 字段才能让 auto 路由、输入校验和结果分析基于同一套语义工作；
- 适配逻辑显式化后，日期格式和多值/单值边界才能被测试直接覆盖。

替代方案：

- 保留当前 provider 风格字段名，只增加少量 helper。这个方案会继续让 shared 契约和 provider 契约混在一起，不采用。

### 决策三：auto 候选规划后移到请求校验之后，改为请求感知排序

`resolve_backend_selection()` 不再承担最终候选链规划职责。它只负责解析“显式 backend / auto / provider-extension 默认值”。真正的 auto 候选链在请求通过 schema 校验并完成 shared 语义归一化后，再基于命令能力、市场语义、标的形态和 provider 支持矩阵生成。

这样做的原因是：

- 请求感知排序必须看到 `market`、`symbol`、`quote-id` 等语义，当前 resolver 的入参信息不足；
- 把候选规划放到请求校验之后，能直接基于 normalized request 推断 A 股、美股、quote 语义；
- 这能避免继续把错误的全局顺序固化进 resolver 和测试。

替代方案：

- 给 `resolve_backend_selection()` 增加原始 request_data 参数。这个方案会让 resolver 既处理显式选择又处理请求语义，职责过重，不采用。

### 决策四：shared `market` 和 provider 原生过滤分层表示，不再靠字段名混用

shared multi-backend 命令统一暴露语义化 `market`。provider 原生过滤表达式如 `fs` 不再直接作为 shared 命令内部字段出现。对于确实需要 provider 原生过滤的 single-backend extension 命令，应使用显式的 provider-specific 字段或 adapter 内部映射，而不是继续把 `market` 和 `fs` 当作同一层语义。

这样做的原因是：

- `market` 表示用户和 shared 层可理解的市场语义；`fs` 表示 provider 内部过滤表达式；
- 当前混用让校验、回归样本和 provider 结果解释全部失真；
- 分层后，shared 命令和 extension 命令可以各自保留清晰边界。

替代方案：

- 继续把 `market` 和 `fs` 都塞进一个字符串字段，由不同 provider 自己猜。这个方案正是当前问题来源，不采用。

### 决策五：`stock.profile` 在 shared 层收紧为单标的语义

shared `stock.profile` 的逻辑语义收紧为“单次请求只描述一个标的资料”。当前 CLI 选项是否保持兼容拼写，可以在实现时决定，但 shared 层和 provider 适配层必须统一把它当作单标的能力处理；若未来确有多标的资料需求，应另开能力或 extension，而不是继续在 shared 层隐式混合。

这样做的原因是：

- 当前可用 provider 中，`yfinance` 和 `akshare` 都是单标的资料语义；
- 把单标的能力伪装成多值 shared 能力，只会制造 fallback、适配和标准化歧义；
- 收紧 shared 语义能减少无意义的 provider 路径分叉。

替代方案：

- 继续保留“表面多值，内部按 provider 各自解释”。这个方案会保留当前歧义，不采用。

### 决策六：`--limit` 分为显示裁剪和执行减载两层，并按命令簇声明策略

运行时 `limit` 不再被默认解释为“已经减轻执行成本”。系统将为命令定义声明 `limit` 策略：

- 仅显示裁剪；
- 可前移到 provider 请求；
- 需在 adapter 层走轻量抓取路径。

对于无法前移的命令，raw 元数据和回归报告必须明确标记“本次仅做显示裁剪，未应用执行减载”。

这样做的原因是：

- 当前 `limit` 的最大问题不是没裁剪，而是裁剪语义被误解；
- 按命令簇声明策略比引入统一分页框架更小、更可控；
- 明确元数据能让回归报告解释真实成本，而不是继续误导使用者。

替代方案：

- 只有当所有命令都能执行减载时才暴露 `limit`。这个方案过于理想化，不采用。

### 决策七：真实回归脚本显式分类失败层级，测试断言改为验证语义而不是固化旧实现

真实回归结果将至少区分 `sample_mismatch`、`adapter_gap`、`product_defect`、`upstream_instability` 四类失败归因。测试方面，原先直接断言静态 auto 顺序或旧字段名的用例需要改成验证请求感知排序、provider 适配结果和失败分类边界。

这样做的原因是：

- 当前脚本不是没有价值，而是分类过粗；
- 如果不改测试，修正后的行为会被旧断言视为回归；
- 分类收敛后，回归报告才能真正支持排期和修复优先级判断。

## Risks / Trade-offs

- [风险] 迁移 shared 内部字段名会影响现有单元测试和部分内部调用桩。 -> 缓解：先在 provider 适配层同时接受旧字段与新字段过渡，待测试和脚本迁完后再收紧。
- [风险] auto 候选规划后移后，watch、raw、测试桩等路径都要重新构造候选链。 -> 缓解：把候选规划做成独立 helper，并补充 executor/facade 的定向测试。
- [风险] 对 `stock.profile` 收紧单标的语义可能让少量依赖旧多值形式的测试或脚本失败。 -> 缓解：CLI 拼写先兼容，语义先收紧，并在错误消息中明确单标的限制。
- [风险] 部分重路径命令暂时无法真正执行减载。 -> 缓解：允许第一阶段只补元数据和分类，不伪造“已减载”，并优先实现最痛命令簇的前置减载。
- [风险] 从 `.skill` 迁出元数据时，若迁移不完整，可能导致命令面或帮助信息短期不一致。 -> 缓解：用命令库存量测试、CLI help 测试和真实回归矩阵三层校验迁移结果。

## Migration Plan

1. 先把 shared 命令真相源迁入仓库，建立 provider-neutral 字段名，并让 `request_schema` 与命令构建层围绕新真相源生成 CLI 选项。
2. 引入 normalized request / adapter helper，优先覆盖 history、realtime、profile、search、resolve 命令簇，同时保留必要的旧字段兼容层。
3. 将 auto 候选规划后移到请求归一化之后，补充请求感知排序与 trace 元数据，并更新 facade / executor / watch 相关测试。
4. 为 `limit` 增加命令簇级策略与 raw 元数据，再逐步把重路径命令接入真正的执行减载。
5. 最后更新真实回归脚本、失败分类和测试断言，重新跑一轮最小真实回归子集，再扩展到全量回归。

## Open Questions

- 哪些 single-backend extension 命令也值得纳入统一日期输入契约，哪些应该保留 provider 原生形态。
- `market price live` 这类 provider 过滤语义很强的命令，是否需要在本轮直接改字段名，还是先通过 adapter 隔离 raw filter。
- `stock.profile` 是否需要在 CLI 层立即切换到单数选项拼写，还是先保留旧拼写以减少一次性兼容风险。
- 对无法真正执行减载的命令，是否需要在 observation / raw 输出里统一展示 `execution_limit_applied` 一类元数据字段名称。
