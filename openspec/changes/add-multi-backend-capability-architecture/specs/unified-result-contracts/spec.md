## ADDED Requirements

### Requirement: 系统必须按 capability 定义标准结果契约
系统 MUST 为每类共享 capability 定义独立标准结果契约，而 SHALL NOT 使用单一全局万能结构表达所有结果。

#### Scenario: 历史行情能力返回标准历史契约
- **WHEN** 任一 backend 成功执行历史行情 capability
- **THEN** 系统 MUST 返回满足历史行情契约的标准结果对象

#### Scenario: 资料类能力返回标准资料契约
- **WHEN** 任一 backend 成功执行资料类 capability
- **THEN** 系统 MUST 返回满足资料契约的标准结果对象

### Requirement: 标准结果契约必须区分核心字段、可选字段和原始字段
每个标准结果契约 MUST 明确区分共享核心字段、可选字段、provider 原始字段和 provider 扩展字段。

#### Scenario: observation 只依赖核心字段
- **WHEN** observation 处理标准结果契约
- **THEN** observation MUST 只依赖该契约声明的核心字段集合，而 SHALL NOT 直接依赖 provider 原始字段名

#### Scenario: 原始字段可以在 raw 视图中保留
- **WHEN** 用户请求 raw 视图或调试输出
- **THEN** 系统 SHALL 能保留 provider 原始字段或扩展字段，而 SHALL NOT 因标准化而无条件丢弃

### Requirement: 标准化失败必须显式暴露
系统 MUST 对标准化失败或关键字段缺失进行显式报告，而 SHALL NOT 静默生成语义错误的契约结果。

#### Scenario: 缺少关键字段时拒绝生成共享契约
- **WHEN** provider 返回值缺失某 capability 契约要求的关键字段
- **THEN** 系统 MUST 返回明确标准化错误或能力不满足错误

#### Scenario: 可选字段缺失不阻断共享能力
- **WHEN** provider 只缺失某 capability 契约的可选字段
- **THEN** 系统 SHALL 仍然生成有效标准结果，并标记缺失字段为空或未提供
