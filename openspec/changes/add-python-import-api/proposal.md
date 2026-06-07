## Why

当前 `opentrade` 已经提供了较完整的 CLI 命令树和技术指标子包，但缺少一套面向其他 Python 程序的稳定 import 入口。随着命令目录、请求校验、后端路由和执行链已经收敛到统一骨架，现在补齐程序化 API 的时机已经成熟，可以避免外部调用方绕过 CLI 细节、重复拼装请求或直接依赖内部模块。

## What Changes

- 新增一个面向程序调用的 `opentrade.api` package，并以 `OpenTrade` 作为唯一推荐的顶层导出入口。
- 为 `search`、`quote`、`stock`、`fund`、`bond`、`futures`、`market`、`resolve` 提供对象式命名空间 API，使其能力覆盖现有 CLI 对应命令。
- 程序化 API 复用现有共享命令目录、请求 schema 校验、backend 选择、执行链和 enrichment 逻辑，保证与 CLI 在业务能力和结果语义上保持一致。
- 程序化 API **不提供** `watch` 入口，也不暴露仅用于 CLI 展示/输出的参数语义作为主接口能力。
- 技术指标继续通过 `opentrade.indicators` 及其子模块导入，不把指标函数平铺到 `from opentrade import ...`。
- 顶层 `opentrade` 导出保持直接、显式、利于 IDE 补全，不引入懒导入或动态导出机制。

## Capabilities

### New Capabilities
- `python-import-api`: 定义 `opentrade` 的对象式程序化 import API，包括 `OpenTrade` 顶层入口、命名空间组织、CLI 等价调用语义，以及指标子包的导入边界。

### Modified Capabilities

## Impact

- 受影响代码主要位于 `opentrade/__init__.py`、新增的 `opentrade/api/` package，以及少量现有执行链复用点。
- 对外 API 会新增 `from opentrade import OpenTrade` 的稳定入口。
- 现有 CLI 行为、技术指标实现、后端 provider 逻辑和依赖集合不要求发生破坏性调整。
- 需要新增程序化 API 回归测试，验证 import 可用性、对象式命名空间补全友好性，以及 API/CLI 的能力对齐。
