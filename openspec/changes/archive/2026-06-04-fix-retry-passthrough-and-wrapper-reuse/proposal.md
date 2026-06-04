## Why

当前多 backend 重试方案已经具备统一入口雏形，但还有两个关键缺口未闭环：`passthrough_exceptions` 只是声明未真正参与执行判定，且 `with_network_retry()` 虽然缓存了外层 wrapper，仍在每次调用时重复创建底层 retry decorator。现在需要单独收敛这两个问题，避免后续实现继续带着“规格已声明但行为未兑现”和“热路径开销仍未消除”的双重债务前进。

## What Changes

- 为 `retry_utils.with_network_retry()` 和 `call_with_network_retry()` 增加 `passthrough_exceptions` 语义，明确直通异常优先于自动重试。
- 调整 `BackendProvider` 的统一执行入口与缓存键，使 provider 级 retry wrapper 同时绑定 `retry_exceptions` 与 `passthrough_exceptions`，避免错误复用。
- 将底层 retry decorator 的构造移动到 wrapper 创建阶段，确保同一函数与同一异常策略只创建一次稳定包装器。
- 保留“重试耗尽后抛出最后一个真实 provider 异常”的现有语义，不向 facade 或调用方泄漏通用 `MaxRetriesReachedError`。
- 补充针对 passthrough 优先级、wrapper 复用边界、缓存键区分和 provider 执行入口的回归测试。

## Capabilities

### New Capabilities
- `provider-passthrough-policy`: 定义 provider 级统一重试中直通异常的优先级、缓存绑定方式与回归边界。
- `retry-wrapper-reuse`: 定义统一重试包装器的稳定复用语义，避免每次调用重复构造底层 retry decorator。

### Modified Capabilities

无。

## Impact

- 受影响代码：
  - `opentrade/retry_utils.py`
  - `opentrade/backends/base.py`
  - `tests/test_retry_regression.py`
  - `tests/test_facade_unit.py`
  - `tests/test_provider_handlers_extended.py`
- 受影响运行时行为：
  - provider 声明的 guardrail / 参数错误可明确走直通路径，不再只是静态配置。
  - 同一 provider capability 的 retry 包装器会与 passthrough 配置一同缓存，不会跨策略误复用。
  - watch / 批量执行等热路径会复用稳定 retry decorator，减少重复闭包与装饰开销。
- 主要风险：
  - 若 passthrough 与 retryable 异常集合划分不清，可能把本应重试的网络错误提前直通。
  - 若 wrapper 复用实现不当，可能破坏“重试耗尽后抛最后真实异常”的现有语义。
