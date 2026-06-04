## Context

当前 `opentrade` 已经形成稳定的统一执行骨架：

- `CommandExecutor` 负责命令级请求装配与结果后处理；
- `CommandFacade` 负责 single backend 与 `auto` backend 调度；
- `BackendProvider` 负责 capability handler 注册；
- `CapabilityHandler` 负责单个能力的业务调用与结果标准化。

但网络重试还没有进入这个骨架的稳定横切层。现状是 `opentrade/retry_utils.py` 提供了通用重试工具，但只有 `efinance` 的部分 handler 在显式调用它，`akshare` 与 `yfinance` 基本仍是直接调用上游函数。这样会带来三个问题：

1. 新 backend 接入时必须重复决定“哪里包 retry”，没有统一挂载点。
2. `auto` 模式下无法稳定表达“先在当前 backend 内消化瞬时网络失败，再决定是否跨 backend failover”。
3. side-effect 命令、限流错误、provider 专属 guardrails 的边界散落在不同 handler 内，后续很难审计和统一测试。

这次 change 的约束已经明确：

- 采用方案 B，把统一执行入口放在 `BackendProvider` 层，而不是直接挂到 `CommandFacade`；
- 限流错误属于可重试错误；
- `auto` 模式继续保留 facade 级多 backend failover，但顺序必须调整为“单 backend 内重试优先，跨 backend failover 在后”。

## Goals / Non-Goals

**Goals:**

- 为 `BackendProvider` 增加稳定的统一执行入口，承载网络重试这一横切逻辑。
- 让 `efinance`、`akshare`、`yfinance` 和未来 backend 能以一致方式声明自己的可重试异常集合。
- 把限流错误纳入 provider 级网络重试范围，并允许 provider 保留自身错误翻译语义。
- 保持 `auto` 的外层候选链 failover 机制，但确保每个候选 backend 在切换前先完成内部重试。
- 保持 side-effect 命令默认不自动重试，避免重复执行有副作用操作。
- 为新的执行层次补齐 regression 测试，保证 single backend 与 `auto` 行为都可验证。

**Non-Goals:**

- 不修改现有 command catalog、shared/provider-extension 分类规则。
- 不在本轮把所有 provider guardrails 统一抽象成全新框架。
- 不引入真实网络集成测试，也不改变当前 retry 的基础退避算法实现。
- 不改变 `auto` failover 的高层候选链顺序与 eligibility 语义，只调整其与单 backend 重试的先后关系。

## Decisions

### 决策一：把统一执行入口放在 `BackendProvider`，而不是 `CommandFacade`

`CommandFacade` 继续负责 single backend 与 `auto` backend 的调度、异常聚合和最终 `final_backend` 回写；`BackendProvider` 新增统一执行入口，负责：

- 根据命令定义判断是否允许自动重试；
- 读取 provider 自身声明的可重试异常集合；
- 在允许时用统一 retry 工具包裹 handler 的原子网络调用；
- 在不允许时直接执行 handler。

选择这一方案而不是把 retry 直接挂到 `CommandFacade`，原因是：

- provider 最清楚自己的网络异常模型，异常集合和 guardrail 语义不应全部挤进 facade；
- `CommandFacade` 保持“调度器”角色更清晰，避免同时承担 provider 内部策略判断；
- 后续新增 backend 时，只要补 provider 级策略，而不需要再碰 facade 的横切判断分支。

替代方案：

- 方案 A：在 `CommandFacade` 直接包装 `handler.execute`。优点是入口更集中；缺点是 provider 异常语义会被迫上浮到 facade，长期更容易演变成中央特判表。本次不采用。

### 决策二：统一重试以 provider 级策略声明“异常集合 + side-effect 豁免”

本次不让每个 handler 自己决定是否调用 `call_with_network_retry`。改为由 provider 暴露稳定策略元数据，例如：

- 默认可重试异常集合；
- 限流异常集合；
- 对 side-effect 命令的默认豁免；
- 必须直接透传的 guardrail 异常集合。

其中限流异常被视为可重试网络错误的一部分，但是否先做错误翻译由 provider 自己决定。也就是说：

- `yfinance` 仍可以把 `YFRateLimitError` 转换为带 Yahoo 语义的异常；
- 但该异常不会因此绕过 retry，而会被 provider 策略纳入可重试集合。

这样做的原因是：

- “限流也要重试”是跨 backend 的运行时规则；
- 但“限流错误长什么样”是 provider 私有实现细节；
- 两者应分层，而不应混在单个 handler 的 `try/except` 里。

### 决策三：`auto` 采用“两层恢复”模型

`auto` 执行顺序明确为：

1. facade 选择当前 candidate backend；
2. 当前 provider 通过统一执行入口完成单 backend 内部重试；
3. 若内部重试仍失败，异常返回 facade；
4. facade 再根据既有 failover eligibility 规则决定是否尝试下一个 backend。

执行流如下：

```text
CommandFacade._invoke_auto
  -> provider.execute_capability(...)
       -> provider retry policy
       -> handler.execute(...)
  -> fail? facade 判断是否进入下一个 backend
```

这样做的原因是：

- 瞬时网络抖动应优先在当前 backend 内吸收；
- provider 自身限流或短时链路故障不应立刻触发跨 backend 切换；
- failover 仍然保留为更高一层恢复手段，用于“当前 backend 经过内部重试仍失败”的情况。

替代方案：

- 先跨 backend failover，再让下一个 backend 自己 retry。这个顺序会导致 candidate 链切换过早，并放大不同 provider 的请求成本和不确定性，因此不采用。

### 决策四：side-effect 命令继续默认跳过自动重试

当前测试和已有语义已经把 `fund.reports.download` 这类命令视为 side-effect 命令，并要求其不经过自动 retry。该边界保留不变，但挂载点从 handler 内局部判断提升到 provider 统一执行入口。

这样可以避免：

- 下载命令被透明重复执行；
- 未来写入型 provider-extension 命令在未显式声明幂等性的情况下被自动重放。

### 决策五：现有 `retry_utils` 保留为基础设施，但去除 `efinance` 专属语义

`retry_utils` 继续作为统一 retry 封装工具存在，但其模块说明、缓存属性名和对外语义需要改成 backend-agnostic。它只负责：

- 包装单个原子网络调用；
- 保存原始签名；
- 按既定退避策略重复执行。

它不负责：

- 选择哪些异常可重试；
- 识别 side-effect 命令；
- 决定是否进入下一个 backend。

这些判断全部上移到 provider 执行入口或 facade。

## Risks / Trade-offs

- [风险] provider 级统一入口会改变现有 mock/patch 位置，导致部分单测需要整体改写。 → 缓解：同步补 facade/provider regression，优先让测试围绕新执行层次断言，而不是继续钉死旧的 handler 内调用点。
- [风险] 把限流纳入重试会增加单次命令时延。 → 缓解：沿用现有 retry 上限，不在本轮扩增重试次数；同时保留最终异常语义，避免“无限等待但看不出是限流”。
- [风险] 若 provider guardrail 与 retry 异常集合划分不清，可能把真正的参数错误误判为可重试。 → 缓解：provider 策略显式区分“可重试异常”和“直接透传异常”，并增加针对 `ValueError` / invalid period 等场景的测试。
- [风险] `auto` 两层恢复会让失败路径更难读。 → 缓解：保留 facade 级失败聚合，并在 observation / error message 中明确区分“backend 内部重试后失败”和“跨 backend failover 后失败”。

## Migration Plan

1. 先重构 `retry_utils` 的命名与对外语义，使其不再绑定 `efinance`。
2. 在 `BackendProvider` 引入统一执行入口和 provider 级 retry policy 元数据。
3. 把 `efinance` 现有局部 retry 调用迁入 provider 统一入口，消除 handler 内散落包装。
4. 为 `akshare`、`yfinance` 补 provider 级策略声明，并复查现有 guardrail 异常是否需纳入可重试集合或直接透传集合。
5. 调整 `CommandFacade`，让 single backend 与 `auto` 都通过 provider 统一执行入口，而不是直接调 `handler.execute`。
6. 补齐并更新 regression 测试，重点验证 side-effect 豁免、限流重试和 `auto` 两层恢复顺序。
7. 若验证发现 provider 级策略分类不合理，可回滚到“provider 统一入口存在但仅 `efinance` 启用 retry”的过渡状态；不回滚 facade 的结构改造。

## Open Questions

- 是否需要把 provider 级 retry policy 暴露成显式数据结构类，还是首轮先用简单属性/方法即可。
- 限流异常在最终失败时，是否需要额外在错误消息中暴露“已重试 N 次”这类信息。
- observation 是否需要单独记录“内部 retry 次数”，还是仅记录最终 backend 和最终异常即可。
