## Why

`add-multi-backend-capability-architecture` 已经把命令入口、共享命令目录、provider 架构和核心 capability 迁移到多后端模型，但仓库里仍然残留两类收尾问题：

- 内部处理层仍保留部分 legacy 语义影子，例如基于 `(module_name, function_name)` 的旧分类常量、旧回补分支和旧兼容判定；
- 一部分 import 在重构后已经失效，继续保留只会增加阅读噪音，并掩盖真正的依赖边界。

这些问题虽然不再主导用户入口，但会持续带来三个工程成本：

- 维护者仍需要在新旧两套语义之间来回切换，难以判断哪些逻辑是真正有效的；
- observation / enrichment 还没有完全以 capability / contract 为稳定对象，后续继续演进时会反复碰到旧分类残影；
- 无效 import 和遗留测试/文档表述会降低代码可读性，放大“看起来还兼容旧模型”的错误预期。

这次 change 的目标不是再开一轮架构设计，而是把前一轮重构真正收尾：明确取缔仍然存在的 legacy 运行时影子，建立 import hygiene 的清理标准，并把文档与测试基线同步到“新架构已经是唯一主路径”的状态。

## What Changes

- 清理运行时内部仍然残留的 legacy 命令分类与旧回补语义，使 `commands`、`executor`、`enrichment`、`observation` 只围绕 shared / provider-extension 命令和标准结果契约工作。
- 移除仅为旧函数驱动模型服务的残余兼容逻辑、常量、分支、注释和帮助文案，不再保留“仍可回退到旧模型”的暗示。
- 重新定义 observation / enrichment 的内部依赖边界，使其优先消费 capability、contract 和标准补充接口，而不是旧的模块名/函数名分类。
- 系统性清理真正无效的 import，并补充最小验证，避免把 `__future__`、类型注解或延迟导入误判为无效 import。
- 同步更新相关测试与文档，确保它们不再把 legacy registry、legacy 命令分类或旧函数名当作真实运行时模型。

## Capabilities

### New Capabilities

- `legacy-runtime-closeout`: 定义如何识别、清理并验证多后端重构后仍然残留的 legacy 运行时影子。
- `import-hygiene`: 定义无效 import 的清理标准、例外边界和验证要求。

### Modified Capabilities

- `backend-agnostic-execution-pipeline`: 补充要求，明确运行时主链不得再依赖旧函数驱动命令分类。
- `unified-result-contracts`: 补充要求，明确 observation / enrichment 的兼容逻辑应下沉到契约或标准化层，而不是散落在旧分类分支中。

## Impact

- 主要影响目录：
  - `efinance_cli/commands.py`
  - `efinance_cli/executor.py`
  - `efinance_cli/enrichment/service.py`
  - `efinance_cli/observation.py`
  - `tests/`
  - `docs/`
- 这是一次重构收尾和代码卫生清理，不引入新的业务 capability，也不新增运行时依赖。
- 这次 change 可能删除更多旧常量、旧分支和无效导入，属于低到中风险的内部收口；风险主要集中在 observation / enrichment 仍覆盖的边界路径。
- 不包含对无关工作区改动的处理，尤其不包含 `pyproject.toml` 之类与本次目标无关的脏改动。
