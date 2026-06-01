## Why

当前代码基线已经完成“单 backend 命令重分类”并归档到 `archive/2026-05-31-reclassify-single-backend-commands`：`shared` 只保留真正多 backend 的命令，单 backend 命令已经稳定下沉为 `provider-extension`。这一步把命令分类边界理顺了，但运行时 backend 路由仍停留在单次只命中一个 concrete provider 的状态。

当前事实是：

- `BackendName` 已包含 `yfinance`，并且运行时注册表已经正式接入 `efinance`、`akshare` 与 `yfinance`；
- [resolver](/D:/Projects/PythonProjects/efinance-cli/efinance_cli/backends/resolver.py) 仍把共享命令默认解析到固定 `BackendName.EFINANCE`；
- [facade](/D:/Projects/PythonProjects/efinance-cli/efinance_cli/facade.py) 仍只会对单个 `backend.resolved` 调一次 provider handler；
- `provider-extension` 已具备“未显式传 backend 时自动路由到所属 provider”的基线，但还不支持显式 `auto` 语义；
- `yfinance` 相关帮助文本、支持矩阵与扩展命令已经落地，因此 `auto` 设计需要直接建立在“三个正式 provider 共存”的事实上，而不是旧的 optional provider 假设上。

现在需要单独推进 `auto` backend，是因为新的运行时策略已经明确：默认 `--backend` 就应该等于 `auto`，而 `auto` 不只是“选一个默认 provider”，而是一个受控降级链，按 `akshare -> yfinance -> efinance` 顺序尝试同一个共享命令；同时它还要能对 provider 特定命令做自动 backend 适配。如果不把这层策略提升为正式能力，后续接入 `yfinance` 之后，默认路径仍会停留在“默认 backend 太死、失败恢复全靠用户手工重试”的状态。

## What Changes

- **BREAKING**：把共享命令的默认 backend 从固定 `efinance` 改为 `auto`。
- **BREAKING**：把运行时默认 concrete backend 优先级从 `efinance` 改为 `akshare` 优先。
- 新增 `auto` backend 语义，允许在单次命令执行中按 `akshare -> yfinance -> efinance` 的受控顺序尝试多个 backend。
- 为 `auto` 增加支持矩阵过滤逻辑，只尝试当前命令真正支持、且当前运行时可用的 backend。
- 为 provider-extension 命令定义 `auto` 自适配行为：当用户未显式指定 backend 或显式指定 `auto` 时，系统能自动落到该扩展命令所属 provider，而不是错误参与无意义的多 backend 降级。
- 调整统一执行骨架，使最终成功命中的 concrete backend 能回写到运行时上下文，保证 enrichment、observation 和 watch 继续使用真实命中 backend，而不是保留 `auto` 这一抽象选择。
- 为多 backend 失败聚合、错误分类和最终报错增加显式规则，避免把用户输入错误误判成可继续降级的 provider 故障。

## Capabilities

### New Capabilities

- `auto-backend-routing`: 定义 `auto` backend 的选择语义、候选链顺序、支持矩阵过滤与最终 backend 命中规则。
- `backend-failover-policy`: 定义哪些错误允许进入下一个 backend、哪些错误必须立即失败，以及全链路失败时如何聚合错误信息。

### Modified Capabilities

- `backend-provider-architecture`: 修改运行时 backend 解析要求，允许 `auto` 作为非真实 provider 的路由策略存在，并把默认 backend 语义改为 `auto`。
- `backend-agnostic-execution-pipeline`: 修改统一执行骨架，支持单次命令中的多 backend 尝试，并要求最终命中 backend 传播到增强、观察和 watch 链路。
- `provider-extension-commands`: 修改 provider-extension 默认路由规则，要求 `auto` 能自动适配到扩展命令所属 provider，而不是参与无意义的跨 provider 降级。

## Impact

- 主要影响代码：
  - `efinance_cli/models.py`
  - `efinance_cli/backends/resolver.py`
  - `efinance_cli/facade.py`
  - `efinance_cli/executor.py`
  - `efinance_cli/enrichment/service.py`
  - `efinance_cli/commands.py`
  - `tests/test_multi_backend_scaffold.py`
  - `tests/test_cli_full_regression.py`
  - `tests/test_observation_smoke.py`
  - `docs/cli-设计与使用说明.md`
  - `docs/架构设计说明.md`
- 这不是新增 provider，而是新增一层运行时路由策略；会改变未显式传 `--backend` 时的默认行为。
- 这项 change 以前置归档 `reclassify-single-backend-commands` 为基线，不再重新讨论 shared / provider-extension 的分类规则。
- 这项 change 与 `add-yfinance-backend-support` 强相关：本轮复查确认 `yfinance` 已完成正式注册，因此 `auto` 候选链实现时应直接把它视为正式候选；保留的过滤逻辑应面向“命令支持矩阵 + provider 可用性”这一通用规则，而不是继续依赖 optional provider 跳过分支。
