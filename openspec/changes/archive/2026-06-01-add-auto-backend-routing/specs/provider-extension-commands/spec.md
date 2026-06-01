## MODIFIED Requirements

### Requirement: 系统必须支持 provider-specific 扩展命令
系统 MUST 允许 backend provider 注册共享命令之外的扩展命令，并把这些命令挂载到稳定的业务语义命令树中，而 SHALL NOT 以 provider 名称作为顶层命令组直接暴露给用户；在存在 `auto` backend 语义时，provider-extension 命令 MUST 支持自动适配到所属 provider。

#### Scenario: provider 扩展命令显示在业务语义命令树中
- **WHEN** 某 provider 注册扩展命令
- **THEN** 系统 SHALL 在帮助页和命令树中按该命令声明的业务语义 CLI 路径展示该命令，而 SHALL NOT 强制创建同名 provider 根组

#### Scenario: auto 对扩展命令执行自动适配
- **WHEN** 用户对 provider-extension 命令未显式传入 backend，或显式传入 `--backend auto`
- **THEN** 系统 MUST 自动适配到该命令所属 provider，而 SHALL NOT 让该命令参与无意义的多 provider 降级链

#### Scenario: 非目标 concrete backend 下不可调用扩展命令
- **WHEN** 用户对 provider-extension 命令显式传入错误 concrete backend
- **THEN** 系统 MUST 返回明确错误，说明该命令仅属于指定 provider
