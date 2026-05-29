# AKShare 后端适配实施方案

## 1. 文档目的

本文档用于指导 `efinance-cli` 从“单一 `efinance` 后端 CLI”演进为“可接入 `efinance` 与 `akshare` 的多后端 CLI”，并在保持现有可用命令的基础上，为 `akshare` 提供可扩展的超集命令。

本文档不是概念性讨论，而是面向落地实施的工程方案。重点回答以下问题：

- 当前架构为什么不能直接切换到 `akshare`
- 适配器方案的最小可行结构是什么
- 哪些命令应做共享适配，哪些命令应保留为 `efinance` 专属
- `akshare` 超集命令应如何接入而不污染现有命令树
- 如何分阶段实施、验证、回滚与控制风险

## 2. 设计来源与原则

本方案的架构设计灵感来自：

- [AI Coding 时代, 学习并理解设计模式将变得愈发重要](https://vortezwohl.github.io/software-engineering/2026/05/22/AI-Coding-%E6%97%B6%E4%BB%A3-%E7%90%86%E8%A7%A3%E8%AE%BE%E8%AE%A1%E6%A8%A1%E5%BC%8F%E5%8F%98%E5%BE%97%E6%9B%B4%E5%8A%A0%E9%87%8D%E8%A6%81.html)

文章中的核心判断不是“为了工程感而套模式”，而是：

- 先识别变化点，再决定是否引入模式
- 用模式管理变化，而不是制造抽象噪音
- 在 AI Coding 时代，结构约束的价值高于局部实现速度

针对本项目，真实变化点非常明确：

- 数据后端会变化，`efinance` 不再是唯一来源
- 不同后端接口形态不同，但 CLI 命令语义需要尽量稳定
- 某些命令是共享能力，某些命令天然带有后端特有语义
- observation、indicator enrichment、rendering 不应被后端细节污染

因此本文档只精确引入以下模式：

- `Adapter`
  用于把 `akshare` 与 `efinance` 的异构接口翻译成统一后端能力接口。
- `Strategy`
  用于在运行时选择具体后端实现，而不是在命令处理处写大量条件分支。
- `Facade`
  用于把“命令语义 -> 后端调用 -> 结果标准化 -> observation/enrichment”组织成统一高层入口。
- `Proxy`
  用于封装网络重试、限流、缓存、能力检查等访问控制逻辑，而不是散落在各命令中。
- `Decorator`
  用于附加重试、指标增强、标准化、观测日志等横切能力。
- `Template Method`
  用于固定命令执行骨架，把“参数归一化、调用、标准化、渲染”稳定下来。

不引入的内容：

- 不为“未来可能有更多后端”预埋复杂插件系统
- 不先做通用 DI 容器
- 不先做动态加载的 provider marketplace
- 不把所有命令一开始都改造成完美抽象

## 3. 当前现状评估

### 3.1 当前架构的优点

当前项目已经具备一定分层，适合做渐进式改造：

- `efinance_cli/commands.py`
  负责命令树构建与统一运行时参数挂载。
- `efinance_cli/registry.py`
  维护命令白名单、帮助文本、CLI 路径和回调。
- `efinance_cli/executor.py`
  维护统一执行骨架。
- `efinance_cli/enrichment/service.py`
  负责技术指标增强。
- `efinance_cli/observation.py`
  负责 observation 输出。
- `efinance_cli/rendering.py`
  负责统一渲染。

这意味着项目不是把所有逻辑糊在一个 Click 文件里，存在重构空间。

### 3.2 当前架构的主要问题

当前项目虽然有分层，但“上层语义”和“底层后端”并未分离，主要表现在：

- `registry.py` 直接枚举 `efinance` 模块与函数白名单
- `fund_compat.py` 直接 import `efinance` 内部模块
- `enrichment/service.py` 直接调用 `efinance.*.get_quote_history`
- 测试大量直接 patch `efinance` 函数
- 命令帮助文本中直接暴露“对应函数: efinance.xxx.yyy”

因此当前结构本质上是：

```text
CLI 命令 -> efinance 函数 -> pandas 结果 -> enrichment / observation / rendering
```

而不是：

```text
CLI 命令 -> 命令语义 -> 后端能力 -> 标准化结果 -> enrichment / observation / rendering
```

### 3.3 为什么不能直接把 `akshare` 塞进现有 registry

因为当前 registry 管理的是“上游函数白名单”，不是“命令能力白名单”。

例如：

- `resolve quote-id`
- `quote price history`
- `market add`
- `search local`

这些命令本身就带有明显的 `efinance` 语义，不是简单换成 `akshare` 某个函数即可等价成立。

因此，必须先把“命令能力”与“上游实现”拆开。

## 4. 目标、非目标与约束

### 4.1 Objective

- 在不破坏现有 CLI 基础体验的前提下，为项目引入 `akshare` 后端适配能力
- 让一部分共享命令支持 `efinance` 与 `akshare`
- 保留无法等价迁移的 `efinance` 专属命令
- 为 `akshare` 增加明确的超集命令入口
- 让 observation、indicator enrichment、rendering 继续复用，不直接耦合具体后端

### 4.2 Non-goals

- 不追求首版覆盖全部现有 50 个叶子命令
- 不追求所有命令都做到双后端无差异
- 不追求首版支持任意第三方数据后端
- 不追求把 `efinance` 与 `akshare` 的全部字段完全统一
- 不在首版引入复杂插件系统或运行时动态发现机制

### 4.3 Constraints

- 必须尽量保持现有用户命令可用
- 不能把 `quote_id` 这种后端特有概念强行伪装成跨后端通用概念
- 必须允许命令显式声明“仅支持某后端”
- 必须为新增结构提供自动化验证路径
- 必须控制 diff 半径，优先渐进演进

## 5. 命令能力分层策略

命令必须重新划分为三层，而不是一视同仁。

### 5.1 Shared 命令

定义：

- 命令的业务语义清晰
- `efinance` 与 `akshare` 都能提供近似能力
- 虽然字段细节不同，但可以通过标准化层收束

建议首批纳入 shared 的命令：

- `stock price history`
- `stock price latest`
- `stock price live`
- `stock profile`
- `fund nav history`
- `fund nav history-batch`
- `fund profile`
- `fund catalog`
- `fund managers`
- `futures catalog`
- `futures price history`
- `futures price live`
- `bond price history`
- `bond price live`
- `watch`

### 5.2 Efinance-only 命令

定义：

- 命令语义直接绑定 `efinance` 的内部模型或东财式入口
- 强行适配会引入误导性语义

建议保留为 `efinance` 专属的命令：

- `resolve quote-id`
- `quote profile`
- `quote price latest`
- `quote price history`
- `quote trades`
- `quote flow history`
- `quote flow today`
- `market add`
- `search local`

说明：

- 这些命令不应在 `akshare` 后端下伪造成功
- 应在帮助文本与运行时能力检查中明确提示“仅支持 efinance 后端”

### 5.3 AKShare Superset 命令

定义：

- 这些命令不是为了兼容旧语义，而是为了释放 `akshare` 覆盖面更广的价值

建议新增的 `akshare` 超集命令组：

- `macro`
- `index`
- `industry`
- `option`
- `forex`
- `rate`
- `commodity`

说明：

- 这类命令不应伪装成 `efinance` 旧命令
- 应以“新增能力”的方式加入命令树

## 6. 总体架构方案

### 6.1 目标结构

```text
Click CLI
  -> Command Registry（命令语义注册）
  -> Backend Resolver（后端选择）
  -> Command Facade（统一调用入口）
  -> Backend Adapter（efinance / akshare）
  -> Result Standardizer（结果标准化）
  -> Enrichment / Observation / Rendering
```

### 6.2 模块职责建议

建议新增或调整以下模块：

- `efinance_cli/backend_types.py`
  定义后端枚举、能力名、标准结果模型。
- `efinance_cli/backends/base.py`
  定义 `MarketBackend` 协议或抽象基类。
- `efinance_cli/backends/efinance_backend.py`
  封装现有 `efinance` 实现。
- `efinance_cli/backends/akshare_backend.py`
  封装 `akshare` 适配实现。
- `efinance_cli/backends/factory.py`
  根据 `--backend` 或默认策略创建后端实例。
- `efinance_cli/command_catalog.py`
  用“命令能力定义”替代当前“上游函数白名单定义”。
- `efinance_cli/standardization.py`
  把不同后端输出统一到 CLI 可消费的列模型。
- `efinance_cli/capabilities.py`
  定义命令能力与后端支持矩阵。

已有模块的改造方向：

- `registry.py`
  从“efinance 函数注册中心”转为“命令定义注册中心”。
- `executor.py`
  保留模板执行骨架，但调用对象由函数回调改为命令门面。
- `enrichment/service.py`
  不再直接 import `efinance`，改走 backend facade 获取历史数据。
- `fund_compat.py`
  降级为 `efinance` backend 的内部兼容实现，不再作为 CLI 全局语义的一部分。

## 7. 核心模式映射到本项目的具体用法

### 7.1 Adapter

适用位置：

- `EfinanceBackend`
- `AkshareBackend`

职责：

- 把各自上游函数签名翻译成统一方法签名
- 把上游返回值转换成统一结构
- 收束上游异常风格

例子：

- `efinance.stock.get_quote_history`
- `akshare.stock_zh_a_hist`

二者参数名、默认值、时间粒度、返回列并不一致，应由 adapter 负责翻译。

### 7.2 Strategy

适用位置：

- `BackendResolver`
- `CommandFacade`

职责：

- 在运行时选择 `efinance` 或 `akshare`
- 避免在命令处理逻辑中出现大量 `if backend == ...`

### 7.3 Facade

适用位置：

- `CommandFacade`

职责：

- 接收命令语义请求
- 调用后端能力
- 做标准化
- 再把结果交给 enrichment / observation / rendering

这样调用方只面对“一个稳定入口”，而不是直接接触后端细节。

### 7.4 Proxy

适用位置：

- 后端网络调用包装
- 能力检查包装
- 限流与重试包装

职责：

- 执行前检查当前命令是否被当前后端支持
- 统一附加重试、缓存、节流、告警

### 7.5 Decorator

适用位置：

- `with_network_retry`
- 结果标准化后的增强链
- 调试日志或 tracing

职责：

- 不改业务调用接口，只叠加横切能力

### 7.6 Template Method

适用位置：

- `CommandExecutor.run()` 与 `invoke()`

建议固定骨架：

1. 解析命令请求
2. 解析后端
3. 做能力检查
4. 调用命令门面
5. 标准化结果
6. 做 enrichment
7. 做 observation
8. 做 rendering
9. 输出或 watch 循环

## 8. 标准后端接口设计

首版不需要定义一个巨大的全能接口，而应定义“命令能力接口”。

建议采用以下两层结构：

### 8.1 基础后端协议

```python
class MarketBackend(Protocol):
    backend_name: str

    def supports(self, capability: str) -> bool:
        ...
```

### 8.2 能力方法集合

```python
class MarketBackend(Protocol):
    backend_name: str

    def supports(self, capability: str) -> bool:
        ...

    def search(self, query: str, market: str | None, limit: int) -> pd.DataFrame:
        ...

    def stock_price_history(
        self,
        symbol: str,
        start_date: str | None,
        end_date: str | None,
        timeframe: str | int | None,
        adjustment: str | int | None,
    ) -> pd.DataFrame:
        ...

    def stock_price_live(self, market: str | None = None) -> pd.DataFrame:
        ...

    def stock_profile(self, symbol: str) -> pd.Series | pd.DataFrame:
        ...

    def fund_nav_history(self, symbol: str, limit: int | None = None) -> pd.DataFrame:
        ...
```

实现要求：

- 首版只定义首批 shared 命令需要的方法
- 后续按命令增量扩展
- 不要一开始就把全部 50 个命令塞进一个超大接口

## 9. 标准结果模型设计

### 9.1 为什么必须做标准化

`efinance` 与 `akshare` 的差异不只在函数名，还在：

- 返回值类型不同
- 中文列名不同
- 时间字段格式不同
- 同一语义字段的命名不同
- 某些后端返回 `Series`，某些返回 `DataFrame`

如果不做标准化：

- `observation.py` 会继续充满后端特判
- `enrichment/service.py` 无法复用
- `rendering.py` 会被迫理解越来越多上游细节

### 9.2 标准化层职责

建议新增 `standardization.py`，负责：

- 字段名映射
- 日期列归一化
- 代码列归一化
- K 线列归一化
- 单行结果与表格结果统一
- 多标的字典结果统一

建议至少统一以下关键字段：

- `代码`
- `名称`
- `日期`
- `开盘`
- `收盘`
- `最高`
- `最低`
- `成交量`
- `成交额`
- `涨跌幅`
- `涨跌额`
- `换手率`

说明：

- 标准化层的目标不是保留所有原始字段
- 原始字段可在 `--view raw` 下保留
- `observation` 与 enrichment 应优先依赖标准字段

## 10. 命令注册模型重构方案

### 10.1 当前问题

当前 `registry.py` 主要在管理：

- 上游模块名
- 上游函数名
- CLI 路径
- 帮助文本

这使得命令定义与后端实现绑定。

### 10.2 重构目标

命令定义应改为下面这种结构：

```python
@dataclass(slots=True)
class CommandDefinition:
    command_key: str
    cli_path: tuple[str, ...]
    help_text: str
    capability: str
    supported_backends: set[str]
    allow_watch: bool
    has_side_effect: bool
    request_builder: Callable[..., dict[str, Any]]
```

说明：

- `command_key` 是内部稳定标识，例如 `stock.price.history`
- `capability` 是后端能力名，例如 `stock_price_history`
- `supported_backends` 用于运行时和帮助页提示
- `request_builder` 用于把 CLI 参数翻译成标准请求字典

### 10.3 推荐拆分

建议把当前 `registry.py` 拆成：

- `command_catalog.py`
  管理命令定义。
- `legacy_efinance_mapping.py`
  保存从旧 `efinance` 函数到新命令定义的迁移关系，便于过渡。

## 11. CLI 层改造方案

### 11.1 新增全局后端参数

建议为所有共享命令增加统一参数：

```text
--backend efinance|akshare
```

默认策略建议：

- 首版默认仍为 `efinance`
- 共享命令允许显式切换为 `akshare`
- `efinance-only` 命令若传 `--backend akshare`，应明确报错

### 11.2 是否需要配置默认后端

建议第二阶段再支持：

- 环境变量，例如 `EFI_BACKEND=akshare`
- 配置文件默认后端

首版先不做，避免修改范围过大。

### 11.3 帮助文本策略

帮助文本中应明确：

- 当前命令支持哪些后端
- 当前命令是否为共享命令
- 某些命令是否为 `efinance` 专属
- 某些命令是否为 `akshare` 超集命令

## 12. enrichment 与 observation 改造方案

### 12.1 enrichment 改造目标

当前 `enrichment/service.py` 直接调用 `efinance.*.get_quote_history` 回补历史数据。该设计必须调整，否则切换后端后 enrichment 会悄悄退回 `efinance`，导致语义错乱。

正确改法：

- `fetch_history_for_code` 不再按 `module_name` 直接访问 `efinance`
- 改为通过 backend facade 获取标准化的历史 K 线

建议替换思路：

```text
当前命令结果 -> 抽取 symbol -> backend.fetch_history_for_enrichment(...) -> 标准 K 线 -> enrich_history_frame(...)
```

### 12.2 observation 改造目标

`observation.py` 已经具备一定字段别名兼容能力，这层可以尽量复用。

建议策略：

- shared 命令统一走标准化字段
- `observation.py` 逐步从“兼容很多原始字段名”转向“优先消费标准字段”
- raw 模式下仍可保留原始返回

### 12.3 兼容策略

短期：

- 保留现有字段别名逻辑

中期：

- 将字段别名逻辑移入标准化层

长期：

- observation 尽量只依赖标准结构，不再直接理解上游字段差异

## 13. 测试与验证方案

### 13.1 验证目标

必须验证以下内容：

- 现有 `efinance` 默认行为未回归
- shared 命令在 `akshare` 后端下可用
- `efinance-only` 命令在 `akshare` 下明确失败
- `akshare` 超集命令可正常进入执行链
- observation 与 enrichment 在双后端下保持基本一致的结构约定

### 13.2 测试分层

建议新增三类测试：

- 单元测试
  测后端 adapter 的参数翻译与结果标准化。
- 合同测试
  对同一个 capability，验证两个 backend 的输出都满足标准结构契约。
- CLI 回归测试
  验证 `--backend` 参数、错误提示、帮助文本和 shared 命令行为。

### 13.3 合同测试示例

例如对 `stock_price_history`：

- 输出必须是 `DataFrame`
- 必须存在 `日期`、`收盘`
- 若存在价格列，则必须可转数值
- 日期列必须单调可排序

### 13.4 watch 模式验证

必须单独验证：

- shared 命令在 `--watch` 下双后端都能跑通
- 不支持 watch 的命令仍保持禁止
- watch 刷新不会因为后端切换绕过能力检查

## 14. 分阶段实施计划

### 阶段 A：建立后端抽象骨架

目标：

- 不改变用户可见命令
- 先把结构搭起来

任务：

- 新增 `backends/base.py`
- 新增 `backends/factory.py`
- 新增 `EfinanceBackend`
- 新增 `CommandDefinition`
- 为 executor 增加 backend 解析能力

验证：

- 原有测试在默认 `efinance` 下通过
- 不新增 `akshare` 行为，只确认骨架不破坏当前路径

### 阶段 B：把 shared 命令迁移到能力接口

目标：

- 先迁移少量共享命令，不追求全面

建议首批迁移：

- `stock price history`
- `stock price live`
- `stock profile`
- `fund nav history`
- `futures price history`

任务：

- 将这些命令从“直绑 efinance 函数”改为“走 backend capability”
- 引入 `standardization.py`

验证：

- 共享命令默认 `efinance` 行为不回归
- `--backend akshare` 下可成功获取并渲染结果

### 阶段 C：迁移 enrichment / observation

目标：

- 让 shared 命令在 `akshare` 下也能走完整增强链

任务：

- 改造 `enrichment/service.py`
- 让 observation 优先消费标准结构

验证：

- shared 命令在双后端下都能输出 observation
- 基础技术指标能够稳定计算

### 阶段 D：声明并保护 provider-specific 命令

目标：

- 清晰区分哪些命令不支持 `akshare`

任务：

- 在命令定义中加入 `supported_backends`
- 在帮助文本与运行时错误中明确提示

验证：

- `efinance-only` 命令在 `akshare` 下失败信息清晰

### 阶段 E：新增 AKShare 超集命令

目标：

- 释放 `akshare` 的独有价值

建议顺序：

1. `index`
2. `macro`
3. `industry`
4. `option`

验证：

- 新命令不破坏旧命令路径
- 结构上与 shared 命令复用同一执行骨架

## 15. 风险分析

### 15.1 语义风险

风险：

- 同名命令在双后端下结果相似但并不完全等价

应对：

- 文档明确“共享命令保证近似业务语义，不保证底层源完全一致”
- raw 模式允许用户查看原始字段

### 15.2 结果标准化风险

风险：

- 标准化层过度裁剪字段，导致信息丢失

应对：

- observation / enrichment 只依赖核心字段
- raw 模式保留原始结果

### 15.3 测试污染风险

风险：

- 现有测试大量 patch `efinance`，迁移后容易失效

应对：

- 新测试优先 patch backend facade，而不是 patch 上游包
- 保留少量 `efinance` 直连测试作为回归保护

### 15.4 复杂度失控风险

风险：

- 适配多后端后，结构变得过于抽象

应对：

- 只为真实共享命令引入能力接口
- 不支持的命令显式标记为 provider-specific
- 不强迫所有命令走同一种抽象深度

## 16. 实施建议的最小切片

如果只做第一批最小闭环，我建议选择以下切片：

1. 新增 `--backend`
2. 新增 `MarketBackend` 协议
3. 实现 `EfinanceBackend`
4. 实现 `AkshareBackend` 的以下能力：
   - `stock_price_history`
   - `stock_price_live`
   - `stock_profile`
5. 让以下命令先改走 backend facade：
   - `stock price history`
   - `stock price live`
   - `stock profile`
6. 为这些命令补 contract test

这是最小但完整的验证闭环，因为它同时覆盖：

- 历史 K 线
- 实时列表
- 单标的资料
- 双后端能力差异
- 标准化层

## 17. 最终建议

建议采用以下总体策略：

- 第一原则：不要让 `akshare` 假扮成 `efinance`
- 第二原则：让 CLI 的稳定对象从“上游函数”切换为“命令语义”
- 第三原则：共享命令做 adapter，后端特性做显式边界
- 第四原则：新增 `akshare` 超集命令，而不是把所有差异都塞进旧命令

一句话总结：

> 本项目适合做“语义稳定、后端可切换、能力分层清晰”的双后端 CLI，不适合做“把 AKShare 伪装成另一个 efinance”的兼容壳。

## 18. 建议后续实施顺序

建议后续按以下顺序推进开发：

1. 先提交“后端抽象骨架 + 默认行为不变”
2. 再提交“首批 shared 命令适配”
3. 再提交“enrichment / observation 后端解耦”
4. 再提交“provider-specific 保护与帮助文本”
5. 最后提交“AKShare 超集命令”

这样每一步都可验证、可回退、可审查，符合当前项目的零信任与分步收敛原则。
