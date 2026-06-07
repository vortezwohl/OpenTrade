## 1. API 结构与公共入口

- [ ] 1.1 新增 `opentrade/api/` package，并创建 `__init__.py`、`client.py`、`_runtime.py` 以及按能力域拆分的命名空间模块骨架
- [ ] 1.2 在 `opentrade.__init__` 中显式导出 `OpenTrade`，保持顶层导出清晰且不新增函数式入口
- [ ] 1.3 为新增 `.py` 文件补充中文文件级说明、类/函数 docstring，并检查 UTF-8 without BOM 编码一致性

## 2. 共享命令程序化 API

- [ ] 2.1 在 `opentrade/api/_runtime.py` 中封装共享命令调用桥接，复用命令定义、schema 校验、backend 解析与 `CommandExecutor.invoke`
- [ ] 2.2 在 `OpenTrade` 及其命名空间模块中实现 `search`、`quote`、`stock`、`fund`、`bond`、`futures`、`market`、`resolve` 的 shared command 对应方法
- [ ] 2.3 为程序化 API 方法筛选公开参数，只保留业务参数和结果相关运行时参数，明确排除 `watch` 与终端输出控制参数

## 3. 扩展能力补齐与导出边界

- [ ] 3.1 盘点现有 provider extension 命令，决定哪些需要纳入 `OpenTrade` 首版公开对象式 API，并按既有业务路径补齐
- [ ] 3.2 确保 `opentrade.indicators` 与其子模块导出保持不变，不把指标函数混入顶层 `opentrade` 或 `OpenTrade`
- [ ] 3.3 为 `OpenTrade` 命名空间属性和方法命名做自审，保证其与 CLI 业务语义对齐且利于 IDE 补全

## 4. 验证与文档

- [ ] 4.1 新增程序化 API 单元测试，覆盖 `from opentrade import OpenTrade`、命名空间属性发现、代表性 shared command 调用成功
- [ ] 4.2 新增 API/CLI 对齐测试，验证关键方法复用现有执行链且不暴露 `watch` 入口
- [ ] 4.3 更新 README 或中文文档，补充 `OpenTrade` 的 import 用法、对象式调用示例，以及指标子包导入说明
