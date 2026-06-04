# retry-wrapper-reuse Specification

## Purpose
TBD - created by archiving change fix-retry-passthrough-and-wrapper-reuse. Update Purpose after archive.
## Requirements
### Requirement: 统一重试工具必须复用稳定 retry decorator
系统 MUST 在创建网络重试 wrapper 时一次性构造底层 retry decorator，并在后续调用中复用该稳定对象；同一函数与同一异常策略 SHALL NOT 在每次调用时重复装饰。

#### Scenario: 同一函数重复调用时复用底层 decorator
- **WHEN** 调用方对同一个函数和同一组异常策略重复执行 `with_network_retry()` 返回的 wrapper
- **THEN** 系统 MUST 复用首次构造的底层 retry decorator，且 SHALL NOT 在每次调用路径中重新执行 `on_exceptions(...)(tracked_call)`

### Requirement: 重试耗尽后必须继续抛出最后一个真实异常
系统 MUST 在稳定复用 retry decorator 的同时保留最后一次真实 provider 异常，并在重试耗尽后对外抛出该异常；系统 SHALL NOT 把内部 `MaxRetriesReachedError` 作为最终对外错误替代真实异常。

#### Scenario: 重试耗尽后恢复最后真实异常
- **WHEN** 统一重试 wrapper 在达到重试上限后仍持续收到命中 retry 策略的异常
- **THEN** 系统 MUST 对外抛出最后一次真实异常对象或其等价语义，而 SHALL NOT 只暴露通用 `MaxRetriesReachedError`

### Requirement: 默认重试与显式禁用重试的语义必须保持区分
系统 MUST 继续把 `retry_exceptions=None` 解释为使用默认网络异常集合，把 `retry_exceptions=()` 解释为显式禁用自动重试；二者 SHALL NOT 因稳定 decorator 复用而被混淆。

#### Scenario: 显式空集合不回退到默认异常集
- **WHEN** 调用方以 `retry_exceptions=()` 调用统一重试 wrapper
- **THEN** 系统 MUST 直接执行原函数并保留单次失败语义，而 SHALL NOT 回退到默认网络异常集合或触发隐式自动重试

