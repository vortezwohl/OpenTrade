## ADDED Requirements

### Requirement: 系统必须以命令目录而不是上游函数注册共享命令
系统 MUST 通过显式命令目录定义共享命令，而 SHALL NOT 依赖第三方函数名、模块名或函数签名作为共享命令的稳定来源。

#### Scenario: 共享命令由稳定命令键驱动
- **WHEN** 系统启动并构建共享命令树
- **THEN** 每个共享命令 MUST 具有稳定命令键、CLI 路径、能力标识和请求 schema

#### Scenario: 第三方函数签名变化不直接改变 CLI 参数
- **WHEN** 某个 provider 的上游函数签名发生变化
- **THEN** 共享命令的 CLI 参数集合 MUST 继续由命令目录中的请求 schema 决定

### Requirement: 共享命令必须显式声明能力标识与支持矩阵
每个共享命令 MUST 显式绑定一个 capability 标识，并声明可被哪些 backend 支持或不支持。

#### Scenario: 帮助页展示共享命令的支持矩阵
- **WHEN** 用户查看共享命令帮助页
- **THEN** 系统 SHALL 展示该命令绑定的 capability 标识以及支持的 backend 列表

#### Scenario: backend 不支持时拒绝执行共享命令
- **WHEN** 用户对某共享命令选择了不支持该 capability 的 backend
- **THEN** 系统 MUST 在执行前返回明确错误，而 SHALL NOT 伪造成功结果

### Requirement: 共享命令请求 schema 必须独立定义参数语义
系统 MUST 为共享命令定义独立请求 schema，用于描述参数名、类型、默认值、取值域、是否必填和帮助信息。

#### Scenario: 请求 schema 驱动参数解析
- **WHEN** 用户调用共享命令并传入参数
- **THEN** 系统 MUST 根据该命令的请求 schema 执行解析、校验和标准请求构建

#### Scenario: schema 校验失败时阻止下游调用
- **WHEN** 用户输入不满足请求 schema 的参数
- **THEN** 系统 MUST 在能力调用前返回可读校验错误
