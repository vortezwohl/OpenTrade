## ADDED Requirements

### Requirement: 系统必须支持 provider-specific 扩展命令
系统 MUST 允许 backend provider 注册共享命令之外的扩展命令，并把这些命令与共享命令区别展示。

#### Scenario: provider 扩展命令显示在独立命令组
- **WHEN** 某 provider 注册扩展命令
- **THEN** 系统 SHALL 在帮助页和命令树中把这些命令呈现为该 provider 的扩展命令组

#### Scenario: 扩展命令不伪装为共享命令
- **WHEN** 某扩展能力只由单个 provider 提供
- **THEN** 系统 SHALL 以 provider-specific 方式暴露该命令，而 SHALL NOT 把它注册为共享命令

### Requirement: 扩展命令必须复用统一执行骨架
provider-specific 扩展命令 MUST 复用统一请求解析、执行、渲染与输出骨架，而 SHALL NOT 绕过共享执行管线。

#### Scenario: 扩展命令仍走统一执行链
- **WHEN** 用户执行某 provider 扩展命令
- **THEN** 系统 MUST 仍执行请求校验、backend 解析、handler 调用、结果渲染与输出

#### Scenario: 扩展命令可以声明专属请求 schema
- **WHEN** provider 为扩展命令定义专属参数
- **THEN** 系统 SHALL 允许该扩展命令绑定独立请求 schema 和帮助文本

### Requirement: 扩展命令必须显式声明可见性与约束
系统 MUST 为扩展命令声明所属 provider、可见性范围和运行时约束。

#### Scenario: 非目标 provider 下不可调用扩展命令
- **WHEN** 用户试图在错误 provider 上执行某 provider 的扩展命令
- **THEN** 系统 MUST 返回明确错误，说明该命令仅属于指定 provider
