## ADDED Requirements

### Requirement: 系统必须通过统一执行骨架处理共享命令与扩展命令
系统 MUST 使用统一执行骨架处理命令调用，包括请求校验、backend 解析、能力调用、标准化、增强、观察、渲染和输出。

#### Scenario: 共享命令执行遵循固定步骤
- **WHEN** 用户执行任一共享命令
- **THEN** 系统 MUST 依次执行请求校验、backend 解析、能力检查、handler 调用、结果标准化、增强、观察、渲染与输出

#### Scenario: 扩展命令执行遵循同一骨架
- **WHEN** 用户执行 provider 扩展命令
- **THEN** 系统 MUST 复用同一执行骨架，只在命令目录与 handler 绑定上与共享命令不同

### Requirement: watch 模式必须复用同一命令请求与 backend 解析结果
系统 MUST 让 watch 模式重复执行同一标准请求与能力解析路径，而 SHALL NOT 为 watch 单独实现旁路逻辑。

#### Scenario: watch 模式重复同一能力调用
- **WHEN** 用户对支持 watch 的命令启用 watch
- **THEN** 系统 MUST 在每次刷新时复用相同的命令请求结构与 backend 选择逻辑

#### Scenario: 不支持 watch 的命令在刷新前被拒绝
- **WHEN** 用户对不支持 watch 的命令启用 watch
- **THEN** 系统 MUST 在进入循环前返回明确错误

### Requirement: enrichment 与 observation 必须依赖标准契约或补充接口
系统 MUST 让 enrichment 与 observation 通过标准结果契约或专用补充接口工作，而 SHALL NOT 直接绑定某 provider 的历史函数或原始字段模型。

#### Scenario: enrichment 通过补充接口请求历史数据
- **WHEN** enrichment 需要回补历史数据
- **THEN** 系统 MUST 通过标准补充接口获取标准历史结果，而 SHALL NOT 直接调用特定 provider 的历史函数

#### Scenario: observation 处理多 backend 结果时保持统一结构
- **WHEN** 不同 backend 返回同一 capability 的标准结果
- **THEN** observation MUST 生成同结构的 observation payload，而 SHALL NOT 因 backend 不同切换到不同 payload 结构
