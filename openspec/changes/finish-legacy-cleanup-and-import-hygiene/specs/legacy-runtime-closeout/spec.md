## ADDED Requirements

### Requirement: 运行时主链必须彻底脱离旧函数驱动命令分类

系统 MUST 让 `commands`、`executor`、`enrichment` 和 `observation` 的主链逻辑围绕 shared / provider-extension 命令、capability 和结果契约工作，而 SHALL NOT 再以旧 `(module_name, function_name)` 分类作为主要分流依据。

#### Scenario: shared 命令进入 observation / enrichment 时不再依赖旧模块名分类

- **WHEN** shared 命令执行后进入 observation 或 enrichment
- **THEN** 系统 MUST 根据 command key、capability、contract 或标准补充接口完成分流
- **AND** SHALL NOT 因为旧 `module_name` / `function_name` 元组匹配而决定主路径行为

#### Scenario: provider-extension 命令不借道 legacy efinance 命令语义

- **WHEN** provider-extension 命令进入统一执行骨架
- **THEN** 系统 MUST 依据扩展命令定义和对应 provider handler 运行
- **AND** SHALL NOT 通过模拟 legacy `efinance.xxx.yyy` 语义完成内部路由

### Requirement: 标准补充接口必须是唯一允许的二次取数入口

系统 MUST 通过标准补充接口执行历史回补或其他二次取数逻辑，而 SHALL NOT 保留仅以旧模块名/函数名为输入并直接调用特定 provider 旧 API 的内部入口。

#### Scenario: enrichment 回补历史数据时使用标准补充接口

- **WHEN** enrichment 需要为 shared capability 回补历史数据
- **THEN** 系统 MUST 使用标准请求对象或 capability 上下文调用标准补充接口
- **AND** SHALL NOT 直接以 legacy `module_name` 分支选择 provider 旧函数

#### Scenario: 删除仅为旧模型服务的内部回补分支

- **WHEN** 某个内部辅助函数只服务于已废弃的 legacy 命令模型
- **THEN** 系统 MUST 删除该函数或将其调用方收口到标准补充接口后再移除

### Requirement: 测试与文档不得再把 legacy 命令模型视为当前事实

系统 MUST 让测试和文档以当前 shared / provider-extension 多后端模型为准，而 SHALL NOT 继续断言 legacy registry、legacy 命令分类或旧兼容回调仍然是运行时事实。

#### Scenario: CLI 回归测试不再依赖 legacy registry

- **WHEN** 系统执行 CLI 回归测试
- **THEN** 测试 MUST 以 shared command catalog、provider extension catalog 和统一执行骨架作为断言基准
- **AND** SHALL NOT 以 legacy registry 存在与否作为成功条件

#### Scenario: 架构文档只把 legacy 作为迁移背景

- **WHEN** 文档提及 legacy 命令驱动模型
- **THEN** 文档 MUST 将其标记为历史背景、迁移来源或已移除路径
- **AND** SHALL NOT 将其描述为当前推荐或仍然有效的主路径
