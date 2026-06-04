## Why

当前仓库已经有统一的多 backend 执行骨架，但底层网络重试仍主要以 `efinance` 专属方式挂在个别 handler 内部。这导致同样属于网络访问的 `akshare`、`yfinance` 和后续 backend 无法复用同一套重试能力，横切策略也无法在运行时统一演进。

现在需要单独推进这项 change，是因为多 backend 运行时已经稳定成型，`auto` 路由也已经存在具体 candidate 链语义。如果继续把重试逻辑散落在 provider 内部局部位置，后续任何 backend 扩展都会重复做“手工补 retry”，并且难以定义“先在当前 backend 内重试，再决定是否跨 backend failover”的稳定规则。

## What Changes

- 把底层网络重试从 `efinance` 局部包装提升为全部 backend 可扩展的 provider 级统一能力。
- 为 `BackendProvider` 增加稳定执行入口，使 provider 能在单一位置挂载网络重试、异常分类和 side-effect 豁免逻辑，而不是让各个 handler 分散决定。
- 明确把限流错误纳入可重试范围，而不是默认直接失败；同时保留 provider 自己对限流语义的错误翻译能力。
- 规定 `auto` 模式下的执行顺序：先在当前 concrete backend 内完成其网络重试策略，再按既有 failover 规则决定是否切换到下一个 backend。
- 为 side-effect 命令保留“不自动重试”的默认边界，避免下载、写入、上传类操作被透明重复执行。
- 为全 backend 通用重试补充 facade/provider/unit regression 测试，覆盖 `efinance`、`akshare`、`yfinance` 与 `auto` 交互路径。

## Capabilities

### New Capabilities

- `backend-retry-policy`: 定义多 backend 运行时中的网络重试边界、异常分类、限流重试、side-effect 豁免与 provider 扩展方式。
- `provider-execution-entry`: 定义 `BackendProvider` 的统一执行入口，以及 provider 级横切逻辑如何包裹 capability handler。

### Modified Capabilities

无。

## Impact

- 主要影响代码：
  - `opentrade/retry_utils.py`
  - `opentrade/backends/base.py`
  - `opentrade/backends/providers.py`
  - `opentrade/facade.py`
  - `tests/test_retry_regression.py`
  - `tests/test_provider_handlers_extended.py`
  - `tests/test_facade_unit.py`
- 主要影响运行时行为：
  - `efinance` 不再是唯一具备网络重试挂载点的 backend；
  - `akshare`、`yfinance` 和未来新 backend 可以以相同扩展点接入网络重试；
  - `auto` 模式会先消化当前 backend 的瞬时网络失败，再决定是否切换候选 backend。
- 主要影响风险面：
  - 限流重试可能放大单次请求等待时间，需要在设计中明确重试上限和异常分类；
  - provider 级统一入口会改变部分测试桩和 mock 挂载位置，需要同步调整测试基线。
