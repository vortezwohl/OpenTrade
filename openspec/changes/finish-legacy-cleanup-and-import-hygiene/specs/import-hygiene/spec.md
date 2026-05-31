## ADDED Requirements

### Requirement: 系统必须删除真实无效 import

系统 MUST 删除重构后不再使用、且不承担语义作用的 import，保持文件依赖边界与真实实现一致。

#### Scenario: 普通未引用 import 被删除

- **WHEN** 某个文件中的普通 import 在运行时代码、类型注解、条件分支和函数体内均未被使用
- **THEN** 系统 MUST 删除该 import

#### Scenario: 删除无效 import 后仍能通过基本验证

- **WHEN** 系统删除真实无效 import
- **THEN** 相关文件 MUST 通过编译检查或定向测试验证
- **AND** SHALL NOT 因误删 import 破坏模块加载或关键路径行为

### Requirement: import 清理不得误伤语义性或延迟导入

系统 SHALL NOT 因机械式 unused 检查误删 `__future__`、类型注解依赖、条件导入或延迟导入。

#### Scenario: `__future__` 导入不被误判为无效 import

- **WHEN** 文件使用 `from __future__ import annotations` 或其他语义性 `__future__` 导入
- **THEN** 系统 SHALL 保留该导入，除非明确证明其语义已不再需要

#### Scenario: 函数体内延迟导入按真实使用判断

- **WHEN** 某个 import 出现在函数体内或条件分支内
- **THEN** 系统 MUST 根据真实调用点判断其是否有效
- **AND** SHALL NOT 仅因文件顶层未引用就将其删除

### Requirement: import 清理必须保持最小边界

系统 MUST 把 import hygiene 限定在“删除真实无效 import”和“必要时修正最小相关引用”这一边界内，而 SHALL NOT 借机做无关的风格整理、批量重排或模块重构。

#### Scenario: import 清理不扩散成风格运动

- **WHEN** 系统执行某个文件的 import 清理
- **THEN** 修改 MUST 以删除无效 import 为主
- **AND** SHALL NOT 顺手进行与当前目标无关的大规模导入排序、重命名或结构调整
