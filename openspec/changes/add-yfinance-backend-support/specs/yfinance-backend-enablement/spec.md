## ADDED Requirements

### Requirement: 系统必须把 yfinance 注册为正式 backend provider
系统 MUST 把 `yfinance` 从 optional provider 升级为正式 `BackendProvider`，并允许运行时通过 `--backend yfinance` 解析到该 provider。

#### Scenario: backend 注册表暴露 yfinance
- **WHEN** 系统加载 backend provider 注册表
- **THEN** 注册表 MUST 包含 `BackendName.YFINANCE`

#### Scenario: 共享命令显式选择 yfinance
- **WHEN** 用户对支持矩阵包含 `yfinance` 的共享命令传入 `--backend yfinance`
- **THEN** 系统 MUST 解析到 `yfinance` provider 并进入对应 capability handler

### Requirement: 系统必须在 provider 缺失或依赖不可用时显式失败
系统 MUST 在 `yfinance` 依赖缺失、导入失败或 provider 未完成注册时返回可读错误，而 SHALL NOT 静默回退到其他 backend。

#### Scenario: yfinance 依赖不可导入
- **WHEN** 运行时请求 `--backend yfinance` 但 Python 环境中无法导入 `yfinance`
- **THEN** 系统 MUST 返回 `yfinance backend is unavailable` 类似的显式错误

#### Scenario: 不支持能力时禁止回退
- **WHEN** 用户对某共享命令选择 `--backend yfinance`，但该命令尚未被 `yfinance` 支持
- **THEN** 系统 MUST 在执行前返回 backend 不支持错误

### Requirement: 系统必须为 yfinance 暴露运行时防护元信息
系统 MUST 为 `yfinance` provider 标注其运行时约束，包括 Yahoo 限流风险、全球 ticker 语义以及与现有国内市场命令面的差异。

#### Scenario: 帮助或错误信息暴露运行时约束
- **WHEN** 用户查看 `yfinance` 相关命令帮助或触发运行时错误
- **THEN** 系统 SHALL 能提示 Yahoo 限流或 symbol 语义差异这类关键约束
