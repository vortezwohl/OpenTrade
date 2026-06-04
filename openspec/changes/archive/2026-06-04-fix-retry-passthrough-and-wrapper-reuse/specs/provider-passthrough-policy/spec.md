## ADDED Requirements

### Requirement: Provider 级直通异常必须优先于自动重试
系统 MUST 允许 provider 在统一重试工具中声明 `passthrough_exceptions`，并在命中时直接透传原异常；这些异常 SHALL NOT 进入自动网络重试，即使它们同时属于可重试异常集合。

#### Scenario: guardrail 异常直接透传
- **WHEN** provider handler 抛出命中 `passthrough_exceptions` 的 `ValueError`、invalid period 或其他 guardrail 异常
- **THEN** 统一重试入口 MUST 直接把原异常返回上层，且 SHALL NOT 触发额外重试

#### Scenario: passthrough 优先级高于 retryable
- **WHEN** 同一个异常类型同时出现在 `retry_exceptions` 与 `passthrough_exceptions` 中
- **THEN** 系统 MUST 采用直通语义并立即结束当前调用，而 SHALL NOT 进入自动重试

### Requirement: Provider 重试包装器缓存必须绑定完整异常策略
系统 MUST 将 provider capability 的重试包装器缓存绑定到完整异常策略，包括 `retry_exceptions` 与 `passthrough_exceptions`；不同 passthrough 配置 SHALL NOT 复用同一个缓存包装器。

#### Scenario: 相同 capability 不同 passthrough 配置不复用 wrapper
- **WHEN** 同一个 provider capability 先后以相同 `retry_exceptions` 但不同 `passthrough_exceptions` 执行
- **THEN** 系统 MUST 为两组策略分别缓存独立 wrapper，且 SHALL NOT 命中旧策略下的缓存对象

#### Scenario: 相同 capability 相同完整策略复用 wrapper
- **WHEN** 同一个 provider capability 以相同 `retry_exceptions` 和相同 `passthrough_exceptions` 重复执行
- **THEN** 系统 MUST 复用同一个已缓存的 wrapper，而 SHALL NOT 重复创建 provider 级稳定包装器
