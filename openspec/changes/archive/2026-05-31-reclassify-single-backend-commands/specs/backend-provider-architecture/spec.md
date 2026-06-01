## MODIFIED Requirements

### Requirement: 系统必须支持运行时 backend 解析
系统 MUST 支持在运行时按命令约束和用户选择解析目标 backend，并对单 backend 的 provider-extension 命令提供显式的命令默认路由语义；系统 SHALL NOT 继续把单 backend 的业务命令视为 shared。

#### Scenario: 用户显式指定 backend
- **WHEN** 用户为命令传入 `--backend`
- **THEN** 系统 MUST 优先尝试解析到该 backend provider

#### Scenario: provider-specific 扩展命令使用命令默认 backend
- **WHEN** 用户执行某 provider-specific 扩展命令且未传入 `--backend`
- **THEN** 系统 MUST 默认解析到该命令所属 provider，并把该选择标记为命令默认路由

#### Scenario: 命令与 backend 冲突时拒绝执行
- **WHEN** 用户选择的 backend 与命令支持矩阵冲突
- **THEN** 系统 MUST 在实际调用前给出明确冲突错误，并说明该命令支持哪些 backend 以及默认会路由到哪个 backend

#### Scenario: 单 backend 业务命令不再通过 shared 默认 backend 解析
- **WHEN** 某命令只支持一个 backend
- **THEN** 系统 MUST 通过 provider-extension 语义解析该命令，而 SHALL NOT 把它当作 shared 命令再走通用默认 backend 路径
