## Context

当前仓库已经把多 backend 网络重试收敛到 `BackendProvider.execute()` 和 `retry_utils.with_network_retry()` 这一层，但仍有两个实现与规格不一致的点：

- `ProviderRetryPolicy.passthrough_exceptions` 已定义，却没有进入任何生产执行路径，导致 provider 虽可声明 guardrail / 参数错误应直通，运行时却不会真正尊重这个边界。
- `with_network_retry()` 会缓存外层 wrapper，但 wrapper 内部仍在每次调用时创建新的 `tracked_call` 与 `_NETWORK_RETRY.on_exceptions(...)(tracked_call)`，没有完全兑现“稳定包装器复用”的目标。

这两个问题都位于统一执行热路径，且都已经具备明确的预期行为：前者关系到 provider 语义正确性，后者关系到 watch / 批量路径的重复开销。因此本次 change 只收敛这两个点，不再扩大到新的 retry 策略抽象。

## Goals / Non-Goals

**Goals:**

- 让 `passthrough_exceptions` 进入真实执行链路，并且优先于自动重试判定。
- 保持 `retry_exceptions=None` 与 `retry_exceptions=()` 的语义区分不变。
- 让同一函数在同一组 retry/passthrough 策略下只构造一次稳定 retry decorator。
- 保持“重试耗尽后抛最后一个真实 provider 异常”的现有行为。
- 让 provider 侧缓存键完整表达 retry 相关策略，避免不同 passthrough 配置命中同一个 wrapper。
- 用单测覆盖行为边界，而不是只验证缓存字典非空。

**Non-Goals:**

- 不调整 `Retry` 的退避算法、最大重试次数或日志实现。
- 不新增新的 facade failover 规则，也不重排 candidate backend 顺序。
- 不在本轮重构 provider policy 结构体之外的更大抽象。
- 不引入真实网络集成测试。

## Decisions

### 决策一：在 `retry_utils` 中增加 `passthrough_exceptions`，而不是把直通逻辑散落回 provider 层

`with_network_retry()` 与 `call_with_network_retry()` 新增 `passthrough_exceptions` 参数，由底层统一重试工具负责“直通异常优先于 retry”这一语义。`BackendProvider` 只负责把 provider policy 下发给重试工具。

这样做的原因是：

- 直通异常与可重试异常一样，都是统一重试工具的输入条件，而不是 provider 层的局部实现细节。
- 若把 `except passthrough_exceptions: raise` 散落在各个 provider helper 中，后续新增 backend 时仍会重复实现同类逻辑。
- 把优先级收敛在底层工具里，测试也可以直接围绕 `with_network_retry()` 建立，而不必每次穿过 provider/facade 才能覆盖。

替代方案：

- 只在 `BackendProvider._get_retry_wrapper()` 中人为包一层 `try/except passthrough`。这能修正当前行为，但会把同一语义拆成 provider 层和 retry 工具层两处维护，后续更难复用，因此不采用。

### 决策二：provider 缓存键同时绑定 `retry_exceptions` 与 `passthrough_exceptions`

`BackendProvider._retry_wrapper_cache` 的 key 从 `(capability_name, retry_exceptions)` 扩展为 `(capability_name, retry_exceptions, passthrough_exceptions)`。

这样做的原因是：

- 相同 capability 在不同 passthrough 策略下，运行语义已经不同，继续复用旧 wrapper 属于错误命中。
- provider 级 cache 的职责是复用“稳定执行语义”，而不是只复用“部分相同的 retry 集合”。
- 这个变更成本小，但能直接避免后续测试或运行时因策略切换而出现隐蔽行为污染。

替代方案：

- 保持旧 key，不同策略时清空整个 cache。这样副作用更大，且会掩盖“缓存键表达不完整”的真实问题，不采用。

### 决策三：把底层 retry decorator 的构造前移到 wrapper 创建阶段

`with_network_retry()` 在创建 wrapper 时一次性构造稳定的 `tracked_call` 与 `decorated`，`wrapper(*args, **kwargs)` 每次调用只负责重置本次调用的错误记录并转发给已构造的 `decorated`。

这样做的原因是：

- 现有三方 `Retry.on_exceptions()` 返回的 wrapper 本身已经按“每次调用重新跑 validator”设计，稳定复用同一个 decorated 是安全的。
- 当前性能问题的根源不是 provider cache 缺失，而是 `on_exceptions(...)(tracked_call)` 仍位于每次调用路径里。
- 把构造前移后，热路径只剩参数转发与错误记录复位，才能真正兑现“wrapper 复用”。

替代方案：

- 继续保留当前结构，只增加更多 cache 断言。这不会减少实际重复装饰开销，因此不采用。

### 决策四：保留“重试耗尽后抛最后真实异常”的现有对外语义

稳定 wrapper 仍需记录最后一次真实 provider 异常，并在底层 `Retry` 抛出 `MaxRetriesReachedError` 时恢复原异常对外抛出。

这样做的原因是：

- facade、provider 单测和已有 change 都已经围绕“保留 provider 语义”建立约束。
- 对调用方而言，`MaxRetriesReachedError` 是内部实现细节，不应取代最终业务/网络异常。

## Risks / Trade-offs

- [风险] passthrough 优先级实现错误会让本应重试的异常被提前透传。 -> 缓解：补一条“同一异常同时出现在 retryable 与 passthrough 时，passthrough 优先”的回归测试。
- [风险] 复用稳定 decorated 时若错误记录状态未按调用重置，可能污染后续异常恢复。 -> 缓解：在 wrapper 入口显式清空最后错误引用，并增加连续调用场景测试。
- [风险] provider cache key 扩大后，既有断言会失效。 -> 缓解：同步更新 provider handler 测试，明确断言新的三元 key。

## Migration Plan

1. 先扩展 `retry_utils` API，增加 `passthrough_exceptions` 并前移 decorator 构造时机。
2. 调整 `BackendProvider.execute()` 与 `_get_retry_wrapper()` 的参数和缓存键，使 provider policy 能完整下发到重试工具。
3. 更新回归测试，覆盖 passthrough 优先级、wrapper 复用次数和 provider 缓存键边界。
4. 运行定向 pytest 子集验证行为；若失败，优先回退到“保留 API 变更但禁用 provider 接入”的中间状态，而不是回退整个统一执行入口。

## Open Questions

- 是否需要在后续 change 中把 provider policy 的“直通异常 / 可重试异常”关系进一步文档化到公共类型注释之外。
- 是否需要额外暴露 retry decorator 构造次数的调试观测信息，帮助 watch 场景下排查性能回归。
