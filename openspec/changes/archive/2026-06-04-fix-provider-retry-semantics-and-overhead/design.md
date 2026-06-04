## Context

当前仓库的统一执行链已经把重试入口上移到 `BackendProvider.execute()`，但这一版实现还存在两个收口不完整的问题。

第一，provider 语义在重试耗尽时被冲掉。`retry_utils` 现在会在耗尽后抛出外层 `MaxRetriesReachedError`，只把最后一次 provider 异常挂到 `__cause__`。这不满足“保留 provider 语义”的 change 要求，也让上层只能拿到通用重试错误。

第二，执行入口本身存在热路径噪音。`BackendProvider.execute()` 每次都会构造新的 `invoke` 闭包，再交给 `call_with_network_retry()`；而 `_build_retryable_handler_call()` 里的异常分支都只是原样 `raise`，没有实现实际的异常分层。这会让新加的 wrapper 缓存基本打不中，也把没有收益的额外调用深度放进 watch/批量请求热路径里。

同时，`akshare` 搜索 handler 还保留着“内部吞异常后拼装 `errors`”的模式。这样 provider 级 retry 看不到原始网络异常，导致这条路径名义上接入了统一重试，实际并没有闭环。

## Goals / Non-Goals

**Goals:**

- 让 provider 级统一重试在耗尽时恢复抛出 provider 自身异常语义，而不是通用 `MaxRetriesReachedError`。
- 让 `akshare instrument.search` 的瞬时网络失败真正进入 provider 级 retry 闭环。
- 精简 provider 执行入口的包装方式，使 retry wrapper 缓存能命中稳定调用对象，并移除无效异常分层代码。
- 明确 `retry_utils` 在 `retry_exceptions=None` 与 `retry_exceptions=()` 下的不同语义。
- 用回归测试固定上述行为，避免后续在 provider 骨架上再次回归。

**Non-Goals:**

- 不改变 `auto` failover 的高层策略；当前 backend 内部重试完成后是否继续 failover，仍由现有 eligibility 规则决定。
- 不在本轮重构 `get_backend_provider()` 的 registry 构造策略。
- 不对所有 yfinance 慢路径做性能优化；本轮只处理 provider 执行入口本身引入的无效包装成本。
- 不扩大 side-effect 命令的语义边界或命令目录规则。

## Decisions

### 决策一：重试耗尽后直接恢复抛出最后一次 provider 异常

`retry_utils` 将继续用现有 `Retry` 实现做退避与重试计数，但在捕获 `MaxRetriesReachedError` 后，不再把它作为最终对外异常保留下来，而是直接重新抛出最后一次真实异常；必要时把“已重试 N 次”的信息补进消息或日志，而不是替换异常类型。

这样做的原因是：

- 它满足当前 change 对“保留 provider 语义”的明确要求；
- facade、tests 和未来调用方都无需了解 `vortezwohl.func.retry` 的内部异常类型；
- 限流、guardrail 和 provider 专属网络错误的最终形态重新回到 provider 自身语义层。

替代方案：

- 保留 `MaxRetriesReachedError` 作为外层异常，只依赖 `__cause__` 回溯真实错误。这个方案会继续破坏最终异常契约，也要求上层代码显式解包内部实现细节，因此不采用。

### 决策二：把 `akshare` 搜索的“目录部分失败”与“可重试网络失败”拆开处理

`AkshareSearchHandler` 需要区分两类异常：

- 可容忍的局部目录失败，例如某一类目录源确实不可用，但其他目录源仍可继续；
- 应进入 provider retry 的瞬时网络异常，例如 `OSError`、HTTP 类错误。

实现上不再用一个宽泛的 `except Exception` 全部吞掉，而是优先让 provider retry policy 覆盖的网络异常直接上抛；只有非 retryable 的局部目录失败才记录进 `errors`。这样既保留 `akshare` 搜索“多源聚合”的原始意图，也不再绕过统一重试入口。

替代方案：

- 彻底移除内部 `errors` 聚合，任何目录失败都让整次搜索失败。这个方案过于激进，会改变原有搜索的容错特征，因此不采用。

### 决策三：移除 `_build_retryable_handler_call()` 的空分层闭包，改为稳定调用对象

`BackendProvider.execute()` 不再为每次请求构造临时 `invoke` 闭包。改为使用稳定的 provider/handler 调用路径，例如直接把 `handler.execute` 或 provider 内部的固定 helper 传给 `call_with_network_retry()`，仅在必要时以显式异常策略决定是否进入重试。

这样做的原因是：

- wrapper 缓存才能按“同一函数对象 + 同一异常集合”稳定复用；
- 当前 `_build_retryable_handler_call()` 不提供任何真实语义，只是在制造额外调用层级；
- 行为更直接，测试也更容易围绕真实执行点断言。

替代方案：

- 保留当前闭包，只在闭包对象上再做缓存。这个方案会让 provider 层继续承担一套额外缓存逻辑，复杂度高于收益，不采用。

### 决策四：`retry_exceptions=None` 表示使用默认集合，`retry_exceptions=()` 表示显式禁用

`retry_utils` 将把“未传值”和“显式空集合”分开处理。`None` 继续回退到默认网络异常集合；空元组则表示不要为任何异常触发自动重试，但仍可保留统一包装接口与签名保持能力。

这样做的原因是：

- 这个语义边界更符合 Python 常见 API 约定；
- 它为后续 provider 或测试场景保留了“共用包装器但关闭重试”的稳定出口；
- 不需要当前立刻新增调用方，也值得一次性修正。

## Risks / Trade-offs

- [风险] 直接恢复抛出最后一次 provider 异常后，部分现有测试如果断言 `MaxRetriesReachedError` 会失效。 → 缓解：把回归测试区分为“retry 工具内部行为测试”和“provider 对外契约测试”，前者仍可覆盖内部重试机制，后者统一断言最终 provider 语义。
- [风险] `akshare` 搜索上抛更多网络异常后，可能让某些过去“勉强返回部分结果”的场景改为失败。 → 缓解：只把 provider retry policy 命中的网络异常上抛，保留非网络局部目录失败的 `errors` 聚合。
- [风险] 改成稳定调用对象后，如果错误地直接传 `handler.execute`，可能让部分 provider 未来难以插入额外分层逻辑。 → 缓解：保留一个稳定 helper 方法承载最小分层，而不是恢复临时闭包。
- [风险] `retry_exceptions=()` 语义修复可能影响未来依赖旧行为的调用方。 → 缓解：当前仓库内没有这样的调用方，本轮通过回归测试明确新语义即可。

## Migration Plan

1. 先调整 `retry_utils`，明确默认异常集合与显式空集合语义，并修复“重试耗尽后恢复抛出真实异常”的最终行为。
2. 重构 `BackendProvider.execute()`，移除 `_build_retryable_handler_call()` 的临时闭包，改用稳定调用对象接入统一重试。
3. 修改 `AkshareSearchHandler` 的异常边界，让 retryable 网络异常上抛，非 retryable 的目录局部失败继续走 `errors` 聚合。
4. 更新 facade/provider/retry 相关测试，增加 `akshare` 搜索与 provider 语义断言。
5. 运行最小回归集；若发现 provider 语义修复影响 `auto` 路径错误文案，再单独补齐脚手架测试或 observation 断言。

## Open Questions

- provider 语义恢复抛出时，是否还需要把“已重试 N 次”追加到最终异常 message 中，还是只保留日志/observation 即可。
- `akshare` 搜索的哪些具体异常应被视为“局部目录失败”而不是“整次请求失败”，是否需要再细分为更窄的异常集合。
