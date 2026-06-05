## Context

当前仓库已经建立了 `request schema -> auto planner -> facade -> provider adapter -> standard result` 的执行主干，但这条主干上的边界仍不够真实。静态审查确认了三类核心失真：

1. shared identifier 契约与 provider-native identifier 契约混杂。`quote.*` 共享命令禁止直接传东财 `quote_id`，但 `efinance` 适配层实际仍按 `quote_id` 真实接口消费；`yfinance` 又把共享 `symbol` 与 Yahoo ticker 混用，导致契约表意与真实执行不一致。
2. auto routing 已经尝试做请求感知，但候选真实性过滤函数并未接入候选规划主路径，且 `quote.*` 仍在读取旧字段名。这使 Strategy 层的意图存在，但没有真正成为执行前置条件。
3. capability matrix 与实现粒度不一致。某些 shared 命令在 schema 中支持多标的或某类市场语义，但具体 provider 只支持单标的或完全不支持该市场，当前实现依赖运行期失败兜底，而不是在契约层如实约束。

从设计模式视角，这次修复的关键不是增加更多抽象，而是让现有抽象各归其位：
- Adapter 负责 shared contract 到 provider-native contract 的显式翻译；
- Strategy 负责基于真实能力和 normalized request 规划候选链；
- Facade 负责统一执行与错误传播，不自行猜测 provider 语义；
- Factory 继续维持 provider 注册入口稳定，不把内部重构泄漏到上层。

## Goals / Non-Goals

**Goals:**
- 让 `quote.*`、A 股 `yfinance`、单标的限制等路径的 shared contract 与真实 backend 接口重新对齐。
- 让 auto planning 真正使用“请求真实性过滤 + normalized 字段”生成候选链，而不是只做排序装饰。
- 将 provider adapter 的翻译责任显式化，禁止依赖错误 passthrough 或远端偶然兼容。
- 让 shared capability matrix 成为可信契约，能真实表达单标的、多标的、市场语义和 provider 支持面的限制。
- 在修复行为的同时补齐回归测试，保证后续改动不再悄悄回到“表面支持”。
- 修复关键 provider 模块的编码与中文乱码，恢复可审查、可维护状态。

**Non-Goals:**
- 不新增后端，不扩展新的资产域。
- 不修改 `.venv` 内第三方库源码，也不假定可以通过 monkey patch 修复上游行为。
- 不把本次修复扩展为新一轮大规模 provider 架构重写；优先在现有 `BackendProvider / Facade / Auto planner` 主干内精确修复。
- 不把 shared 契约过度抽象成难以理解的新框架；本次只解决已被证实的真实性失真。

## Decisions

### 决策 1：把 identifier 语义收敛成“shared identifier”与“provider-native identifier”两层

**选择**：在 shared contract 层显式区分：
- shared `symbol` / `symbols` 表示 provider-neutral 输入；
- provider-native `quote_id`、Yahoo ticker 属于 adapter 内部可消费语义，不能直接混进 shared contract；
- 若某共享能力无法对某 backend 做可靠翻译，就必须在 contract/adaptation 层显式拒绝。

**理由**：
- 这是当前 `quote.*` 与 A 股 `yfinance` 失真的根源。
- 只有把 identifier 分层，Adapter 才能真正封装 backend 细节，而不是把 provider-native 约束泄漏到 shared schema。
- 这符合“先识别变化点再建结构”的原则，identifier 是本次最核心变化点。

**备选方案与否决原因**：
- 保持现状，只补几处临时翻译：会让 shared contract 继续含糊，问题会在其他命令路径复发。
- 允许 shared 命令直接接受 provider-native identifier：会破坏多后端 shared contract 的成立条件，不采用。

### 决策 2：把 `efinance` 的 `quote.*` 路径改成强制显式 adaptation

**选择**：`quote.price.latest`、`quote.profile` 在 `efinance` 下必须统一走本地 symbol -> Eastmoney `quote_id` 翻译，再调用真实接口。已有 `_resolve_efinance_quote_id/_quote_ids()` 必须进入执行主路径，generic passthrough 不得再承载这些 shared command family。

**理由**：
- `.venv` 中真实签名已证明 `efinance.common.get_latest_quote()` 与 `get_base_info()` 只接受 Eastmoney `quote_id`。
- 当前 shared schema 明确禁止用户直接传 `quote_id`，因此 adapter 必须自己补完翻译责任。
- 这正是 `provider-request-adaptation` spec 想表达但当前实现没有兑现的点。

**备选方案与否决原因**：
- 放宽 schema，允许用户直接传 `quote_id`：会把 provider-native 语义暴露到 shared 层，不采用。
- 在 facade 层做特殊分支翻译：会破坏 Adapter 边界，不采用。

### 决策 3：把 A 股到 Yahoo ticker 的翻译责任真正接到 `yfinance` 主路径

**选择**：历史、实时、资料三条 shared 路径统一复用现有 A 股 ticker 翻译函数；若输入形状或市场语义无法稳定翻译，则 adapter 必须抛出 `ProviderContractError`，而不是原样传给 Yahoo。

**理由**：
- 代码里已有翻译函数，但主执行路径未实际接入，这是典型“抽象已存在但行为未闭环”。
- 如果 auto routing 把 yfinance 作为 A 股候选，就必须先保证它的 contract truthfulness。
- 这能让 yfinance 的支持面从“看起来能跑”变成“要么真支持，要么明确失败”。

**备选方案与否决原因**：
- 直接把 yfinance 从所有 A 股 shared 支持矩阵中去掉：太保守，会丢掉本来可稳定支持的子场景。
- 保持现状，仅靠 auto 顺序把 yfinance 排后：无法修复显式 backend 场景，也不真实。

### 决策 4：让 auto planner 的 Strategy 决策以真实性过滤为主，而不是只做排序

**选择**：`plan_auto_backend_candidates()` 必须在排序前应用 `_supports_request_truthfully()` 这类真实性裁剪，并修复其读取旧字段名的问题。candidate chain 的语义是“允许尝试的真实候选”，不是“按偏好排序的所有理论候选”。

**理由**：
- 当前 helper 已存在但未接入，说明设计意图明确，只是实现未完成。
- 只有先过滤再排序，Facade 的 failover 才具备可解释性。
- 这能显著减少无意义的第一跳失败和错误传播噪音。

**备选方案与否决原因**：
- 保留当前全候选链，只在失败时依赖 failover eligibility：会继续把明显不支持的 backend 推入运行期，不采用。
- 把真实性过滤塞进 Facade：Facade 不应理解 provider 能力细节，职责不对。

### 决策 5：把 capability matrix 视为外部契约，按真实能力收紧而不是按理想能力声明

**选择**：shared command 的 `supported_backends`、单标的/多标的语义、市场支持面必须围绕真实 adapter 能力重写。对不能稳定支持的组合，应在 schema、adapter 或 truthfulness 规则中尽早失败，而不是保留“表面支持”。

**理由**：
- 测试、文档、auto 路由都依赖 capability matrix；矩阵不真实，上层就都不可信。
- 这是降低未来维护成本的关键，比“局部修通某个命令”更重要。

**备选方案与否决原因**：
- 继续依赖 ProviderContractError 在运行时兜底：这只能事后失败，无法形成可信契约，不采用。

### 决策 6：把编码修复纳入本次 change 的交付边界，但仅限本次触达的关键 provider 文件

**选择**：对本次直接参与修复的 provider / contract 关键 Python 文件，统一校正为 UTF-8 without BOM，并恢复中文 docstring 与注释可读性。范围仅限本次必须触达的文件，不扩散到整个仓库。

**理由**：
- 项目 AGENTS 把编码正确性列为硬规则；当前乱码已直接影响审查与后续维护。
- 如果放任乱码继续存在，后续 contract 修复很难被准确 review。

**备选方案与否决原因**：
- 完全忽略编码问题：违反项目硬约束，不采用。
- 一次性清洗全仓库编码：超出本次范围，风险过大，不采用。

## Risks / Trade-offs

- [Risk] 收紧 shared contract 后，部分历史上“勉强可跑”的调用会转为显式失败。 -> Mitigation: 在 spec、tasks 与最终实现中把这些变化定义为契约修正，并补充针对性的回归用例与错误消息。
- [Risk] A 股 `yfinance` 翻译接入后，仍可能存在个别代码前缀无法可靠映射。 -> Mitigation: 只支持已可稳定判定的前缀，其他形状显式抛出 `ProviderContractError`。
- [Risk] auto candidate chain 收紧后，某些命令的 fallback 次序和命中 backend 会变化。 -> Mitigation: 把 candidate order、attempted candidates、final backend 全部纳入 raw metadata 与测试断言。
- [Risk] 编码修复可能引入无关 diff。 -> Mitigation: 只处理本次必须修改的关键 provider 文件，并在任务拆分中单独列出编码校正步骤。
- [Risk] 若 spec 写得过宽，后续实现又会回到“表面支持”。 -> Mitigation: 每个 requirement 都落到可测试场景，尤其覆盖 quote adaptation、truthful filtering、single-target 限制和 A 股 ticker 翻译。

## Migration Plan

1. 先固化 proposal、design 与 spec，明确 shared identifier、truthfulness 与 auto routing 的新契约。
2. 实现阶段优先修复 `efinance` 的 `quote.*` adaptation 路径，使 shared symbol 到 Eastmoney `quote_id` 翻译闭环成立。
3. 接入 `yfinance` 的 A 股 ticker 翻译到历史、实时、资料主路径，并对无法翻译的场景显式拒绝。
4. 更新 auto planner：修复旧字段名读取、接入真实性过滤，并校准候选规划 metadata。
5. 收紧 capability matrix 与 request validation / adapter truthfulness 规则，保证 schema、planner、adapter 读同一份 normalized contract。
6. 补充并通过单元测试、契约测试和关键回归测试，再修复本次触达文件的编码与中文可读性。
7. 若上线后发现某类 identifier 翻译误判，可按 feature slice 回滚对应 adapter truthfulness 收紧，不回滚整个 provider 框架主干。

## Open Questions

- `quote.price.history` 在 shared 层是否继续允许多标的一次性请求，还是按 truthfulness 收紧到仅在支持批量的 backend 下成立？
- 对于 A 股 `yfinance`，是否需要把“显式 backend = yfinance 且输入为六码”也视为合法翻译场景，还是仅对 auto/shared 内部使用开放？
- 编码修复的最小范围是否只限 provider 相关文件，还是应同时纳入 `command_catalog.py`、`contracts.py`、`models.py` 这几个契约核心文件？