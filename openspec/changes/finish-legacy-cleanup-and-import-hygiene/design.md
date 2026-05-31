## Context

当前仓库已经完成 shared 命令目录、provider 架构、结果契约和统一执行骨架的主体迁移，用户入口层面不再依赖 legacy registry。但从实现内部看，仍存在三类未彻底收口的内容：

1. `enrichment` 和 `observation` 还保留部分旧命令分类常量与 `(module_name, function_name)` 判定。
2. 部分测试、注释和文档仍然把旧模型描述成现行事实，而不是历史背景。
3. 重构期间移动实现后，少量 import 已经失效，降低了文件的真实依赖可见性。

本次设计的核心判断是：这已经不是“继续扩架构”，而是“让现有多后端架构真正成为唯一主模型”。因此所有改动都必须围绕“收口现有模型”展开，而不是再引入新的抽象层。

## Goals / Non-Goals

**Goals:**

- 取缔运行时主链中的 legacy 命令分类影子和旧回补分支。
- 让 `enrichment` / `observation` 明确以 capability、contract 和标准补充接口为稳定对象。
- 建立真正可执行的 import hygiene 规则，并在本仓库内完成一轮清理。
- 同步收口测试与文档，使其不再传播“旧模型仍是运行时事实”的错误信号。

**Non-Goals:**

- 不新增 shared capability 或 provider-specific 命令。
- 不在这轮继续做新一层泛化抽象。
- 不把“整理代码”扩大成无关重构、重命名或风格统一运动。
- 不处理与当前目标无关的依赖升级、配置调整或工具链切换。

## Decisions

### 决策一：用 capability / contract 分类替换残留的旧命令元组分类

当前残留的 legacy 影子主要来自诸如 `HISTORY_COMMANDS`、`LATEST_COMMANDS`、`REALTIME_LIST_COMMANDS`、`OBSERVATION_MULTI_HISTORY_COMMANDS` 这类基于旧模块名和函数名的分类常量。它们在旧模型下有意义，但在现有架构中已经不再是稳定对象。

本次清理将采用以下方向：

- 对 shared 命令，优先使用 `command_key`、`capability_id`、`contract_name` 或标准化结果类型做分类；
- 对 provider-extension 命令，只允许保留和该 provider 扩展命令定义直接相关的运行时判定，不再借道旧 `efinance` 模块名；
- 任何仅为了兼容旧 registry 时代命令名而存在的分类分支都应被删除或收口。

这样做的原因：

- 现在真正稳定的是 capability 和 result contract，而不是历史函数名；
- 保留旧元组分类只会让后续维护者误以为仍存在第二条主路径；
- observation / enrichment 的边界只有建立在统一契约之上，才能继续稳定支撑多后端演进。

### 决策二：标准补充接口是允许存在的唯一“二次取数”入口

历史上 `fetch_history_for_code(module_name, ...)` 这类接口直接把 enrichment 绑回了某个 provider 的旧调用方式。即使命令入口已经迁移，这类回补路径仍会把内部模型偷偷拉回 legacy 时代。

本次 change 的规则是：

- 允许存在“标准补充接口”，例如基于标准请求对象和 capability 的历史回补接口；
- 不允许存在只接受旧 `module_name` / `function_name` 语义、并直接调用特定 provider 旧 API 的内部辅助入口；
- 如确有过渡期适配逻辑，应包裹在标准接口后面，并在实现上以 shared command / provider handler 为中心，而不是以旧函数名为中心。

### 决策三：import hygiene 只清理“真实无效 import”，不追求形式主义

这次 import 清理不做机械式“凡是静态工具说 unused 就删”。需要明确区分三种情况：

- 真正未使用的 import：应删除；
- 语义性 import：例如 `from __future__ import annotations`，虽然不是普通名字引用，但不属于无效 import；
- 延迟导入、类型注解专用导入或条件导入：需要结合实际调用点判断，不能误删。

因此本次清理遵循：

- 优先依赖 AST / lint / 编译检查识别候选项；
- 对每一项候选 import 做最小人工确认；
- 删除后必须通过至少一轮编译或相关测试，确保不是误删。

### 决策四：测试与文档必须同步收口到“新模型已生效”

如果只删运行时代码，不收文档和测试，仓库仍会持续释放错误信号。为避免这种“表面清理”，本次 change 还要求：

- 回归测试不再断言 legacy registry、legacy 模块名分类或旧兼容回调仍然存在；
- 文档不再把旧命令驱动模型描述成当前结构；
- 如果仍保留少量历史背景说明，必须明确写成“历史包袱/迁移背景”，不能与现行设计混写。

## Risks / Trade-offs

- [风险] `observation` / `enrichment` 清理时可能误删仍被 shared capability 间接依赖的边界逻辑。  
  缓解：先把“标准补充接口”和“契约级兼容映射”作为保底边界，再逐步删除旧分类分支。

- [风险] 部分测试仍然通过 provider patch 或旧字段名来构造输入，容易和 legacy 清理范围混淆。  
  缓解：区分“测试 provider 适配实现”与“测试 legacy 命令模型”两类场景，只清理后者。

- [风险] import 清理容易演变成大范围风格整理。  
  缓解：只删真实无效 import，不顺手做导入排序、批量重排或无关格式化。

- [风险] 文档中大量历史术语可能需要更新，但这轮不应演变为全仓库文档重写。  
  缓解：只更新与当前运行时模型、开发入口和测试基线直接相关的文档。

## Migration Plan

1. 盘点运行时主链中仍然存在的 legacy 分类常量、旧回补接口和旧兼容分支。
2. 先将仍然需要的 observation / enrichment 分类判断改写为 capability / contract 驱动。
3. 删除仅服务于旧模型的内部辅助入口、常量、注释和帮助文案。
4. 清理无效 import，并用编译检查与定向测试验证未误删。
5. 同步修正测试与文档，使其和新运行时模型保持一致。

## Open Questions

- 是否需要为“历史背景保留”单独建立一份迁移记录文档，还是只在现有文档中做最小澄清即可？
- 当前仓库是否需要引入正式的 import/lint 工具门禁，还是先通过本次清理和现有测试闭环控制？
