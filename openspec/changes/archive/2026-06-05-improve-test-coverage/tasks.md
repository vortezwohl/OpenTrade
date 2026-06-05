## 1. 基础设施准备

- [x] 1.1 扩展 	ests/conftest.py：新增 sample_ohlcv_frame()、sample_empty_dataframe()、sample_single_row_dataframe()、sample_profile_data() 共享 pytest fixture
- [x] 1.2 在 	ests/cli_regression_support.py 中补充辅助函数 make_request_field() 和 make_request_schema()，用于 request_schema 测试中快速构造 RequestField/RequestSchema

## 2. contracts.py 单元测试

- [x] 2.1 创建 	ests/test_contracts_unit.py，编写 ContractsUnitTest 测试类
- [x] 2.2 测试 uild_standard_result：正常 DataFrame、空 DataFrame、contract mapping 缺失字段
- [x] 2.3 测试 normalize_contract_mapping：中文列名→英文列名映射、未定义列名保持原样、多别名优先级、空值跳过 
ormalize_contract_mapping：中文列名→英文列名映射、未定义列名保持原样
- [x] 2.4 测试 ensure_mapping_has_required_fields：字段完整通过、字段缺失抛出 StandardizationError 且消息包含字段名

## 3. indicators 全覆盖

- [x] 3.1 创建 	ests/test_indicators_full.py，编写 IndicatorsFullTest 测试类
- [x] 3.2 列出 indicators/__init__.py 中 __all__ 的所有函数，与各子模块实际公开函数对比，编写断言
- [x] 3.3 测试趋势类指标（adx、supertrend、parabolic_sar、tenkan、kijun）：每个至少验证输出类型与列名
- [x] 3.4 测试动量类指标（rsi、roc、williams_r、cci、bias、bbi）：每个至少验证输出类型与列名
- [x] 3.5 测试成交量类指标（mfi、vr、adl、chaikin_osc、cmf、vwap）：每个至少验证输出类型与列名
- [x] 3.6 测试波动性类指标（atr、bollinger_bands）：验证输出类型与列名
- [x] 3.7 测试均线类指标（ema、sma）：验证输出类型与长度
- [x] 3.8 手工公式验证：ATR、RSI、ADX 三项，使用可手算的小样本数据交叉验证

## 4. enrichment 边界测试

- [x] 4.1 创建 	ests/test_enrichment_edge.py，编写 EnrichmentEdgeTest 测试类
- [x] 4.2 测试空 DataFrame 输入不崩溃
- [x] 4.3 测试单行 DataFrame 输入不崩溃
- [x] 4.4 测试缺失 '成交量' 列时成交量相关指标不存在但其他指标正常
- [x] 4.5 测试仅含 '收盘' 和 '日期' 列时基于收盘价的指标正常但 OHLC 指标缺失
- [x] 4.6 测试英文列名（'open'/'close'/'high'/'low'/'volume'）与中文列名行为一致

## 5. request_schema 与 resolver 单元测试

- [x] 5.1 创建 	ests/test_schema_and_resolver.py，编写 SchemaAndResolverTest 测试类
- [x] 5.2 测试 build_click_options_for_schema：必填 str 字段 → Click Option required=True 字段 → Click Option required=True
- [x] 5.3 测试 build_click_options_for_schema：可选 int 字段带默认值 → default 正确 字段带默认值 → default 正确
- [x] 5.4 测试 build_click_options_for_schema：bool 字段 → is_flag=True，生成 --name / --no-name 字段 → is_flag=True，生成 --name / --no-name
- [x] 5.5 测试 build_click_options_for_schema：Choice 字段 → choices 元组正确s 元组正确
- [x] 5.6 测试 build_click_options_for_schema：multiple 字段 → multiple=True=True
- [x] 5.7 测试 
esolve_backend_selection：显式指定有效后端、不支持后端、auto 模式候选链

## 6. provider handler 覆盖率补充

- [x] 6.1 创建 	ests/test_provider_handlers_extended.py，编写 ProviderHandlersExtendedTest 测试类
- [x] 6.2 测试 AkshareStockPriceLiveHandler：mock akshare 实时行情返回值，验证标准化结果字段
- [x] 6.3 测试 AkshareFundNavHistoryHandler：mock akshare 净值返回值，验证 contract_name
- [x] 6.4 测试 AkshareStockProfileHandler：mock akshare 资料返回值，验证 contract_name 和数据字段
- [x] 6.5 测试 AkshareStockPriceHistoryHandler：mock akshare K 线返回值，验证 contract_name
- [x] 6.6 测试 YfinanceRealtimeHandler：mock yfinance fast_info，验证标准化后数据字段
- [x] 6.7 测试 EfinanceGenericHandler：以 ond.catalog 为例验证命令绑定正确转发至 efinance.bond

## 7. facade.py 单元测试

- [x] 7.1 创建 	ests/test_facade_unit.py，编写 FacadeUnitTest 测试类
- [x] 7.2 测试单后端成功路径：指定 efinance/yfinance，handler 成功返回
- [x] 7.3 测试单后端失败路径：指定后端抛异常时异常被传播
- [x] 7.4 测试 auto failover：第一候选成功、第一失败第二成功、全部失败抛 AutoBackendExecutionError
- [x] 7.5 测试副作用命令处理：und.reports.download 不走 retry 包装

## 8. 回归验证

- [x] 8.1 运行全部现有测试确认无回归：114 passed (预存的 yfinance 模块缺失致 8 个测试环境性失败，非本次引入)：pytest tests/ -v
- [x] 8.2 运行新增的全部测试确保通过：54 passed + 62 subtests
- [x] 8.3 检查测试覆盖率增量：新增 6 个测试文件，新覆盖 contracts / indicators(全量) / enrichment(边界) / schema+resolver / provider-handler(6个) / facade







