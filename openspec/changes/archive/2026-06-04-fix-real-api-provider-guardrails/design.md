## Context

当前仓库已经把共享命令执行链收敛成 `request schema -> auto planner -> facade -> provider adapter -> rendering` 的主干，但 2026-06-04 的真实 API 回归说明，这条主干仍然把三类不该混在一起的职责耦合在了一起：

1. 执行层内部控制信息与 provider 原生 kwargs 没有硬边界。`CommandFacade.invoke()` 会把执行期的 `execution_limit` 注入请求字典，部分 efinance shared/generic 适配分支又直接把整个 `request_data` 透传给上游函数，导致 `stock holders latest-count --limit 5`、`stock ipo latest --limit 5`、`fund catalog --limit 5`、`bond catalog --limit 5`、`futures catalog --limit 5` 等真实命令因 `__runtime_limit__` 泄漏而失败。
2. `auto` 的 failover 资格判定仍然依赖原始异常类型，无法区分“本地契约错误”和“provider / 上游失败”。在真实回归里，`fund profile`、`bond flow today` 等失败都表现成 `TypeError` / `ValueError`，但根因并不是用户输入错误，而是第三方 provider 响应或其内部实现崩溃；当前策略会直接中断兜底链。
3. 共享 CLI 契约与部分 provider 真实契约不一致。`stock leaderboard daily` 与 `stock holders latest-count` 的命令文档和回归样本都采用 `YYYYMMDD`，而 efinance 上游函数要求 `%Y-%m-%d`；当前适配层没有归一化，所以错误地把共享命令的“统一日期输入”责任推给了调用方。
4. 对上游坏返回缺少反腐层。`fund profile` 会在 efinance 上游 `fund.get_base_info()` 内部因 DataFrame dtype 冲突崩溃，`bond flow today` 会因上游返回 `bool` 结构而在 `common.getter` 内部崩溃。项目本地并不拥有修复第三方库源码的权限，但必须决定这些错误在本地应如何分类、呈现以及是否允许 auto 继续尝试下一个 backend。

这次变更服务的不是“把所有真实回归都修完”，而是先把本地职责边界补齐：Facade 只编排，Adapter 只做显式翻译与归一化，Failover Policy 只基于分类后的错误决策，Guardrail 只负责吸收第三方不稳定而不伪造成功结果。这也对应用户给出的设计模式参考：用清晰边界替代偶然耦合，而不是继续靠局部补丁堆行为。

## Goals / Non-Goals

**Goals:**

- 建立执行层内部控制字段与 provider 原生请求参数的硬边界，确保内部元数据不会再泄漏到第三方 SDK。
- 为 `auto` 引入可解释的错误分类与切换规则，让本地契约错误快速失败，让 provider / 上游失败保持可兜底。
- 为已证实的共享日期契约不一致建立本地归一化行为，至少覆盖真实回归中暴露的 `stock leaderboard daily`、`stock holders latest-count` 等命令。
- 为已证实的上游坏返回建立 guardrail：不伪造成功，不把 provider 崩溃误报成用户错误，并让 auto 能基于稳定分类做后续决策。
- 补充与这些边界配套的单元测试、回归脚本样本和失败分类断言，使后续真实回归结论可解释。

**Non-Goals:**

- 不在本次变更中重写整个 provider 体系，也不把所有 shared 命令都升级成新的抽象层。
- 不修改第三方 `.venv` 中的 efinance、yfinance、akshare 上游源码。
- 不在本次变更里引入新的 backend、网络超时框架或全局性能治理；超时与重查询成本问题另立 change 处理。
- 不把任何明确失败的上游调用伪装成空结果或兼容成功，避免掩盖真实可用性问题。

## Decisions

### 决策 1：把“执行控制信息”和“provider 请求 kwargs”拆成两个层次

**选择**：`Facade` 不再通过给 normalized request 字典追加内部字段来传递执行控制信息。执行层元数据应通过显式的 execution context 传递，或者在进入第三方 callback 前统一做 request sanitization；只有明确声明支持该控制字段的 adapter 分支，才能消费这些元数据。

**理由**：

- `__runtime_limit__` 泄漏是典型的 Facade 污染 Adapter 边界问题。内部控制字段一旦混入 provider kwargs，generic passthrough 就会把它错误地当成上游真实参数。
- 让 Adapter 显式决定“是否消费 execution limit”，比在 Facade 层偷偷改写请求字典更符合单一职责。
- 这也是最小闭环：不需要重写请求模型，只需要建立统一的“内部字段永不直通第三方 callback”规则。

**替代方案与否决原因**：

- 只在若干报错命令上手工 `pop('__runtime_limit__')`：短期可止血，但会继续保留同类泄漏点。
- 继续沿用混合字典、仅要求开发者记得过滤：约束太弱，真实回归已证明会再次漏出。

### 决策 2：引入 provider 错误分类边界，而不是继续按原始异常类型做 failover

**选择**：把 failover policy 建立在“分类后的 provider 错误”上，而不是 `TypeError` / `ValueError` / `RuntimeError` 这类原始 Python 异常。Adapter 本地发现的契约不满足、参数不支持、共享语义无法落到当前 backend 的情况，应抛出明确的本地契约错误；第三方 callback、返回结构漂移、标准化失败、远端断连、限流等，则应被归为 provider 执行失败或 provider 响应错误。

**理由**：

- 在真实回归里，`TypeError` 既可能代表“本地写错参数”，也可能代表“efinance 上游拿到了 bool/错误 payload 后内部崩溃”。继续按原始异常类型判断，只会扩大误判。
- 将异常分类前移到 provider adapter / 反腐层，可以让 `auto` 只关心“这是不是值得继续尝试下一个 backend 的失败”，而不是猜测堆栈来源。
- 这种做法比“黑名单 / 白名单异常类型”更谨慎，因为未知错误不会被自动假设为可恢复，只有被明确归类为 provider failure 的错误才参与 failover。

**替代方案与否决原因**：

- 把 `TypeError`、`ValueError` 一律视为可 failover：过于冒进，会把本地编程错误和契约错误也吞进兜底流程。
- 继续维护一个更长的异常白名单：仍然靠异常类名偶然匹配，无法表达错误来源和阶段。

### 决策 3：共享日期输入保持 provider-neutral，日期格式归一化放在 Adapter 层

**选择**：共享命令继续接受项目文档与样本中已经使用的 `YYYYMMDD` 输入；针对 efinance 等要求 `%Y-%m-%d` 的上游函数，由 Adapter 显式归一化。若用户本来就传入带连字符日期，应保持兼容。

**理由**：

- 当前 shared CLI 已经把 `start-date`、`end-date`、`date` 描述成统一日期输入，直接改文档去追随某个 provider 的局部格式，会让共享层失去意义。
- 日期归一化属于典型 Adapter 职责，应由 provider 边界承担，而不是让测试脚本或用户记住不同 backend 的私有格式。
- 这类归一化是纯本地可验证行为，不依赖第三方修复。

**替代方案与否决原因**：

- 直接把 CLI 文档和样本改成 `%Y-%m-%d`：会把 provider 特有契约泄漏到 shared 层，且与现有真实回归样本不兼容。
- 只修测试脚本、不修产品：不能解决真实用户输入体验问题。

### 决策 4：对已知上游坏返回建立 Guardrail，但不伪造成功结果

**选择**：在 provider adapter / 标准化边界上，为已知的坏返回和第三方内部崩溃建立 guardrail。Guardrail 的职责是把上游异常稳定地收口成“provider failure”或“provider response error”，保留 backend、command、stage 和原始异常摘要；在 `auto` 模式下允许 failover，在显式 backend 模式下则向用户暴露稳定且可解释的失败。

**理由**：

- `fund profile` 和 `bond flow today` 的问题不在本地业务逻辑本身，而在第三方库执行期崩溃；本地最合理的职责不是篡改结果，而是把这种失败吸收到统一边界里。
- 若直接吞掉异常并返回空结果，会伪造可用性；若完全放任原始堆栈外泄，又会让产品层和回归报告无法判断失败归因。
- 这就是反腐层的价值：把外部不稳定隔离成项目内部可消费的错误语义。

**替代方案与否决原因**：

- 直接 monkey patch `.venv` 中第三方源码：高风险、不可持续，也不符合本次 change 的边界。
- 对显式 backend 自动静默切换：会掩盖“用户明确选择某 backend 但该 backend 当前不可用”的事实。

### 决策 5：真实回归脚本与测试断言围绕“边界语义”更新，而不是围绕当前错误实现更新

**选择**：测试与回归样本应断言以下语义：内部控制字段不会泄漏、共享日期输入会被适配、auto 只在 provider failure 上兜底、显式 backend 的 provider failure 会被稳定分类。报告层需要区分至少三类失败：本地契约错误、provider failure、上游不可用/不稳定。

**理由**：

- 当前报告里已经出现把脚本误用、产品缺陷、上游崩溃混在一起的情况，这会反过来误导后续修复优先级。
- 若测试继续断言原始 `TypeError` / `unexpected keyword argument` 之类的偶发表现，会把本次修复错误地视为回归。

**替代方案与否决原因**：

- 只补单元测试不更新真实回归脚本：无法保证后续报告仍然可解释。

## Risks / Trade-offs

- **[风险] 新的错误分类过细，初期可能遗漏某些真实 provider 失败场景。** -> **缓解**：先覆盖本次真实回归中已经证实的几类失败，并保留尝试轨迹与原始异常摘要，便于后续增量扩展分类。
- **[风险] 过于保守的 failover policy 可能仍然放过某些本可兜底的错误。** -> **缓解**：默认只让明确归类为 provider failure 的错误参与兜底，先避免误吞本地 bug；后续根据真实回归样本再扩展分类。
- **[风险] 日期归一化若实现过宽，可能误改非日期字符串。** -> **缓解**：仅在已知日期字段上做格式转换，并限制为长度和字符集都满足日期模式的输入。
- **[风险] 对上游坏返回建立 guardrail 后，部分 stderr / trace 内容会变化。** -> **缓解**：把变化限定为错误分类和消息收口，不更改成功结果结构，并更新对应测试与报告断言。
- **[风险] 显式 backend 仍可能失败，用户会认为“没有真正修好”。** -> **缓解**：在 design 和 spec 中明确本次目标是“本地边界治理”，不是修复第三方库自身行为；显式 backend 失败将更稳定、更可解释。

## Migration Plan

1. 先在 provider 调用边界引入 request sanitization，并补定向测试覆盖 `--limit` 泄漏样本，确保不再向第三方 callback 暴露内部字段。
2. 再引入 provider 错误分类与 auto failover policy，先覆盖真实回归已证实的 rate limit、远端断连、返回结构漂移、第三方内部崩溃等路径。
3. 在 efinance 相关 adapter 中补共享日期归一化与 guardrail，覆盖 `stock leaderboard daily`、`stock holders latest-count`、`fund profile`、`bond flow today` 等真实样本。
4. 最后更新单元测试、provider handler 测试、真实回归脚本和失败分类报告，重新跑最小真实样本集验证分类是否符合设计预期。
5. 若新分类导致意外的大范围失败，可先回退到“request sanitization + 日期归一化”两项纯局部改动，再单独迭代错误分类层。

## Open Questions

- 是否需要为 provider failure 定义统一的结构化 metadata 字段，以便 raw / observation / HTML 报告直接消费，而不是只靠 stderr 文本？
- `fund profile` 在 auto 模式下若 efinance 失败但 yfinance 成功，最终输出是否需要显式记录“曾经从 efinance failover 到 yfinance”的稳定字段，而不仅是 trace 文本？
- 除了 `stock leaderboard daily`、`stock holders latest-count`，是否还存在更多共享命令对 `YYYYMMDD` 与 `%Y-%m-%d` 的契约错位，需要在实现前再做一次扫查？
