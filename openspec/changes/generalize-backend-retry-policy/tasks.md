## 1. 重试基础设施收口

- [x] 1.1 重构 `opentrade/retry_utils.py` 的模块说明、缓存标记与对外命名语义，移除 `efinance` 专属表述并保持现有签名保真与退避能力。
- [x] 1.2 为统一重试工具补或更新回归测试，验证其仍能处理网络异常恢复、超限失败和基础异常注册表边界。

## 2. Provider 统一执行入口

- [x] 2.1 在 `opentrade/backends/base.py` 为 `BackendProvider` 增加统一执行入口，以及 provider 级 retry policy 的最小稳定接口。
- [x] 2.2 在 `opentrade/backends/providers.py` 为 `efinance`、`akshare`、`yfinance` 声明各自的可重试异常、限流异常和直接透传异常策略。
- [x] 2.3 把 `efinance` handler 内现有局部 `call_with_network_retry` 包装迁移到 provider 统一执行入口，并保留 side-effect 命令默认跳过自动重试的边界。

## 3. Facade 与 auto 集成

- [x] 3.1 调整 `opentrade/facade.py`，让 single backend 路径通过 provider 统一执行入口，而不是直接调用 `handler.execute`。
- [x] 3.2 调整 `opentrade/facade.py` 的 `auto` 路径，确保每个 candidate backend 先完成 provider 内部重试，再按既有 failover eligibility 规则决定是否切换到下一个 backend。
- [x] 3.3 复查并保持 `final_backend` 回写语义，确保 provider 统一执行入口引入后 enrichment、observation 和 watch 仍使用真实命中 backend。

## 4. 回归测试与验证

- [x] 4.1 更新 `tests/test_provider_handlers_extended.py`，让断言围绕 provider 统一执行入口与 side-effect 豁免，而不是旧的 handler 内局部包装点。
- [x] 4.2 更新 `tests/test_facade_unit.py`，覆盖 single backend、限流重试、side-effect 跳过和 `auto`“先内部重试、后 failover” 的执行顺序。
- [x] 4.3 运行并复查与本 change 直接相关的测试集合，至少覆盖 `tests/test_retry_regression.py`、`tests/test_provider_handlers_extended.py` 和 `tests/test_facade_unit.py`。
