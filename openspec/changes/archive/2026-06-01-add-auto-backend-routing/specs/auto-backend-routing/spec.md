## ADDED Requirements

### Requirement: 系统必须支持 auto 作为默认 backend 路由策略
系统 MUST 支持 `auto` 作为运行时 backend 选择语义；对未显式指定 `--backend` 的共享命令，系统 MUST 默认按 `auto` 语义解析，而不是固定解析到某个单一 provider。

#### Scenario: 未显式指定 backend 时走 auto
- **WHEN** 用户执行共享命令且未传入 `--backend`
- **THEN** 系统 MUST 把该请求按 `auto` backend 语义解析

#### Scenario: auto 候选链按固定顺序构造
- **WHEN** 系统为共享命令构造 `auto` backend 候选链
- **THEN** 系统 MUST 以 `akshare -> yfinance -> efinance` 作为降级顺序

### Requirement: 系统必须过滤 auto 候选链中的无效 backend
系统 MUST 在执行 `auto` 候选链前，过滤掉当前命令不支持或当前运行时不可用的 backend。

#### Scenario: 命令支持矩阵过滤候选 backend
- **WHEN** 某共享命令只支持候选链中的部分 backend
- **THEN** 系统 MUST 仅尝试该命令支持矩阵允许的 backend

#### Scenario: 未注册 provider 不进入 auto 尝试
- **WHEN** auto 候选链中包含尚未正式接入的 provider
- **THEN** 系统 SHALL 跳过该 provider，而 SHALL NOT 因它不存在而让整条 auto 链直接失败

### Requirement: 系统必须记录 auto 的最终命中 backend
系统 MUST 在 auto 请求成功后记录最终成功命中的 concrete backend，并把该信息传播到后续执行链。

#### Scenario: auto 命中具体 provider
- **WHEN** auto 候选链中的某个 backend 成功返回结果
- **THEN** 系统 MUST 记录该 backend 为最终命中 backend

#### Scenario: 后续链路可读取最终命中 backend
- **WHEN** 命令主调用已经通过 auto 成功命中某个 concrete backend
- **THEN** enrichment、observation、watch 与输出元信息 MUST 能读取该最终命中 backend
