## Why

当前共享命令骨架已经能把多 backend 命令跑通，但最近几轮真实回归和结果分析也暴露出一组系统性问题：共享输入契约、auto 路由策略、provider 适配边界、`market/fs` 语义、`--limit` 执行语义和回归分类口径彼此没有收敛，导致样本错配、上游波动和产品缺陷被混在一起，同时把大量慢调用放大成整条命令超时。

现在需要把这些问题集中收口，是因为它们已经不再是单个 bug，而是共享执行链的基础行为缺陷。如果继续沿用当前命令目录、generic passthrough 和静态 auto 候选顺序扩展功能或补测试，错误的输入假设和错误的路由语义会继续固化到公共骨架里。

## What Changes

- 统一 shared 命令的输入契约，明确日期、symbol、quote-id、market 等字段在 CLI 层的稳定形态，并要求 provider 适配层负责把统一输入翻译为上游真实参数格式。
- 将 `auto` backend 从静态候选顺序改为请求感知排序，按命令类型、市场语义和标的形态选择更合理的候选链，并为候选执行补充可观测的预算与 trace。
- 收敛 shared schema 到 provider 的适配边界，减少直接 `callback(**request_data)` 的 generic passthrough，优先为 history、realtime、profile、search、resolve 等命令簇建立显式输入适配。
- 统一 `market` 抽象语义，禁止在 shared 层直接混用 provider 原生 `fs` 过滤表达式；对必须保留 provider 原生过滤的命令，显式声明独立适配路径。
- 修复 `stock.profile` 一类请求形态歧义，明确 shared 能力的单标的/多标的边界，避免共享层表面支持多值、provider 实际只支持单值的错位。
- 将 `--limit` 从纯展示裁剪收敛为“显示裁剪”和“执行减载”两层语义，对重路径命令按能力拆分前置减载策略，避免继续把显示层参数伪装成执行层参数。
- 重构真实回归脚本和测试集，区分 `sample_mismatch`、`adapter_gap`、`product_defect`、`upstream_instability` 等失败分类，并同步更新当前把错误 auto 候选顺序或旧抽象固化为正确行为的测试断言。

## Capabilities

### New Capabilities
- `shared-input-normalization`: 定义 shared CLI 输入的统一日期、标的、市场和 quote 标识契约，以及 provider 适配前的标准化边界。
- `adaptive-auto-routing`: 定义请求感知的 auto backend 候选排序、候选执行预算和候选 trace 语义。
- `provider-request-adaptation`: 定义 shared schema 到 provider 调用参数的显式适配边界，覆盖 history、realtime、profile、search、resolve 等关键命令簇。
- `execution-aware-limiting`: 定义显示层裁剪与执行层减载的区别，并为重路径命令建立前置减载要求。
- `regression-failure-classification`: 定义真实回归脚本的失败分类语义和结果报告边界，避免把样本错配直接记成产品缺陷。

### Modified Capabilities

无。

## Impact

- 主要影响代码：
  - `opentrade/command_catalog.py`
  - `opentrade/request_schema.py`
  - `opentrade/commands.py`
  - `opentrade/backends/resolver.py`
  - `opentrade/facade.py`
  - `opentrade/backends/providers.py`
  - `opentrade/rendering.py`
  - `scripts/run_third_full_regression.py`
  - `scripts/run_incremental_full_regression.py`
  - `tests/test_schema_and_resolver.py`
  - `tests/test_cli_full_regression.py`
  - `tests/test_multi_backend_scaffold.py`
  - `tests/test_facade_unit.py`
  - 视实现方式补充 provider / rendering / regression 相关测试
- 主要影响行为：
  - shared 命令的输入契约会变得更严格、更统一，provider 自身参数语义不再直接泄漏到 shared 层；
  - `auto` 的默认路由行为会发生变化，且会按请求语义而不是固定顺序选择候选 backend；
  - `--limit` 不再默认等同于“仅展示前 N 行”，部分命令会增加真正的执行减载语义；
  - 真实回归报告会显式区分样本错配、适配缺口、产品缺陷和上游不稳定。
- 风险：
  - 这项变更会触碰 shared 命令目录、backend resolver、provider 适配层和测试基线，影响面比单点 bug 修复更大；
  - 若输入统一和 provider 适配边界定义不清，可能把现有“勉强可跑”的命令临时收紧成显式失败；
  - 若 `auto` 候选策略或执行减载改动过急，可能改变现有观测结果与脚本断言，需要同步更新测试和报告口径。
