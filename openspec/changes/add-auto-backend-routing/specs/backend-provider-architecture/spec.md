## MODIFIED Requirements

### Requirement: 系统必须支持运行时 backend 解析
系统 MUST 支持在运行时按命令约束和用户选择解析目标 backend；系统 MAY 允许某些 backend 标识作为路由策略存在而不是实际 provider；默认共享命令 backend MUST 改为 `auto`，而 provider-extension 在 `auto` 或未显式指定 backend 时 MUST 自动适配到所属 provider。

#### Scenario: 用户显式指定 concrete backend
- **WHEN** 用户为命令传入具体 backend
- **THEN** 系统 MUST 优先尝试解析到该 backend provider

#### Scenario: 共享命令默认解析到 auto
- **WHEN** 用户执行共享命令且未传入 `--backend`
- **THEN** 系统 MUST 默认按 `auto` backend 语义解析，而不是直接解析到固定 concrete backend

#### Scenario: provider-extension 在 auto 下自动适配所属 provider
- **WHEN** 用户执行 provider-extension 命令且未传入 `--backend`，或显式传入 `--backend auto`
- **THEN** 系统 MUST 自动解析到该命令所属 provider，并把该选择标记为命令默认路由或 auto 适配结果

#### Scenario: 命令与 backend 冲突时拒绝执行
- **WHEN** 用户选择的 concrete backend 与命令支持矩阵冲突
- **THEN** 系统 MUST 在实际调用前给出明确冲突错误
