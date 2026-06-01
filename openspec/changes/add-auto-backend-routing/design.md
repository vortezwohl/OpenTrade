## Context

当前运行时 backend 选择模型非常直接：

- `BackendName` 只包含真实 provider：`efinance`、`akshare`、`yfinance`
- [efinance_cli/backends/resolver.py](/D:/Projects/PythonProjects/efinance-cli/efinance_cli/backends/resolver.py) 中 `DEFAULT_BACKEND = BackendName.EFINANCE`
- 未显式指定 backend 的共享命令统一解析到这个默认 backend
- provider-extension 命令未显式指定 backend 时，解析到其 `provider_name`
- [efinance_cli/facade.py](/D:/Projects/PythonProjects/efinance-cli/efinance_cli/facade.py) 只会对一个 `backend.resolved` 调一次 provider handler
- enrichment / observation 的历史回补继续沿用 `request.backend_selection`
- `shared` / `provider-extension` 的分类收紧已经完成，当前 `shared` 目录只保留真正多 backend 的命令
- [efinance_cli/backends/factory.py](/D:/Projects/PythonProjects/efinance-cli/efinance_cli/backends/factory.py) 当前已无 optional provider，占位过滤不再是 `yfinance` 的特殊路径，而只是未来扩展时的通用保护

这个结构的优点是简单，但它隐含两个限制：

1. backend 解析结果只能是一个 concrete provider，不能表达“候选链”。
2. 一旦默认 backend 临时异常，主链不会自恢复，只能由用户手动重跑并切换 `--backend`。

这次设计默认建立在一个已经完成的前置基线上：

- `archive/2026-05-31-reclassify-single-backend-commands` 已经把单 backend 命令迁出了 shared catalog；
- 当前需要解决的是“多 backend 共享命令如何默认走受控路由”，而不是重新讨论命令分类边界；
- `yfinance` 已经完成正式注册，因此 `auto` 候选链在实现时应直接把它作为正式候选；保留注册过滤只是为了兼容未来可能新增但暂未接入的 provider。

## Goals / Non-Goals

**Goals:**

- 让 `auto` 成为默认 backend 语义，而不是要求用户显式记忆最优 provider。
- 让共享命令在默认路径下具备受控的跨 backend 降级能力。
- 让 provider-extension 命令在 `auto` 模式下自动适配到所属 provider。
- 让最终成功命中的 concrete backend 在 enrichment、observation、watch 和错误输出中保持一致。
- 让失败聚合足够清晰，避免误把用户输入错误当作可降级故障。

**Non-Goals:**

- 不把 `auto` 注册成真实 `BackendProvider`。
- 不要求所有命令都参与多 backend failover，尤其 provider-extension 不需要按全链路尝试。
- 不在本轮设计复杂的 backend 健康缓存、熔断器或长期状态记忆。
- 不在本轮改变各 provider 自己的 handler 实现逻辑，只在路由与执行骨架层加策略。
- 不重复实现已归档的 shared / provider-extension 重分类工作。

## Decisions

### 决策一：`auto` 作为路由策略存在，不作为真实 provider 存在

`auto` 会进入 backend 选择语义，但不会出现在 `list_backend_providers()` 返回值中。

原因：

- `auto` 不提供任何 capability handler，也不生产任何标准结果；
- 它只是控制“试谁、按什么顺序试、何时继续、何时停止”；
- 如果把它伪装成 provider，会迫使 `get_backend_provider()`、`supports()`、扩展命令注册等真实 provider 语义变得扭曲。

### 决策二：默认 backend 改为 `auto`，但默认 concrete backend 优先级改为 `akshare`

解析规则将变为：

- 未传 `--backend` 的共享命令：默认 `requested = auto`
- `auto` 的候选链优先级：`akshare -> yfinance -> efinance`
- 未传 `--backend` 的 provider-extension 命令：默认解析到该命令所属 provider，不进入全链路 failover

原因：

- 默认行为已经明确要求从固定 backend 切到 `auto`；
- 第一候选要体现“默认 concrete backend 从 efinance 改为 akshare”；
- provider-extension 没有必要先试无关 provider，再退回所属 provider；
- 当前 `yfinance` 已覆盖部分共享命令与 `quote news` 扩展命令，因此把它放入共享命令候选链、同时让扩展命令继续保留所属 provider 直达语义，是现在最符合代码现实的拆分方式。

### 决策三：扩展 backend 选择结构，显式承载候选链与最终命中 backend

当前 `BackendSelection` 只有：

- `requested`
- `resolved`
- `source`

它不足以表达 `auto` 的两阶段语义。设计上需要新增类似：

- `candidate_chain: tuple[BackendName, ...]`
- `final_backend: BackendName | None`
- `is_auto: bool`

其中：

- `resolved` 表示本次解析后的主要执行语义，可能是 `auto` 或已确定的 concrete backend；
- `candidate_chain` 表示 `auto` 可尝试的真实 backend 列表；
- `final_backend` 表示最终成功命中的 concrete backend。

### 决策四：failover 只对可降级错误继续，对输入错误立即停止

`auto` 不应实现成“抛任何异常都继续试下一个 backend”。建议分成三类：

- 可降级错误：
  - 网络异常
  - 限流异常
  - provider 不可用
  - provider 对该请求形状不支持
- 立即失败错误：
  - schema 校验失败
  - 缺少必填参数
  - 明显非法输入
- 全链路失败：
  - 记录每个 backend 的失败原因并聚合报错

### 决策五：provider-extension 在 `auto` 下走“自动适配”，不走完整降级链

对 provider-extension 命令：

- 若用户未传 `--backend`，仍走命令所属 provider；
- 若用户显式传 `--backend auto`，也直接适配到该命令所属 provider；
- 若用户显式传错误 concrete backend，仍立即报错。

### 决策六：最终命中 backend 必须回写到执行上下文

`CommandFacade` 成功命中某个 concrete backend 后，执行主链必须把这个 backend 回写到 `InvocationRequest.backend_selection` 或其等价运行时结果中。

原因：

- [efinance_cli/enrichment/service.py](/D:/Projects/PythonProjects/efinance-cli/efinance_cli/enrichment/service.py) 当前会继续用 `request.backend_selection` 做历史回补；
- [efinance_cli/executor.py](/D:/Projects/PythonProjects/efinance-cli/efinance_cli/executor.py) 当前会先执行主命令、再串行进入 enrichment / observation；
- 如果保留 `auto` 而不回写 concrete backend，增强链要么无法运行，要么会误用错误 provider；
- watch 模式展示、raw 输出和调试信息也都应该反映真实命中 backend。

## Risks / Trade-offs

- [风险] `auto` 会让执行主链从“一次调用”变成“多次候选尝试”，复杂度上升。 → 缓解：把多 backend 尝试集中在 resolver/facade/executor，避免扩散到 provider 层。
- [风险] 如果错误分类做不好，`auto` 可能掩盖真实用户输入错误。 → 缓解：把 schema/参数错误定义为立即失败，禁止继续降级。
- [风险] 未来新增 provider 可能再次出现“枚举已存在、运行时尚未正式接入”的阶段性状态。 → 缓解：候选链在运行前统一过滤“命令支持 + provider 可用性”，但不要把 `yfinance` 继续当作特殊跳过分支。
- [风险] enrichment / observation 可能继续引用抽象 backend 而不是最终命中 backend。 → 缓解：要求 facade/executor 回写 final backend，并补充针对增强链的测试。
- [风险] provider-extension 的 `auto` 语义容易和共享命令的 failover 混淆。 → 缓解：文档与帮助明确区分“共享命令 auto=降级链”和“扩展命令 auto=自动适配所属 provider”。
- [风险] 当前 runtime `--count` 与某些扩展命令的业务参数曾出现命名重叠。 → 缓解：延续现有做法，保持业务参数和 runtime 参数语义分离，避免 `auto` 设计顺手放大 CLI 歧义。

## Migration Plan

1. 在 `BackendSelection` 中引入 `auto` 及候选链元数据。
2. 修改 resolver，把未显式指定 backend 的共享命令默认解析到 `auto`，并构造 `akshare -> yfinance -> efinance` 候选链。
3. 修改 facade / executor，引入多 backend 尝试、错误聚合与最终命中 backend 回写。
4. 修改 provider-extension 的默认路由规则，使 `auto` 可自动适配所属 provider。
5. 校正 enrichment / observation / watch，对最终命中 backend 做一致性验证。
6. 最后更新测试与文档，确保默认行为变化被完整覆盖。

当前基线确认：

- 第 0 步前置条件已满足：单 backend 命令重分类已归档完成；
- 本 change 真正从第 1 步开始实施，不需要回退去改 shared catalog 分类语义。

回退策略：

- 如果 `auto` 主链不稳定，可先保留 `provider-extension` 的 auto 自适配，临时关闭共享命令的全链路 failover；
- 如果增强链兼容性有问题，可先保证主命令正确执行，再局部修复 final backend 回写与补数链。

## Open Questions

- 当 `auto` 的第一候选 backend 已支持命令但返回空结果时，这应被视为成功还是可降级失败？
- 是否需要在 raw 输出中显式增加 `attempted_backends` 与 `final_backend` 元信息？
- 对 `watch --backend auto`，是否要每轮都重新从 `akshare` 开始，而不是记住上一轮成功 backend？
