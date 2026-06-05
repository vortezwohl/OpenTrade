## Why

当前 opentrade 的多后端共享命令已经形成 request schema -> auto planner -> facade -> provider adapter -> rendering 的主干，但真实静态审查和多轮真实回归都说明，这条主干仍然把 provider 原生契约、shared 语义、backend 路由和模块边界混在一起。结果是 shared 命令表面统一、实际不统一，provider 适配职责过载，providers.py 演化成单文件巨型实现，继续修补只会放大结构腐化。

## What Changes

- 重新定义多后端 shared 命令的稳定输入契约，明确哪些字段是真正 provider-neutral 的 shared 语义，哪些字段必须留在 provider adapter 内部消化。
- 收敛 quote_id、ticker、A 股代码、market 枚举、单值/多值支持面的后端兼容边界，避免 shared 命令继续过度承诺 backend-neutral 能力。
- 将 opentrade/backends/providers.py 按 backend 和公共适配职责拆分为多个模块文件，保留 backends 包内聚，不再用单个 80KB 巨型模块承载全部 provider 实现。
- 调整 backend provider 工厂、注册表和测试布局，使 provider 构建、公共辅助函数、后端特有 adapter 和 shared 结果标准化各自落在清晰模块边界上。
- 为 shared contract、provider 支持矩阵、identifier 语义和 adapter 模块边界补充可验证 spec 与实现任务，确保后续实现不再靠隐式约定推进。
- 不在本次 change 中直接修复所有真实 API 稳定性问题，也不承诺引入新 backend；本次先解决结构性边界和模块拆分问题。

## Capabilities

### New Capabilities
- shared-provider-contracts: 定义 shared 命令在多 backend 下必须满足的统一输入契约、标识符语义和支持矩阵边界。
- provider-adapter-modularization: 定义 provider adapter 代码在 backends 包内的拆分边界、模块职责和工厂注册规则。
- provider-identifier-semantics: 定义 quote_id、ticker、A 股代码等跨 backend 标识符在 shared 命令中的允许语义与失败方式。
- provider-capability-truthfulness: 定义 shared 命令支持矩阵、单值/多值能力和 market 支持面必须与真实 provider 能力一致，禁止表面支持。
- provider-request-adaptation: 定义 shared 请求如何通过显式 adapter 翻译为 backend-native kwargs。
- adaptive-auto-routing: 定义 auto 路由如何建立在真实、收敛后的 shared identifier 和 capability truth 之上。

### Modified Capabilities
<!-- 当前仓库暂无 openspec/specs 基线，本次全部以新增 capability 落地。 -->

## Impact

- 主要受影响代码：
  - opentrade/backends/providers.py
  - opentrade/backends/factory.py
  - opentrade/backends/__init__.py
  - opentrade/command_catalog.py
  - opentrade/request_schema.py
  - opentrade/facade.py
  - opentrade/backends/auto_planner.py
  - provider 相关单元测试、契约测试和回归测试
- 可能新增的模块形态：
  - opentrade/backends/providers_common.py
  - opentrade/backends/efinance_provider.py
  - opentrade/backends/akshare_provider.py
  - opentrade/backends/yfinance_provider.py
  - 或等价的按职责拆分模块
- 不引入新第三方依赖，不修改 .venv 中第三方源码。
- 若实现按本 proposal 落地，部分 shared 命令的报错会更早、更明确地暴露“不支持该 backend / 不支持该输入形态”，这是预期的契约收紧，不视为回归。