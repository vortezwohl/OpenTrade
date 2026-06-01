## ADDED Requirements

### Requirement: CommandFacade.invoke 单后端成功路径
	ests/test_facade_unit.py SHALL 验证 CommandFacade.invoke 在指定单一后端且该后端成功返回时的行为。

#### Scenario: 显式后端成功
- **WHEN** 调用 CommandFacade().invoke(definition, backend_selection_efinance, kwargs) 且 efinance handler 成功返回
- **THEN** 返回 StandardResult 且数据正确

### Requirement: CommandFacade.invoke 后端失败时传播异常
	ests/test_facade_unit.py SHALL 验证 CommandFacade.invoke 在指定后端抛出异常时的行为。

#### Scenario: 指定后端执行失败
- **WHEN** 调用 CommandFacade().invoke(definition, backend_selection_yfinance, kwargs) 且 yfinance handler 抛出 RuntimeError
- **THEN** 异常被传播，不被静默吞没

### Requirement: CommandFacade.invoke auto 模式逐后端 failover
	ests/test_facade_unit.py SHALL 验证 CommandFacade.invoke 在 auto 模式下逐候选后端尝试直至成功的逻辑。

#### Scenario: 第一候选成功
- **WHEN** auto 模式且 candidate_chain 为 (akshare, yfinance, efinance)，akshare 成功返回
- **THEN** 仅调用 akshare，不尝试后续后端
- **AND** 返回的 BackendSelection.final_backend 为 akshare

#### Scenario: 第一候选失败第二候选成功
- **WHEN** auto 模式且 akshare 抛出异常，yfinance 成功返回
- **THEN** 最终使用 yfinance 的结果
- **AND** final_backend 为 yfinance

#### Scenario: 全部候选失败
- **WHEN** auto 模式且所有候选后端均抛出异常
- **THEN** 抛出 AutoBackendExecutionError
- **AND** 异常消息包含所有后端的失败信息

### Requirement: CommandFacade.invoke side-effect 命令处理
	ests/test_facade_unit.py SHALL 验证对有副作用的命令（如 und.reports.download）不进行网络重试的行为差异。

#### Scenario: 副作用命令不走网络重试
- **WHEN** 调用 CommandFacade().invoke 处理 und.reports.download 命令
- **THEN** handler 的 execute 被直接调用（不经过 call_with_network_retry 包装）
