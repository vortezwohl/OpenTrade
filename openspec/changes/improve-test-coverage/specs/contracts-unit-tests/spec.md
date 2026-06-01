## ADDED Requirements

### Requirement: build_standard_result 构建标准结果
	ests/test_contracts_unit.py SHALL 验证 uild_standard_result 对以下输入场景的正确行为：
- 传入合法 contract mapping 时返回包含 contract_name、data、provider_fields 的标准结果；
- 传入空 DataFrame 时返回空数据列表但结构完整。

#### Scenario: 正常 DataFrame 输入
- **WHEN** 调用 uild_standard_result(contract=HISTORY_BARS_CONTRACT, data=valid_dataframe, contract_name='history-bars')
- **THEN** 返回的 StandardResult.contract_name 等于 'history-bars'
- **AND** StandardResult.data 为非空列表
- **AND** StandardResult.provider_fields 为空字典

#### Scenario: 空 DataFrame 输入
- **WHEN** 调用 uild_standard_result 并传入空 DataFrame
- **THEN** 返回的 StandardResult.data 为空列表
- **AND** 不抛出异常

### Requirement: normalize_contract_mapping 映射规范化
	ests/test_contracts_unit.py SHALL 验证 
ormalize_contract_mapping 的行为：
- 将 DataFrame 行的字典表示中的中文列名映射为英文标准列名；
- 对未在契约中定义的列名保持原样传递。

#### Scenario: 中文列名规范化
- **WHEN** DataFrame 包含 '股票代码'、'股票名称' 等中文列名且契约定义了对应映射
- **THEN** 输出的字典键为 'code'、'name' 等英文标准名

#### Scenario: 未映射列名保持原样
- **WHEN** DataFrame 包含契约未定义的列名
- **THEN** 该列名在输出字典中保持原样

### Requirement: ensure_mapping_has_required_fields 必填字段验证
	ests/test_contracts_unit.py SHALL 验证 ensure_mapping_has_required_fields 的行为：
- 所有必填字段存在时静默通过；
- 缺少必填字段时抛出 StandardizationError 并包含缺失字段名。

#### Scenario: 字段完整
- **WHEN** 字典包含契约定义的全部必填字段
- **THEN** 函数正常返回，不抛出异常

#### Scenario: 字段缺失
- **WHEN** 字典缺少至少一个必填字段
- **THEN** 抛出 StandardizationError，异常消息包含缺失字段名
