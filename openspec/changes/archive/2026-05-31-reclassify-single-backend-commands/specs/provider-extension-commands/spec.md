## MODIFIED Requirements

### Requirement: 系统必须支持 provider-specific 扩展命令
系统 MUST 允许 backend provider 注册共享命令之外的扩展命令，并把这些命令挂载到稳定的业务语义命令树中，而 SHALL NOT 以 provider 名称作为顶层命令组直接暴露给用户；凡是仅支持单一 backend 的命令，系统 MUST 以 provider-extension 方式建模。

#### Scenario: provider 扩展命令显示在业务语义命令树中
- **WHEN** 某 provider 注册扩展命令
- **THEN** 系统 SHALL 在帮助页和命令树中按该命令声明的业务语义 CLI 路径展示该命令，而 SHALL NOT 强制创建同名 provider 根组

#### Scenario: 扩展命令不伪装为共享命令
- **WHEN** 某扩展能力只由单个 provider 提供
- **THEN** 系统 SHALL 继续以 provider-specific 方式暴露该命令，并保留其 provider 归属与支持矩阵，而 SHALL NOT 把它注册为共享命令

#### Scenario: 单 backend 命令必须进入 provider-extension
- **WHEN** 某业务命令当前只支持一个 backend
- **THEN** 系统 MUST 把它注册到对应 provider 的 extension_commands，而 SHALL NOT 继续留在 shared command 集合中

### Requirement: 扩展命令必须显式声明可见性与约束
系统 MUST 为扩展命令声明所属 provider、可见性范围和运行时约束，并在用户选择错误 backend 时返回带指导信息的明确错误。

#### Scenario: 非目标 provider 下不可调用扩展命令
- **WHEN** 用户试图在错误 provider 上执行某 provider 的扩展命令
- **THEN** 系统 MUST 返回明确错误，说明该命令仅属于指定 provider，并提示该命令默认会路由到哪个 backend

#### Scenario: 单 backend 扩展命令允许省略 backend
- **WHEN** 某 provider-specific 扩展命令的支持矩阵仅包含一个 backend，且用户未显式传入 `--backend`
- **THEN** 系统 MUST 默认解析到该命令所属 provider，而 SHALL NOT 要求用户重复传入相同 backend
