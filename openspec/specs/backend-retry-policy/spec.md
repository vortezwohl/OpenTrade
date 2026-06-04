# backend-retry-policy Specification

## Purpose
TBD - created by archiving change generalize-backend-retry-policy. Update Purpose after archive.
## Requirements
### Requirement: 系统必须为全部 backend 提供可扩展的网络重试策略
系统 MUST 提供 backend-agnostic 的网络重试策略扩展点，而 SHALL NOT 继续只让 `efinance` 以局部 handler 包装方式独占该能力。

#### Scenario: 非 efinance backend 可声明网络重试策略
- **WHEN** 系统加载 `akshare`、`yfinance` 或后续新增 backend provider
- **THEN** provider MUST 能声明自己的可重试网络异常集合并接入统一重试能力

#### Scenario: efinance 不再独占重试挂载点
- **WHEN** 系统执行任一需要网络访问的 concrete backend 命令
- **THEN** 是否进入网络重试 MUST 由统一 provider 策略决定，而 SHALL NOT 依赖 `efinance` handler 内部手工包装

### Requirement: 限流错误必须纳入网络重试范围
系统 MUST 把 provider 识别出的限流错误视为可重试的网络失败类型之一，而 SHALL NOT 默认把限流直接视为最终失败。

#### Scenario: yfinance 限流触发重试
- **WHEN** `yfinance` 在原子网络调用中抛出其限流异常
- **THEN** provider 级网络重试 MUST 先按既定策略重试该调用

#### Scenario: 限流重试耗尽后保留 provider 语义
- **WHEN** 某 backend 的限流错误在达到重试上限后仍未恢复
- **THEN** 系统 MUST 以保留 provider 语义的最终异常结束，而 SHALL NOT 把它静默改写成无上下文的通用错误

### Requirement: side-effect 命令默认不得自动重试
系统 MUST 对具有副作用的命令默认关闭自动网络重试，除非未来有显式幂等性规则授权，否则 SHALL NOT 因统一重试引入重复副作用执行。

#### Scenario: 下载类命令跳过自动重试
- **WHEN** 用户执行 `fund.reports.download` 这类 side-effect 命令
- **THEN** 系统 MUST 直接执行 provider handler，而 SHALL NOT 自动重放该命令

### Requirement: 直接透传异常不得被误判为可重试
系统 MUST 允许 provider 声明直接透传异常集合，用于表达参数错误、能力限制或 guardrail 错误；这些异常 SHALL NOT 进入网络重试。

#### Scenario: 参数错误直接失败
- **WHEN** provider handler 抛出 `ValueError` 或等价的参数语义错误
- **THEN** 系统 MUST 直接把该错误返回上层，而 SHALL NOT 对其执行网络重试

#### Scenario: provider guardrail 错误直接失败
- **WHEN** provider 抛出其显式 guardrail 异常，例如无效 period、市场不支持或类似运行时约束错误
- **THEN** 系统 MUST 直接结束当前 backend 执行，而 SHALL NOT 把该异常归入瞬时网络失败

