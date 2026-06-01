## ADDED Requirements

### Requirement: raw 视图跳过指标增强与 observation
efinance_cli/executor.py 的 invoke 方法 SHALL 在请求的 iew_mode 为 aw 时，跳过 enrich_market_data 和 uild_observation_output 两个步骤，直接将 _materialize_standard_result 返回的原始字典传递给渲染层。

#### Scenario: --view raw 不触发增强层
- **WHEN** 用户执行 stock price history --symbols 000001 --view raw
- **THEN** invoke 方法不调用 enrich_market_data
- **AND** 不调用 uild_observation_output
- **AND** 直接返回包含 contract_name、data、raw_payload、provider_fields、metadata 的字典

#### Scenario: --view observation 仍走增强层
- **WHEN** 用户执行 stock price history --symbols 000001 --view observation
- **THEN** invoke 方法正常调用 enrich_market_data 和 uild_observation_output
- **AND** 行为与修复前完全一致

#### Scenario: raw 视图不崩溃
- **WHEN** 使用 --view raw 执行任意共享命令
- **THEN** 不会出现 AttributeError: 'str' object has no attribute 'columns' 或类似异常
- **AND** 命令正常退出（exit_code=0）
