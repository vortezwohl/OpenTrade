## ADDED Requirements

### Requirement: 系统必须为 Yahoo 专属能力提供 provider-extension 命令组
系统 MUST 允许 `yfinance` 把不适合进入共享命令面的 Yahoo 专属能力作为 provider-extension 命令暴露。

#### Scenario: 期权链或新闻以扩展命令暴露
- **WHEN** `yfinance` 需要暴露 `option_chain`、`news` 或同类 Yahoo 专属能力
- **THEN** 系统 MUST 通过 provider-extension 命令注册它们，而 SHALL NOT 强行塞进共享命令树

#### Scenario: 扩展命令具备 provider 归属
- **WHEN** 用户查看 `yfinance` 扩展命令定义
- **THEN** 该命令 MUST 标记 `provider_name = BackendName.YFINANCE`

#### Scenario: 单 backend 命令不得误入 shared catalog
- **WHEN** 某个新增 Yahoo 命令当前仅支持 `yfinance`
- **THEN** 系统 MUST 将它定义为 provider-extension，而 SHALL NOT 把它注册进 shared catalog 作为单 backend shared 命令

### Requirement: 扩展命令必须复用统一执行骨架
`yfinance` provider-extension 命令 MUST 继续经过统一请求校验、backend 解析、handler 调用、标准化输出与渲染链路。

#### Scenario: 扩展命令走统一执行主链
- **WHEN** 用户执行一个 `yfinance` provider-extension 命令
- **THEN** 系统 MUST 复用 `CommandExecutor -> CommandFacade -> BackendProvider -> CapabilityHandler` 执行路径

#### Scenario: 错误 backend 下拒绝执行扩展命令
- **WHEN** 用户对 `yfinance` provider-extension 命令显式传入其他 backend
- **THEN** 系统 MUST 返回该扩展命令仅支持 `yfinance` 的明确错误
