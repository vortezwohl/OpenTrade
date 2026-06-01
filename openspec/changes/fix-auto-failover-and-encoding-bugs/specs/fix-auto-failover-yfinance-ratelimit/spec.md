## ADDED Requirements

### Requirement: YFRateLimitError 不阻断 auto 候选链
efinance_cli/facade.py 的 is_failover_eligible_error 函数 SHALL 采用黑名单策略：仅将 click.ClickException、ValueError、TypeError 判定为不可恢复错误，其余所有异常（包括 YFRateLimitError）均视为可恢复，允许 auto 模式继续尝试下一个候选后端。

#### Scenario: yfinance 限流后 failover 到 efinance
- **WHEN** auto 模式候选链为 (akshare, yfinance, efinance)
- **AND** akshare 和 yfinance 均执行失败（包括 YFRateLimitError）
- **THEN** 系统继续尝试 efinance 后端
- **AND** 若 efinance 成功则返回其结果，final_backend 为 efinance

#### Scenario: ClickException 不触发 failover
- **WHEN** auto 模式中某个后端抛出 click.ClickException（参数错误）
- **THEN** 该异常直接传播，不尝试后续候选后端

#### Scenario: ValueError 不触发 failover
- **WHEN** auto 模式中某个后端抛出 ValueError
- **THEN** 该异常直接传播，不尝试后续候选后端
