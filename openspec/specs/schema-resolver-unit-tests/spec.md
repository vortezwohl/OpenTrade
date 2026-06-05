# schema-resolver-unit-tests Specification

## Purpose
TBD - created by archiving change improve-test-coverage. Update Purpose after archive.
## Requirements
### Requirement: build_click_options_for_schema 参数映射正确性
	ests/test_schema_and_resolver.py SHALL 验证 build_click_options_for_schema 对 RequestSchema 中各字段类型的正确 Click 选项映射。

#### Scenario: 必填字符串字段
- **WHEN** schema 包含一个 
equired=True、annotation=str 的字段
- **THEN** 生成的 Click Option 的 
equired 属性为 True
- **AND** 生成的 Option 的 CLI 名称为 --<cli_name>

#### Scenario: 可选整数字段带默认值
- **WHEN** schema 包含一个 
equired=False、annotation=int、default=5 的字段
- **THEN** 生成的 Click Option 的 default 为 5
- **AND** 生成的 Option 的 
equired 为 False

#### Scenario: Bool 字段生成 flag 选项
- **WHEN** schema 包含 annotation=bool 的字段
- **THEN** 生成的 Click Option 为 is_flag=True
- **AND** 同时生成 --<name> 和 --no-<name> 两个选项

#### Scenario: Choice 字段生成受限选项
- **WHEN** schema 包含 annotation=Choice 且 choices=('a','b','c') 的字段
- **THEN** 生成的 Click Option 的 type 为 click.Choice
- **AND** 选项参数为 ('a', 'b', 'c')

#### Scenario: multiple 字段生成可重复选项
- **WHEN** schema 包含 multiple=True 的字段
- **THEN** 生成的 Click Option 的 multiple 为 True

### Requirement: resolve_backend_selection 后端选择逻辑
	ests/test_schema_and_resolver.py SHALL 验证 
esolve_backend_selection 在各种输入下的正确路由行为。

#### Scenario: 显式指定有效后端
- **WHEN** 调用 
esolve_backend_selection(definition, 'efinance') 且 definition.supported_backends 包含 efinance
- **THEN** 返回的 BackendSelection.resolved 为 BackendName.EFINANCE
- **AND** source 为 'explicit'

#### Scenario: 显式指定不支持的后端
- **WHEN** 调用 
esolve_backend_selection(definition, 'yfinance') 但 definition.supported_backends 不包含 yfinance
- **THEN** 抛出 ClickException，提示后端不支持

#### Scenario: auto 模式生成候选链
- **WHEN** 调用 
esolve_backend_selection(definition, None) 或 
esolve_backend_selection(definition, 'auto')
- **THEN** 返回的 BackendSelection.resolved 为 BackendName.AUTO
- **AND** candidate_chain 按优先级排列（akshare → yfinance → efinance）
- **AND** source 为 'default'

