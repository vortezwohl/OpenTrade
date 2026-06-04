## Why

2026-06-04 的真实 API 全量回归已经确认，当前 CLI 在多条真实命令链路上存在确定性的产品缺陷，而不是单纯的上游波动：内部执行层 `--limit` 元数据会泄漏到第三方 SDK kwargs，`auto` 模式会把本应继续兜底的 provider 失败过早判定为不可切换，且部分命令的共享参数契约与真实 provider 契约不一致。它们直接导致真实命令失败、兜底失效和错误归因失真，必须先收敛这些本地缺陷，后续才谈得上扩大真实回归覆盖和评价上游可用性。

## What Changes

- 修复执行层内部控制字段泄漏到 provider kwargs 的问题，确保 `--limit` 等内部元数据不会再以 `__runtime_limit__` 之类的形式传入 efinance、akshare、yfinance 上游函数。
- 重新定义 `auto` backend 的 failover 可切换判定，把“用户输入错误/本地契约错误”和“provider 故障/远端异常/上游结构漂移”区分开，避免真实可恢复错误提前终止兜底链。
- 为真实回归中已证实的 provider 契约不一致和坏返回增加适配护栏，包括共享日期输入到 provider 日期格式的归一化，以及对已知上游坏返回的稳定错误归类与降级策略。
- 补充针对这些确定性缺陷的定向回归测试和真实回归样本分类规则，让报告能够区分“本地 bug”“上游崩溃”“真实不可用”，而不是把它们混成同一类失败。
- 不在本次变更中重写整个 provider 架构，不承诺修复第三方库自身实现，只在本地边界内建立可验证、可维护的防线。

## Capabilities

### New Capabilities
- `provider-request-sanitization`: 约束执行层内部元数据与 provider 原生请求参数隔离，防止内部控制字段泄漏到第三方 SDK 调用。
- `auto-failover-error-classification`: 定义 auto backend 对不同错误类别的切换规则，确保可恢复的 provider 失败不会被误判为不可兜底。
- `provider-compatibility-guardrails`: 为已知真实回归缺陷建立 provider 适配、日期归一化、坏返回收口与错误归类的行为契约。

### Modified Capabilities
<!-- 本仓库当前无既有 specs，留空。 -->

## Impact

- 受影响代码主要集中在 [facade.py](/D:/github-project/efinance-cli/opentrade/facade.py)、[providers.py](/D:/github-project/efinance-cli/opentrade/backends/providers.py)、[auto_planner.py](/D:/github-project/efinance-cli/opentrade/backends/auto_planner.py)、[executor.py](/D:/github-project/efinance-cli/opentrade/executor.py) 以及真实回归脚本与测试集。
- 不引入新依赖，不新增 backend，不改变 CLI 命令树。
- 可能改变部分失败命令的报错类型、fallback 轨迹和 raw/observation 元数据，但目标是让这些变化更真实地反映系统行为，而不是改变成功结果结构。
