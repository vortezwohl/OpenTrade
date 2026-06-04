## ADDED Requirements

### Requirement: CLI 主命令迁移到 opentrade 和 optr
项目的 CLI 脚本入口 SHALL 将 `opentrade` 作为主命令，将 `optr` 作为短命令。系统 MUST 彻底移除 `efinance` / `efi` 作为可安装或主文档推荐的命令入口。

#### Scenario: 安装后主命令为 opentrade
- **WHEN** 用户按照主安装文档安装项目后执行 `opentrade --help`
- **THEN** CLI 能正常启动并展示当前命令树

#### Scenario: 安装后短命令为 optr
- **WHEN** 用户执行 `optr --help`
- **THEN** CLI 能正常启动并展示与 `opentrade --help` 一致的主帮助信息

#### Scenario: 旧命令不再作为项目入口发布
- **WHEN** 维护者查看打包脚本配置与主安装文档
- **THEN** 项目 SHALL 只发布 `opentrade` 与 `optr`
- **AND** README 或主文档 SHALL 不再把 `efinance` / `efi` 作为有效入口
