## Why

当前代码基线已经完成多后端执行骨架与单 backend 命令重分类：

- `shared` 只保留真正多 backend 的命令；
- 单 backend 命令已经稳定下沉到 `provider-extension`；
- `CommandExecutor -> CommandFacade -> BackendProvider -> CapabilityHandler` 主链可复用；
- `BackendName.YFINANCE` 与 optional provider 占位已经存在。

但运行时注册表、共享命令支持矩阵、结果标准化、观察链路与回归测试仍停留在 `efinance + akshare` 双后端状态。也就是说，`yfinance` 目前只是一个“被枚举但不可执行”的预留标识，还没有变成正式 provider。

之所以要先做完整提案，而不是直接补几个 handler，是因为 `yfinance` 的能力结构与现有后端明显不同：它把搜索、历史、快照、资料面、基金资料、WebSocket 实时流和期权链拆在不同入口，并且真实网络访问受 Yahoo 限流影响明显。如果不先在架构层明确共享能力、扩展能力、降级策略与验证边界，后续实现很容易退化成“能调通几个 API 就算支持”的伪集成。

当前还需要明确一个边界：`add-auto-backend-routing` 尚未落地，所以 `yfinance` 首轮接入必须先保证显式 `--backend yfinance` 路径可用，而不能把“默认 auto 自动参与降级链”当成已经存在的运行时前提。

## What Changes

- 新增 `yfinance` backend provider，使其从 optional provider 升级为运行时可解析、可执行、可测试的正式后端。
- 为 `instrument.search`、`stock.price.history`、`stock.profile`、`fund.nav.history`、`fund.profile`、`quote.price.history`、`quote.price.latest`、`quote.profile` 等共享命令补充 `yfinance` 支持矩阵与标准化策略。
- 为 `yfinance.Search`、`Ticker.history()`、`FastInfo` / `Quote.info`、`FundsData` 建立稳定的 capability handler 与结果契约映射。
- 为 `yfinance` 增加 provider-extension 命令组，用于承接不适合塞进共享命令面的 Yahoo 专属能力，例如基金持仓画像、新闻、期权链或后续实时流入口。
- 明确遵循当前命令分类硬规则：凡是仅支持 `yfinance` 单 backend 的命令，必须建模为 provider-extension，而不能留在 shared catalog 中占位。
- 引入 `yfinance` 语义专属的请求归一化与参数转换规则，解决当前共享 schema 与 Yahoo symbol / interval / period 语义不完全一致的问题。
- 为 Yahoo 限流、历史区间限制、市场覆盖不完整、字段缺失与资料面不稳定建立显式错误模型、降级路径和测试约束。
- 扩展 observation / enrichment / rendering 兼容面，确保 `yfinance` 返回的标准结果能够进入现有观察链，而不会偷偷回退到其他 provider 做补数。

## Capabilities

### New Capabilities

- `yfinance-backend-enablement`: 把 `yfinance` 从预留 provider 升级为正式 provider，并定义其运行时注册、依赖探测、错误暴露与支持矩阵约束。
- `yfinance-shared-command-support`: 定义 `yfinance` 在共享命令面上的最小闭环支持范围、参数映射、标准化行为与不支持场景。
- `yfinance-provider-extensions`: 定义 Yahoo 专属能力如何通过 provider-extension 命令暴露，而不污染共享命令树。
- `yfinance-runtime-guardrails`: 定义 Yahoo 限流、历史拉取边界、市场语义差异、字段缺失和降级策略的运行时防护要求。

### Modified Capabilities

无。

## Impact

- 受影响代码主要包括：
  - `efinance_cli/backends/factory.py`
  - `efinance_cli/backends/providers.py`
  - `efinance_cli/backends/resolver.py`
  - `efinance_cli/command_catalog.py`
  - `efinance_cli/contracts.py`
  - `efinance_cli/enrichment/*`
  - `efinance_cli/observation.py`
  - `efinance_cli/rendering.py`
  - `tests/test_multi_backend_scaffold.py` 及新增的 `yfinance` provider 合同测试
- 受影响依赖与运行时系统：
  - 已安装的 `yfinance==1.4.1`
  - Yahoo Finance HTTP / WebSocket 数据端点
  - 现有多后端支持矩阵与帮助文本展示
- 兼容性影响：
  - 会扩大 `--backend yfinance` 的共享命令可用面；
  - 会新增 Yahoo 专属扩展命令；
  - 不承诺所有现有共享命令都能被 `yfinance` 覆盖，未覆盖能力必须显式报错而不是静默回退。
- 这项 change 以前置归档 `reclassify-single-backend-commands` 为命令分类基线，并与 `add-auto-backend-routing` 保持解耦：先保证显式 `--backend yfinance` 路径成立，再让未来 `auto` 路由消费它。
