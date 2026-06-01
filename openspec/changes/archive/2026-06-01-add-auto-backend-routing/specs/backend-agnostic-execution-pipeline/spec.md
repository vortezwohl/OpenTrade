## MODIFIED Requirements

### Requirement: 系统必须通过统一执行骨架处理共享命令与扩展命令
系统 MUST 使用统一执行骨架处理命令调用，包括请求校验、backend 解析、能力调用、标准化、增强、观察、渲染和输出；当 backend 解析结果为 `auto` 时，统一执行骨架 MUST 支持在单次命令执行中按候选链尝试多个 concrete backend。

#### Scenario: auto 共享命令执行遵循固定步骤
- **WHEN** 用户执行以 `auto` 解析的共享命令
- **THEN** 系统 MUST 依次执行请求校验、候选 backend 解析、按顺序尝试 capability handler、结果标准化、增强、观察、渲染与输出

#### Scenario: provider-extension 在 auto 下仍复用同一骨架
- **WHEN** 用户以 `auto` 语义执行 provider-extension 命令
- **THEN** 系统 MUST 复用同一执行骨架，只是 backend 解析阶段直接适配到所属 provider，而不是进入完整降级链

#### Scenario: 最终命中 backend 传播到增强链
- **WHEN** auto 请求成功命中某个 concrete backend
- **THEN** 系统 MUST 让后续 enrichment、observation 与历史回补继续使用该最终命中 backend

### Requirement: watch 模式必须复用同一命令请求与 backend 解析结果
系统 MUST 让 watch 模式重复执行同一标准请求与 backend 选择逻辑；当 backend 语义为 `auto` 时，每轮刷新 MUST 重新按相同 auto 规则解析和尝试 backend。

#### Scenario: watch auto 模式按同一降级链重试
- **WHEN** 用户对 `--backend auto` 的命令启用 watch
- **THEN** 系统 MUST 在每次刷新时重新按相同的 auto 候选链顺序尝试 backend

#### Scenario: 不支持 watch 的命令在刷新前被拒绝
- **WHEN** 用户对不支持 watch 的命令启用 watch
- **THEN** 系统 MUST 在进入循环前返回明确错误
