## Why

当前 `efinance-cli` 的命令注册、参数生成、执行调用、增强回补与帮助文本仍然直接绑定 `efinance` 上游函数，导致系统虽然已经具备一定分层，但本质上仍是“第三方函数驱动的单后端 CLI”。这使得 `akshare` 无法被干净接入，也阻断了未来接入 `yfinance` 等其他后端的可持续演进路径。

现在推进这项变更的原因是：项目已经明确需要支持多后端、允许后端能力差异、且不再以旧版本命令兼容为目标。如果继续围绕现有 `efinance` 命令结构做局部适配，后续只会累积更多条件分支、伪统一语义和跨层耦合，无法形成稳定的长期架构。

## What Changes

- **BREAKING**：重构 CLI 的稳定对象，从“上游函数名与函数签名”切换为“命令语义、能力标识、请求契约与结果契约”。
- **BREAKING**：废弃以 `efinance.xxx.yyy` 为中心的命令注册模型，改为以后端无关的 `CommandDefinition + CapabilityDescriptor` 管理共享命令。
- 引入 `BackendProvider`、`CapabilityHandler`、`BackendResolver` 与 `CommandFacade`，把运行时后端选择、能力路由和命令执行骨架解耦。
- 为共享命令建立显式请求结构与参数校验模型，不再从第三方函数签名动态反射 CLI 参数。
- 为共享能力建立分能力的标准结果契约，例如历史行情、实时行情、资料信息、搜索结果等，允许后端保留原始字段与扩展字段。
- 建立后端扩展命令机制，使 `akshare` 等后端可以暴露共享命令之外的专属命令组，而不污染共享命令树。
- 调整 enrichment、observation、rendering，使其优先依赖标准结果契约而不是具体后端或原始字段集合。
- 首批实施以 `efinance` 与 `akshare` 为目标后端设计，并为未来接入 `yfinance` 预留可扩展的 provider 架构，但本变更不要求实现 `yfinance`。

## Capabilities

### New Capabilities
- `command-capability-catalog`: 定义后端无关的共享命令目录、能力标识、请求构建与支持矩阵。
- `backend-provider-architecture`: 定义多后端 provider、能力处理器、运行时解析与能力检查机制。
- `unified-result-contracts`: 定义按能力拆分的标准结果契约、标准化流程与原始字段保留策略。
- `provider-extension-commands`: 定义后端专属命令的注册、帮助展示、运行时约束与共享骨架复用规则。
- `backend-agnostic-execution-pipeline`: 定义请求校验、能力路由、标准化、增强、观察与渲染的统一执行管线。

### Modified Capabilities

无。

## Impact

- 受影响代码包括：
  - `efinance_cli/registry.py`
  - `efinance_cli/commands.py`
  - `efinance_cli/executor.py`
  - `efinance_cli/models.py`
  - `efinance_cli/enrichment/service.py`
  - `efinance_cli/observation.py`
  - `efinance_cli/rendering.py`
  - 新增 `backends/`、能力目录、标准化模块、命令目录相关代码
- 会引入新的内部抽象与目录结构，并重写命令定义、参数生成和执行入口。
- 会改变现有命令树与帮助文本组织方式，属于显式破坏性调整。
- 不要求新增运行时第三方依赖，但可能需要在开发与测试层补充多后端合同测试、假后端测试夹具和更细粒度的 CLI 回归测试。
