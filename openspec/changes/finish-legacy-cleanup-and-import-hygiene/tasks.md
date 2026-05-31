## 1. Legacy 运行时影子清理

- [x] 1.1 盘点 `commands`、`executor`、`enrichment`、`observation` 中仍然存在的 legacy 命令分类常量、旧回补接口和旧兼容分支。
- [x] 1.2 将 shared 命令相关的 observation / enrichment 分流逻辑改写为 capability、contract 或标准补充接口驱动。
- [x] 1.3 删除仅为旧函数驱动命令模型服务的内部辅助函数、常量、注释和帮助文案。
- [x] 1.4 补充或调整针对 legacy 清理的定向测试，验证 shared / provider-extension 主链不再依赖 legacy 分类。

## 2. Import Hygiene 清理

- [x] 2.1 识别运行时代码与关键测试中的真实无效 import，区分 `__future__`、类型注解、延迟导入等合法例外。
- [x] 2.2 删除确认无效的 import，并做最小配套修正，避免扩散成无关风格整理。
- [x] 2.3 通过编译检查或定向测试验证 import 清理未破坏模块加载和关键路径行为。

## 3. 测试与文档基线收口

- [x] 3.1 更新相关 CLI / observation / retry 回归测试，使其不再断言 legacy registry 或旧命令模型仍存在。
- [x] 3.2 更新与当前运行时模型直接相关的开发文档和架构文档，明确 legacy 仅作为迁移背景。
- [x] 3.3 复查仍然保留的 legacy 提及，区分“历史说明”与“错误现行描述”，删除后者。

## 4. 最终验证与收尾

- [x] 4.1 运行与 legacy 清理和 import 清理直接相关的测试集合，并记录未覆盖风险。
- [x] 4.2 复查工作区，确认本次改动未顺手扩散到无关业务逻辑、依赖或配置。
