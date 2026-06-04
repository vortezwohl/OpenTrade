## ADDED Requirements

### Requirement: Python 包主路径迁移到 opentrade
源码主包目录、模块入口和测试导入路径 SHALL 以 `opentrade` 作为主 Python 包名。仓库 MUST 将 `opentrade` 作为唯一的主实现路径，并彻底移除 `efinance_cli` 作为可导入主路径的身份。

#### Scenario: 主实现包使用 opentrade 目录
- **WHEN** 维护者查看源码根包目录和 `tool.setuptools.packages.find` 配置
- **THEN** 主实现目录为 `opentrade`
- **AND** 打包配置包含 `opentrade*` 而不是 `efinance_cli*`

#### Scenario: 测试与入口模块导入新包路径
- **WHEN** 测试、`__main__` 入口或脚本入口导入主包
- **THEN** 导入路径使用 `opentrade`
- **AND** 主路径不再依赖 `efinance_cli`

#### Scenario: 旧包路径不再作为主实现存在
- **WHEN** 维护者查看源码树与测试基线
- **THEN** 主实现与主导入路径 SHALL 只使用 `opentrade`
- **AND** 仓库 SHALL 不再保留 `efinance_cli` 兼容导入层
