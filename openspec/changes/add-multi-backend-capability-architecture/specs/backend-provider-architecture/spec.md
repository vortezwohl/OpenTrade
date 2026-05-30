## ADDED Requirements

### Requirement: 系统必须通过 BackendProvider 管理后端能力
系统 MUST 把每个数据后端建模为 `BackendProvider`，并由 provider 声明其身份、支持的 capability、扩展命令和 handler 获取方式。

#### Scenario: provider 声明支持的 capability
- **WHEN** 系统加载某个 backend provider
- **THEN** 该 provider MUST 能回答自己支持哪些 capability

#### Scenario: provider 可以声明扩展命令
- **WHEN** 某个 backend 拥有共享命令之外的专属能力
- **THEN** 系统 SHALL 允许该 provider 注册扩展命令，而不要求把该能力伪装成共享命令

### Requirement: 系统必须以 CapabilityHandler 作为最小调用单元
系统 MUST 通过 `CapabilityHandler` 处理具体能力调用，而 SHALL NOT 要求每个 provider 实现一组全能型固定方法。

#### Scenario: 共享 capability 路由到对应 handler
- **WHEN** 用户执行一个共享命令
- **THEN** 系统 MUST 根据 backend 和 capability 解析到唯一的 capability handler

#### Scenario: 不支持的 capability 不生成伪 handler
- **WHEN** provider 未实现某个 capability
- **THEN** 系统 SHALL 明确标记为不支持，而 SHALL NOT 生成返回空值的占位 handler

### Requirement: 系统必须支持运行时 backend 解析
系统 MUST 支持在运行时按命令约束和用户选择解析目标 backend。

#### Scenario: 用户显式指定 backend
- **WHEN** 用户为命令传入 `--backend`
- **THEN** 系统 MUST 优先尝试解析到该 backend provider

#### Scenario: 命令与 backend 冲突时拒绝执行
- **WHEN** 用户选择的 backend 与命令支持矩阵冲突
- **THEN** 系统 MUST 在实际调用前给出明确冲突错误
