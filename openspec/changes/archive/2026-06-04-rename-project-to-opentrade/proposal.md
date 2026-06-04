## Why

当前仓库的项目名、Python 包名、模块文案和 CLI 命令入口仍以 `efinance` / `efinance-cli` / `efinance_cli` 为核心标识，已经与目标产品命名 `Open Trade` 明显不一致。若继续在旧命名上叠加功能，后续发布、文档、导入路径、测试基线和用户命令习惯会持续积累语义债务，因此需要单独推进一次受控的全量命名迁移。

## What Changes

- **BREAKING**：将项目对外名称从 `efinance-cli` / `the-efinance-cli` 全面重命名为 `opentrade` / `Open Trade`。
- **BREAKING**：将 Python 包与模块主路径从 `efinance_cli` 重命名为 `opentrade`，同步调整入口脚本、导入路径、元数据和测试引用。
- **BREAKING**：将 CLI 主命令从 `efinance` 改为 `opentrade`，短命令从 `efi` 改为 `optr`。
- **BREAKING**：彻底移除 `efinance-cli`、`the-efinance-cli`、`efinance_cli`、`efinance` 与 `efi` 的主路径身份，不保留任何兼容入口、兼容包或弃用提示。
- 同步更新 README、项目文档、OpenSpec 变更文档、测试用例和打包配置中的产品标识，保证仓库内外命名一致。

## Capabilities

### New Capabilities
- `project-brand-rename`: 规范项目对外名称、发布元数据、文档标题和产品文案统一迁移到 `opentrade` / `Open Trade`。
- `python-package-rename`: 规范 Python 包目录、模块入口、导入路径和测试引用从 `efinance_cli` 迁移到 `opentrade`。
- `cli-command-rename`: 规范 CLI 主命令和短命令入口迁移到 `opentrade` / `optr`，并要求旧命令彻底移除。

### Modified Capabilities
<!-- 当前仓库未建立对应主线 specs，本次以新增 capability 方式定义 rename 要求。 -->

## Impact

- **受影响代码**：
  - `pyproject.toml`
  - `README.md`
  - `efinance_cli/`（后续迁移为 `opentrade/`）
  - `tests/`
  - `docs/`
  - `openspec/changes/` 中引用现有项目名的文档
- **受影响接口**：
  - CLI 命令入口
  - Python 导入路径
  - PyPI 包名 / 项目元数据
- **受影响系统**：
  - 本地开发与测试命令
  - 发布与安装文档
  - 用户脚本和自动化工具中的旧命令调用（将直接失效并需自行迁移）
