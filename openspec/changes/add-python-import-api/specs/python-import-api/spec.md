## ADDED Requirements

### Requirement: 顶层包 SHALL 提供唯一稳定的对象式 import 入口
`opentrade` 包 MUST 提供 `OpenTrade` 作为面向其他 Python 程序的稳定顶层入口。顶层包 SHALL 不要求调用方直接 import 内部执行模块、CLI 组装模块或 provider 实现模块才能使用主要市场数据能力。

#### Scenario: 顶层导入程序化入口
- **WHEN** 调用方执行 `from opentrade import OpenTrade`
- **THEN** 导入 SHALL 成功
- **AND** `OpenTrade` SHALL 作为公开 API 被显式导出

#### Scenario: 顶层不暴露函数式程序入口
- **WHEN** 维护者检查 `opentrade` 顶层公共导出
- **THEN** 顶层 SHALL 以 `OpenTrade` 作为主要程序化入口
- **AND** 程序化 API SHALL 不要求同时维护平铺的函数式入口集合

### Requirement: OpenTrade SHALL 通过命名空间对象暴露 CLI 等价能力域
`OpenTrade` MUST 以对象式命名空间组织程序化 API，并为现有主要命令域提供可发现、可补全的访问路径。至少 SHALL 覆盖 `search`、`quote`、`stock`、`fund`、`bond`、`futures`、`market`、`resolve` 这些能力域。

#### Scenario: 命名空间属性可发现
- **WHEN** 调用方实例化 `OpenTrade()`
- **THEN** 对象 SHALL 暴露 `search`、`quote`、`stock`、`fund`、`bond`、`futures`、`market`、`resolve` 等命名空间属性

#### Scenario: 命令域方法与 CLI 语义对齐
- **WHEN** 调用方使用 `ot.stock.price_history(...)`、`ot.quote.price_latest(...)`、`ot.search.instruments(...)` 或 `ot.resolve.quote_id(...)`
- **THEN** 每个方法 SHALL 对应现有 CLI 命令树中的同等业务能力
- **AND** 方法命名 SHALL 体现业务语义而不是要求调用方传入字符串命令路径

### Requirement: 程序化 API SHALL 复用现有执行链并返回 Python 对象
程序化 API MUST 复用现有 shared command 定义、请求 schema 校验、backend 解析、执行器和 enrichment/observation 逻辑，以保持与 CLI 在能力和结果语义上的一致性。程序化入口 SHALL 直接返回 Python 对象，而不是终端渲染文本。

#### Scenario: 程序化调用复用现有 command 语义
- **WHEN** 调用方通过 `OpenTrade` 调用某个共享命令对应的方法
- **THEN** 请求 SHALL 经过与 CLI 相同的 schema 校验和 backend 选择流程
- **AND** 返回结果 SHALL 基于现有执行链物化后的 Python 对象

#### Scenario: 程序化入口不提供 watch 包装能力
- **WHEN** 调用方查看 `OpenTrade` 的公开程序化 API
- **THEN** API SHALL 不暴露 `watch` 入口
- **AND** 调用方 SHALL 不需要处理终端循环刷新语义

#### Scenario: 程序化入口不以终端输出参数为主要接口
- **WHEN** 调用方使用程序化 API
- **THEN** 主要接口 SHALL 围绕业务参数、`backend`、`view`、`indicator_level`、`trace_window`、`limit` 等结果相关参数设计
- **AND** API SHALL 不把 `format`、`output_path`、`transpose`、`no_index`、`encoding` 这类终端输出控制参数作为核心能力暴露

### Requirement: 技术指标 SHALL 保持在专用子包导入边界内
技术指标计算函数 MUST 继续通过 `opentrade.indicators` 及其子模块暴露。程序化市场数据 API SHALL 不把技术指标函数混入顶层 `opentrade` 导出或 `OpenTrade` 对象式入口中。

#### Scenario: 技术指标从子包导入
- **WHEN** 调用方执行 `from opentrade.indicators import macd` 或 `from opentrade.indicators.trend import macd`
- **THEN** 导入 SHALL 成功
- **AND** 该导入路径 SHALL 继续作为技术指标的标准入口

#### Scenario: 顶层入口与指标入口边界清晰
- **WHEN** 维护者检查 `opentrade` 顶层公共导出和 `OpenTrade` 对象接口
- **THEN** 技术指标函数 SHALL 不被平铺进顶层导出
- **AND** `OpenTrade` SHALL 专注于命令等价的数据访问能力而非纯计算指标函数集合
