## ADDED Requirements

### Requirement: BackendProvider 必须暴露统一执行入口
系统 MUST 为 `BackendProvider` 提供稳定的统一执行入口，用于协调 capability handler 调用与 provider 级横切逻辑；`CommandFacade` SHALL NOT 继续直接调用 `handler.execute` 作为唯一执行路径。

#### Scenario: single backend 通过 provider 统一入口执行
- **WHEN** `CommandFacade` 处理一个非 `auto` 的 concrete backend 命令
- **THEN** 它 MUST 通过该 backend provider 的统一执行入口完成 handler 调用

#### Scenario: auto backend 的每个候选都通过 provider 统一入口执行
- **WHEN** `CommandFacade` 以 `auto` 模式尝试 candidate backend 链
- **THEN** 每个 candidate backend 的能力调用 MUST 经过各自 provider 的统一执行入口

### Requirement: provider 统一执行入口必须承载网络重试策略
`BackendProvider` 的统一执行入口 MUST 在 handler 调用前应用 provider 级网络重试判定，并在允许时以统一 retry 工具包装原子网络调用。

#### Scenario: 普通网络命令进入 provider 级重试
- **WHEN** provider 执行一个非 side-effect 且异常类型命中可重试集合的能力调用
- **THEN** 统一执行入口 MUST 使用统一 retry 工具包装该调用

#### Scenario: side-effect 命令绕过 provider 级重试
- **WHEN** provider 执行一个被命令定义标记为 `has_side_effect=True` 的能力调用
- **THEN** 统一执行入口 MUST 跳过自动网络重试并直接执行 handler

### Requirement: auto 模式必须先完成单 backend 内部重试，再决定是否 failover
系统 MUST 把 provider 内部网络重试视为当前 candidate backend 的一部分恢复过程；`CommandFacade` SHALL NOT 在当前 backend 尚未完成其内部重试前提前切换到下一个 candidate。

#### Scenario: 当前 backend 内部重试成功时不进入下一个候选
- **WHEN** `auto` 模式下当前 candidate backend 经 provider 内部重试后成功返回
- **THEN** 系统 MUST 立即返回该结果，而 SHALL NOT 再尝试后续 backend

#### Scenario: 当前 backend 内部重试失败后再进入 failover 判定
- **WHEN** `auto` 模式下当前 candidate backend 在完成 provider 内部重试后仍抛出异常
- **THEN** `CommandFacade` MUST 仅在该异常满足 failover eligibility 规则时才尝试下一个 candidate backend

### Requirement: 最终命中 backend 必须继续回写到运行时上下文
系统 MUST 在 provider 统一执行入口引入后继续保留 `final_backend` 回写语义，确保后续 enrichment、observation 和 watch 路径使用真实命中 backend，而不是丢失最终 concrete backend 信息。

#### Scenario: single backend 成功后记录 final_backend
- **WHEN** 某个 concrete backend 通过 provider 统一执行入口成功返回
- **THEN** 运行时上下文 MUST 记录该 concrete backend 为 `final_backend`

#### Scenario: auto 模式在重试与 failover 后记录真实命中 backend
- **WHEN** `auto` 模式最终在某个 candidate backend 成功返回
- **THEN** 运行时上下文 MUST 把该 candidate backend 记录为 `final_backend`
