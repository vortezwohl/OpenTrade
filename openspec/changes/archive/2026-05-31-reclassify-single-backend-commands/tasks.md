## 1. 命令分类规则收紧

- [x] 1.1 重构 `efinance_cli/command_catalog.py` 的分类生成规则，使 `shared` 只保留当前真正多 backend 的命令。
- [x] 1.2 盘点并列出当前所有仅单 backend 支持的命令，作为迁移到 provider-extension 的基线清单。
- [x] 1.3 为命令分类增加守护断言，确保新增单 backend 命令不会再误入 shared catalog。

## 2. provider-extension 迁移

- [x] 2.1 把当前单 backend 的 `efinance` 资产域与 utility 命令迁入对应 provider 的 `extension_commands`。
- [x] 2.2 保持迁移命令的原有业务语义 CLI 路径、capability 和 request schema 绑定不变。
- [x] 2.3 校正 provider 归属、帮助文本和支持矩阵展示，使迁移命令能被明确识别为 provider-extension。

## 3. 运行时与执行主链校正

- [x] 3.1 调整 backend 解析逻辑，确保重分类后的单 backend 命令通过 provider-extension 默认路由工作。
- [x] 3.2 验证迁移命令继续复用统一执行骨架、watch 模式和标准化输出链路。
- [x] 3.3 检查并修正命令装配逻辑，避免因内部重分类导致业务路径丢失或命令冲突。

## 4. 测试与文档

- [x] 4.1 更新 `tests/test_multi_backend_scaffold.py`，固化“shared 只允许多 backend、单 backend 必须是 provider-extension”的断言。
- [x] 4.2 更新 CLI 回归测试，覆盖迁移命令的装配、默认 backend 路由与错误 backend 报错。
- [x] 4.3 更新架构说明与 CLI 使用文档，明确新的 shared / provider-extension 边界。
- [x] 4.4 复查 `add-yfinance-backend-support` 等后续 change，确保其实现将遵循新的命令分类规则。
