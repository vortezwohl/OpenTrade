## MODIFIED Requirements

### Requirement: 系统必须通过统一执行骨架处理共享命令与扩展命令
系统 MUST 使用统一执行骨架处理命令调用，包括请求校验、backend 解析、能力调用、标准化、增强、观察、渲染和输出；从 shared 迁出的单 backend 命令在成为 provider-extension 后仍 MUST 复用同一执行骨架。

#### Scenario: 共享命令执行遵循固定步骤
- **WHEN** 用户执行任一共享命令
- **THEN** 系统 MUST 依次执行请求校验、backend 解析、能力检查、handler 调用、结果标准化、增强、观察、渲染与输出

#### Scenario: 扩展命令执行遵循同一骨架
- **WHEN** 用户执行 provider 扩展命令
- **THEN** 系统 MUST 复用同一执行骨架，只在命令目录与 handler 绑定上与共享命令不同，即使该命令已挂载到业务语义命令树中也是如此

#### Scenario: 迁出的单 backend 命令继续走统一执行主链
- **WHEN** 某原本位于 shared catalog 的单 backend 命令被重分类为 provider-extension
- **THEN** 系统 MUST 继续通过同一执行骨架处理该命令，而 SHALL NOT 为这类迁移命令引入特殊旁路

### Requirement: watch 模式必须复用同一命令请求与 backend 解析结果
系统 MUST 让 watch 模式重复执行同一标准请求与能力解析路径，而 SHALL NOT 为 watch 单独实现旁路逻辑。

#### Scenario: watch 模式重复同一能力调用
- **WHEN** 用户对支持 watch 的命令启用 watch
- **THEN** 系统 MUST 在每次刷新时复用相同的命令请求结构与 backend 选择逻辑，包括 provider-specific 扩展命令在业务语义路径下的默认 backend 解析结果

#### Scenario: 不支持 watch 的命令在刷新前被拒绝
- **WHEN** 用户对不支持 watch 的命令启用 watch
- **THEN** 系统 MUST 在进入循环前返回明确错误
