## 1. Retry API 收敛

- [x] 1.1 为 `opentrade/retry_utils.py` 中的 `with_network_retry()` 和 `call_with_network_retry()` 增加 `passthrough_exceptions` 参数，并保持 `None` 与 `()` 的现有语义区分。
- [x] 1.2 将底层 retry decorator 的构造移动到 wrapper 创建阶段，保留“重试耗尽后抛最后真实异常”的对外行为。

## 2. Provider 接入调整

- [x] 2.1 调整 `BackendProvider.execute()` 与 `_get_retry_wrapper()`，把 provider policy 的 `passthrough_exceptions` 下发到统一重试工具。
- [x] 2.2 扩展 provider 级 `_retry_wrapper_cache` 的 key，使其同时绑定 capability、`retry_exceptions` 与 `passthrough_exceptions`。

## 3. 回归验证

- [x] 3.1 在 `tests/test_retry_regression.py` 中补充 passthrough 优先级、稳定 decorator 复用和 `retry_exceptions=()` 边界测试。
- [x] 3.2 在 `tests/test_facade_unit.py` 与 `tests/test_provider_handlers_extended.py` 中补充 provider 直通异常与缓存键区分测试。
- [x] 3.3 运行定向 pytest 子集，确认新增方案不破坏既有 provider 错误语义与 side-effect 边界。
