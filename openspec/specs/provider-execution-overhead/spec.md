# provider-execution-overhead Specification

## Purpose
TBD - created by archiving change fix-provider-retry-semantics-and-overhead. Update Purpose after archive.
## Requirements
### Requirement: Provider 执行热路径不得依赖无效的临时闭包包装
系统 MUST 避免在每次 provider 执行时构造仅用于原样转发异常的临时闭包；统一重试入口 SHALL 使用稳定调用对象或等价的可复用执行包装，以减少热路径上的重复包装开销。

#### Scenario: 连续执行同一 handler 时复用稳定包装对象
- **WHEN** 同一 provider/handler 在 watch 或批量请求中连续执行
- **THEN** 系统 MUST 允许统一重试包装复用稳定调用对象，而 SHALL NOT 因每次新建临时闭包导致包装器缓存持续失效

### Requirement: Provider 执行入口中的异常分层代码必须有真实语义收益
系统 SHALL NOT 保留只做原样 `raise`、不改变控制流也不提供策略语义的异常分层包装代码；若 provider 执行入口引入额外 helper，它 MUST 承担清晰、可测试的策略职责。

#### Scenario: 空异常分层逻辑被移除或收敛
- **WHEN** provider 执行入口对 handler 调用进行封装
- **THEN** 该封装 MUST 具备明确的策略职责，例如 guardrail 直通或稳定包装复用；若没有额外职责，系统 MUST 直接调用更简单的稳定执行路径

### Requirement: retry_utils 必须区分默认重试与显式禁用重试
系统 MUST 将 `retry_exceptions=None` 解释为“使用默认网络异常集合”，并将 `retry_exceptions=()` 解释为“显式禁用自动重试”；两者 SHALL NOT 被视为同一语义。

#### Scenario: 显式空集合不会回退到默认网络异常集合
- **WHEN** 调用方以 `retry_exceptions=()` 调用统一重试包装接口
- **THEN** 系统 SHALL NOT 回退到默认网络异常集合，也 SHALL NOT 因隐式重试改变单次调用失败语义

