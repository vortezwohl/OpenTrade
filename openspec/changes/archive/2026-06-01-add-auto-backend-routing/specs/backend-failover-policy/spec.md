## ADDED Requirements

### Requirement: 系统必须对 auto backend 使用受控 failover 规则
系统 MUST 在 `auto` 模式下对失败原因进行分类，并只对允许降级的失败继续尝试下一个 backend。

#### Scenario: provider 故障允许进入下一个 backend
- **WHEN** 当前 backend 因网络异常、限流、provider 不可用或 provider 能力缺失而失败
- **THEN** 系统 MUST 继续尝试 auto 候选链中的下一个 backend

#### Scenario: 用户输入错误立即停止
- **WHEN** 当前命令因请求 schema 校验失败、缺少必填参数或明显非法输入而失败
- **THEN** 系统 MUST 立即终止执行，而 SHALL NOT 继续尝试下一个 backend

### Requirement: 系统必须在 auto 全链路失败时聚合错误信息
系统 MUST 在 auto 候选链全部失败时返回聚合后的错误信息，而不是只暴露最后一个 backend 的失败结果。

#### Scenario: 多 backend 全部失败
- **WHEN** auto 候选链中的所有 backend 都执行失败
- **THEN** 系统 MUST 返回包含每个 backend 失败原因的聚合错误

#### Scenario: 聚合错误保留尝试顺序
- **WHEN** auto 全链路失败并生成错误输出
- **THEN** 错误信息 MUST 能反映 backend 的实际尝试顺序
