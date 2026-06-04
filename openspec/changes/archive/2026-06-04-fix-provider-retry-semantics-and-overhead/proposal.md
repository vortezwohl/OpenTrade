## Why

当前 provider 级统一重试入口已经落地，但还有两类关键问题没有收口。第一类是功能语义问题：重试耗尽后对外异常被改写成通用 `MaxRetriesReachedError`，`akshare` 搜索路径也仍然绕过统一重试入口，导致“统一多后端网络重试”在真实路径上不闭环。第二类是执行入口自身的噪音：provider 执行热路径里的闭包包装和空分层代码没有带来业务收益，却持续增加开销与维护负担。

现在需要单独推进这项 change，是因为这些问题已经直接落在新引入的 provider 执行入口上。如果不尽快修正，后续继续沿用这套入口扩展 backend 或补测试时，会把错误的异常契约和无效的执行包装进一步固化到公共骨架里。

## What Changes

- 修复 provider 级网络重试在“重试耗尽”场景下的最终异常语义，要求对外保留 provider 已翻译好的限流/网络错误，而不是暴露无上下文的通用重试异常。
- 修复 `akshare` 搜索路径吞掉底层网络异常的问题，使其能真正接入统一 provider 重试，而不是在 handler 内部把瞬时失败降格为普通 `RuntimeError` 或残缺结果。
- 精简 `BackendProvider.execute()` 的内部包装方式，移除没有实际分层效果的空 `try/except` 闭包，并让统一重试包装尽可能复用稳定函数对象，避免每次热调用重复构造包装器。
- 收敛 `retry_utils` 的接口语义，明确区分“未传 retry 异常集合”和“显式关闭重试”的语义边界，避免未来调用方无法通过空集合禁用自动重试。
- 为上述行为补齐针对 provider 语义、`akshare` 搜索、wrapper 复用与 guardrail 直通的回归测试。

## Capabilities

### New Capabilities

- `provider-retry-semantics`: 定义 provider 级统一重试在重试耗尽、guardrail 直通、`akshare` 搜索接入和 side-effect 豁免下的最终行为语义。
- `provider-execution-overhead`: 定义 provider 执行入口与 retry 工具在热路径上的包装约束，避免无效闭包和不可复用包装器持续叠加开销。

### Modified Capabilities

无。

## Impact

- 主要影响代码：
  - `opentrade/retry_utils.py`
  - `opentrade/backends/base.py`
  - `opentrade/backends/providers.py`
  - `tests/test_retry_regression.py`
  - `tests/test_provider_handlers_extended.py`
  - `tests/test_facade_unit.py`
  - 视实现方式可能补充 `tests/test_multi_backend_scaffold.py`
- 主要影响行为：
  - `yfinance` 和未来其他 provider 在重试耗尽后需要继续暴露 provider 语义异常；
  - `akshare instrument.search` 必须真正进入 provider 级重试闭环；
  - provider 执行入口需要减少无收益的包装开销，但不能改变现有 `auto` failover 与 side-effect 边界。
- 风险：
  - 改动会触碰当前刚引入的 provider 执行骨架，测试桩和异常断言需要同步更新；
  - 若 `akshare` 搜索的异常上抛边界收敛不当，可能把原本允许降级的目录局部失败错误全部提升为整次请求失败。
