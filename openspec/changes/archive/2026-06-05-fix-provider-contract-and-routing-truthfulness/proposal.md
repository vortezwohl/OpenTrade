## Why

当前多后端 shared 命令表面上已经完成统一，但静态审查表明 `opentrade` 仍存在多处“shared 契约声明”和“后端真实接口能力”不一致的问题，尤其集中在 `quote.*` 适配、A 股到 Yahoo ticker 的翻译闭环、以及 auto 路由候选真实性过滤。这些问题已经不再是单点 bug，而是 shared contract、provider adapter 与 auto planner 三层边界失真，需要一次成体系的修复方案来恢复接口真实性、路由可解释性和后续演化安全性。

## What Changes

- 收敛 shared identifier 契约，明确 `symbol`、`symbols`、provider-native `quote_id`、Yahoo ticker、A 股六码在 shared 命令中的允许语义、禁止语义和适配责任。
- 修复 `efinance` 的 `quote.price.latest`、`quote.profile` 等路径，使其必须通过显式 identifier adaptation 把 shared 输入翻译为东财真实 `quote_id`，而不是误用 passthrough。
- 修复 `yfinance` 的 A 股共享标识处理链路，使历史、实时、资料等共享能力真正接入本地 ticker 翻译闭环，或在不支持时显式拒绝，而不是宣传支持但实际原样透传。
- 让 auto backend planning 在生成候选链时真正使用请求真实性过滤，避免把明知不支持当前请求形状的 backend 继续纳入候选链。
- 修复 auto planner 中对 `quote.*` 共享字段读取仍依赖旧字段名的问题，使其与当前 normalized shared request 一致。
- 对齐 shared capability matrix 与真实 provider 能力，明确哪些命令只支持单标的、哪些市场语义不被某 backend 支持，并将这种限制落入契约与错误语义，而不是留给运行期偶发失败。
- 补充针对 provider contract truthfulness、identifier adaptation、auto routing truthfulness 的回归测试与契约测试，确保这次修复不会被后续改动悄悄打回。
- 整治关键 provider 模块的编码与中文注释乱码问题，恢复仓库内文档化边界的可读性与可维护性。

## Capabilities

### New Capabilities
- `provider-identifier-semantics`: 定义 shared identifier 与 provider-native identifier 之间的允许语义、拒绝规则与翻译责任边界。
- `provider-capability-truthfulness`: 定义 shared 能力矩阵必须如实反映单标的/多标的、市场支持面与 backend 实际能力，不允许表面支持。

### Modified Capabilities
- `provider-request-adaptation`: 补充 `quote.*` 路径必须通过显式 identifier adaptation 命中后端真实接口，不得再依赖错误 passthrough。
- `adaptive-auto-routing`: 调整 auto 候选规划，使其必须基于 normalized request 和真实性过滤结果生成候选链，并修复旧字段名读取问题。
- `shared-input-normalization`: 明确 `quote.*` 共享字段的标准归一化结果，并保证 planner / adapter / facade 读取同一份 normalized contract。
- `provider-compatibility-guardrails`: 补充“不支持的 shared 输入形状或市场语义”必须以稳定、可解释的 provider contract failure 暴露，而不是隐式远端失败。
- `provider-execution-entry`: 保证 auto 执行链记录的尝试候选、最终命中 backend 与契约失败语义与真实性路由一致。

## Impact

- 主要受影响代码：
  - `opentrade/backends/efinance_provider.py`
  - `opentrade/backends/yfinance_provider.py`
  - `opentrade/backends/akshare_provider.py`
  - `opentrade/backends/auto_planner.py`
  - `opentrade/backends/providers_common.py`
  - `opentrade/request_schema.py`
  - `opentrade/command_catalog.py`
  - `opentrade/facade.py`
  - `opentrade/models.py`
  - provider 与 shared contract 相关测试集
- 预期行为影响：
  - 部分原本“看似支持、实则误配”的 shared 命令会更早失败，并给出更明确的 contract 错误。
  - `auto` 模式的候选顺序、尝试链和最终命中 backend 可能发生变化，这是契约真实性修复的预期结果。
  - `quote.*`、A 股 `yfinance`、单标的限制等路径的原有模糊行为会被收紧或显式翻译。
- 不引入新第三方依赖，不修改 `.venv` 内第三方源码。