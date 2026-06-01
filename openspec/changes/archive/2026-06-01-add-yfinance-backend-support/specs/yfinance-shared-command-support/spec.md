## ADDED Requirements

### Requirement: 系统必须为 yfinance 提供最小共享命令闭环
系统 MUST 为 `yfinance` 提供一组最小但真实可用的共享命令支持，至少覆盖搜索、历史、最新价 / 快照、股票资料、基金净值历史、基金资料与通用 quote 入口。

#### Scenario: 搜索命令支持 yfinance
- **WHEN** 用户执行 `instrument.search` 并选择 `--backend yfinance`
- **THEN** 系统 MUST 调用 Yahoo 搜索链路并返回满足 `search-results` 契约的结果

#### Scenario: 股票历史命令支持 yfinance
- **WHEN** 用户执行 `stock.price.history` 并选择 `--backend yfinance`
- **THEN** 系统 MUST 返回满足 `history-bars` 契约的标准结果

#### Scenario: 基金资料命令支持 yfinance
- **WHEN** 用户执行 `fund.profile` 并选择 `--backend yfinance`
- **THEN** 系统 MUST 返回包含共享核心字段且保留基金扩展资料的标准结果

### Requirement: 系统必须把 yfinance 参数语义归一化到共享 schema
系统 MUST 在不改变共享命令 schema 的前提下，把共享请求参数转换为 `yfinance` 可执行的 symbol、period、interval 或资料面请求语义。

#### Scenario: 历史请求参数映射到 Yahoo 语义
- **WHEN** 用户使用共享历史命令传入标准起止日期、周期或复权相关参数
- **THEN** 系统 MUST 进行显式参数转换或拒绝不支持的语义，而 SHALL NOT 直接把原始参数无校验透传给 `yfinance`

#### Scenario: quote 命令映射到 Yahoo ticker
- **WHEN** 用户使用 `quote.price.history`、`quote.price.latest` 或 `quote.profile` 并选择 `yfinance`
- **THEN** 系统 MUST 以 Yahoo ticker / quote identity 为核心执行请求，并返回标准契约字段

### Requirement: 系统必须显式声明 yfinance 的共享命令不支持范围
系统 MUST 对 `yfinance` 当前不具备稳定数据来源或无法映射到共享契约的命令保持显式不支持状态。

#### Scenario: 中国市场专属命令保持不支持
- **WHEN** 用户对 `bond.*`、`futures.*`、`flow`、`trades` 或类似本地市场专属命令选择 `--backend yfinance`
- **THEN** 系统 MUST 在调用前返回 backend 不支持错误

#### Scenario: 不完整共享支持矩阵可被测试
- **WHEN** 测试检查共享命令定义与 provider 注册的一致性
- **THEN** `yfinance` 的 `supports()` 结果 MUST 与命令支持矩阵声明一致
