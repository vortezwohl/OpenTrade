## 1. Retry 语义修复

- [x] 1.1 调整 `opentrade/retry_utils.py`，把“未传 retry_exceptions”与“显式空集合”分开处理
- [x] 1.2 调整 `opentrade/retry_utils.py`，让重试耗尽后恢复抛出最后一次真实 provider 异常，而不是对外暴露通用 `MaxRetriesReachedError`
- [x] 1.3 更新 `tests/test_retry_regression.py`，分别覆盖默认异常集合、显式禁用重试和耗尽后的最终异常语义

## 2. Provider 执行入口收敛

- [x] 2.1 重构 `opentrade/backends/base.py` 的 `BackendProvider.execute()`，移除无效的 `_build_retryable_handler_call()` 临时闭包或将其收敛为稳定 helper
- [x] 2.2 确保 provider 执行入口改造后，统一重试包装能够复用稳定调用对象，而不是每次热调用都重新生成包装器
- [x] 2.3 更新 `tests/test_provider_handlers_extended.py` 或新增对应断言，验证 provider 执行入口仍保留 side-effect 豁免与普通命令重试接入

## 3. Akshare 搜索重试闭环

- [x] 3.1 调整 `opentrade/backends/providers.py` 中 `AkshareSearchHandler` 的异常边界，让 provider retry policy 命中的网络异常直接上抛
- [x] 3.2 保留 `akshare` 搜索对非 retryable 局部目录失败的 `errors` 聚合行为，避免把所有目录局部失败都升级成整次请求失败
- [x] 3.3 为 `akshare instrument.search` 增加回归测试，验证网络异常会进入 provider 重试、非网络局部失败仍可返回聚合结果

## 4. 端到端回归验证

- [x] 4.1 更新 `tests/test_facade_unit.py` 或相关 scaffold 测试，验证 provider 语义异常在重试耗尽后仍按最终 provider 形态暴露
- [x] 4.2 运行并复核最小相关测试集，至少覆盖 `tests/test_retry_regression.py`、`tests/test_provider_handlers_extended.py`、`tests/test_facade_unit.py`
- [x] 4.3 若 provider 语义修复影响现有 `auto` / yfinance 脚手架断言，同步补齐 `tests/test_multi_backend_scaffold.py` 的异常期望
