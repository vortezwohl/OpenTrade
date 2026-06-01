## Why

当前命令目录仍把大量只支持单一 backend 的命令注册为 `shared`，这让 `shared` 的语义发生了漂移: 它既像“后端无关共享能力”，又像“暂时只有一个 provider 实现的普通命令”。这会让支持矩阵、默认 backend 路由、测试断言和后续 `yfinance` 接入方案都变得模糊，因为系统已经无法仅凭命令类别判断“它是否真的可切换后端”。

现在需要单独推进这次重整，是因为你已经把新规则明确为硬约束: 所有单后端支持的命令都必须归类为 `provider-extension`。如果不先把这条边界收紧，后续无论是继续接入 `yfinance`，还是维护现有 `efinance` / `akshare` 命令面，都会持续在“共享命令”和“单 provider 命令”之间积累语义债务。

## What Changes

- **BREAKING**：重定义 `shared` 的分类语义，`shared` 只保留真正支持多 backend 的命令。
- **BREAKING**：凡是当前仅支持单一 backend 的命令，全部改归 `provider-extension`，即使它们继续挂在现有业务语义命令树下也是如此。
- 调整 command catalog 的生成规则，不再把“只有一个 supported backend 的命令”注册为 `CommandKind.SHARED`。
- 为迁移后的单 backend 命令补齐 provider 归属、默认 backend 路由和帮助文本展示规则。
- 调整 provider registry 和扩展命令装配逻辑，使当前大量 `efinance` 单 backend 资产域 / utility 命令可以批量作为 extension 暴露。
- 同步更新 backend 解析、执行管线、CLI 回归测试和文档，确保“单 backend 命令 = provider-extension”成为可验证约束。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `command-capability-catalog`: 修改共享命令定义规则，明确 `shared` 只允许多 backend 命令，单 backend 命令不得进入 shared catalog。
- `provider-extension-commands`: 修改 extension 命令边界，明确所有单 backend 命令都必须作为 provider-extension 建模，即使它们继续使用稳定业务语义路径。
- `backend-provider-architecture`: 修改 backend 解析要求，补充“单 backend 命令通过 provider-extension 默认路由”的运行时语义。
- `backend-agnostic-execution-pipeline`: 修改统一执行要求，确保从 shared 迁出的单 backend 命令仍复用同一执行骨架与 watch 路径。

## Impact

- 主要影响代码：
  - `efinance_cli/command_catalog.py`
  - `efinance_cli/commands.py`
  - `efinance_cli/backends/providers.py`
  - `efinance_cli/backends/factory.py`
  - `efinance_cli/backends/resolver.py`
  - `tests/test_multi_backend_scaffold.py`
  - `tests/test_cli_full_regression.py`
  - `docs/cli-设计与使用说明.md`
  - `docs/架构设计说明.md`
- 这是一次命令分类与支持矩阵语义收紧，不一定要求所有 CLI 路径改名，但会改变大量命令在内部的命令类别与 provider 归属。
- 这项 change 会影响后续 `add-yfinance-backend-support` 的命令归类判断，应优先于 `yfinance` 接入实现落地。
