## ADDED Requirements

### Requirement: 系统必须显式处理 Yahoo 限流错误
系统 MUST 把 `yfinance` 抛出的 Yahoo 限流错误视作显式运行时约束，而 SHALL NOT 将其吞并成模糊网络错误或静默空结果。

#### Scenario: 历史请求触发限流
- **WHEN** `yfinance` 在历史、搜索、资料面或基金资料请求中抛出 `YFRateLimitError`
- **THEN** 系统 MUST 返回可读的限流错误信息，并指明错误来自 Yahoo 限流

#### Scenario: 限流错误不伪装成空数据
- **WHEN** Yahoo 返回限流导致 `yfinance` 无法获取结果
- **THEN** 系统 SHALL NOT 伪造空 DataFrame、空列表或成功状态来掩盖失败

### Requirement: 系统必须对字段缺失与资料面不完整做受控降级
系统 MUST 在 `yfinance` 字段缺失或资料面不完整时，优先保证标准契约的核心字段与原始扩展字段可见，而不是伪造完整 payload。

#### Scenario: profile 缺少部分可选字段
- **WHEN** `yfinance` 资料面缺少某些共享可选字段
- **THEN** 系统 MUST 继续返回满足核心契约的结果，并把可用 Yahoo 原始字段保存在 `provider_fields` 或等价扩展区域

#### Scenario: observation 遇到不完整结果
- **WHEN** `yfinance` 的标准结果缺失 observation 所需的非核心字段
- **THEN** 系统 MUST 降级到可接受的 observation / generic rendering 路径，而 SHALL NOT 触发跨 backend 偷偷回补

### Requirement: 系统必须限制 yfinance 的市场与数据语义承诺
系统 MUST 把 `yfinance` 定义为偏全球 Yahoo ticker 语义的数据后端，并显式限制其对本地市场专属能力的承诺。

#### Scenario: symbol 语义差异被显式说明
- **WHEN** 用户使用现有共享命令切换到 `--backend yfinance`
- **THEN** 系统 SHALL 能通过帮助文本、错误信息或文档说明该 backend 以 Yahoo ticker / symbol 语义为主

#### Scenario: 不支持的市场能力不进入假成功路径
- **WHEN** 用户请求超出 `yfinance` 市场覆盖能力的共享命令
- **THEN** 系统 MUST 返回显式不支持错误，而 SHALL NOT 自动切换到其他 provider
