## ADDED Requirements

### Requirement: 项目对外品牌标识统一为 opentrade
仓库的主发布名称、README 标题、主要说明文档和当前活跃变更文案 SHALL 使用 `opentrade` 作为项目主标识，并在需要展示全称时使用 `Open Trade`。系统 MUST 不再把 `efinance-cli` 或 `the-efinance-cli` 作为当前主产品名继续对外呈现。

#### Scenario: README 和打包元数据展示新项目名
- **WHEN** 维护者查看 `README.md` 与 `pyproject.toml`
- **THEN** 项目标题、描述和主安装说明使用 `opentrade` / `Open Trade`
- **AND** 不再把 `efinance-cli` 作为当前项目主名称

#### Scenario: 当前活跃文档不再混用旧品牌名
- **WHEN** 维护者查看本次变更涉及的主文档与活跃 OpenSpec 工件
- **THEN** 文档 SHALL 以 `opentrade` / `Open Trade` 作为主名称
- **AND** 若提及 `efinance-cli`，仅用于迁移说明或兼容提示
