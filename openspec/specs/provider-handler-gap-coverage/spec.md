# provider-handler-gap-coverage Specification

## Purpose
TBD - created by archiving change improve-test-coverage. Update Purpose after archive.
## Requirements
### Requirement: AkshareStockPriceLiveHandler 数据标准化
	ests/test_provider_handlers_extended.py SHALL 验证 AkshareStockPriceLiveHandler.execute 对 akshare 实时行情返回值的标准化行为。

#### Scenario: 正常行情数据标准化
- **WHEN** mock akshare 返回包含 '代码'、'名称'、'最新价' 列的 DataFrame
- **THEN** handler 返回的 StandardResult.data 中每条记录包含 'code'、'name'、'close' 等标准字段

### Requirement: AkshareFundNavHistoryHandler 净值数据处理
	ests/test_provider_handlers_extended.py SHALL 验证 AkshareFundNavHistoryHandler.execute 对 akshare 基金净值数据的正确转换。

#### Scenario: 基金净值数据标准化
- **WHEN** mock akshare 返回包含基金净值列的 DataFrame
- **THEN** handler 返回的 StandardResult 的 contract_name 为 'fund-nav-history'

### Requirement: AkshareStockProfileHandler 资料处理
	ests/test_provider_handlers_extended.py SHALL 验证 AkshareStockProfileHandler.execute 对 akshare 股票资料数据的正确转换。

#### Scenario: 股票资料数据标准化
- **WHEN** mock akshare 返回包含股票基础信息的 DataFrame
- **THEN** handler 返回的 StandardResult 的 contract_name 为 'profile-info'

### Requirement: AkshareStockPriceHistoryHandler 历史行情处理
	ests/test_provider_handlers_extended.py SHALL 验证 AkshareStockPriceHistoryHandler.execute 对 akshare 历史 K 线数据的正确转换。

#### Scenario: 历史 K 线数据标准化
- **WHEN** mock akshare 返回包含 OHLCV 列的历史 DataFrame
- **THEN** handler 返回的 StandardResult 的 contract_name 为 'history-bars'

### Requirement: YfinanceRealtimeHandler 实时行情处理
	ests/test_provider_handlers_extended.py SHALL 验证 YfinanceRealtimeHandler.execute 对 yfinance 实时行情数据的正确转换。

#### Scenario: yfinance 实时行情标准化
- **WHEN** mock yfinance Ticker.fast_info 返回实时价格信息
- **THEN** handler 返回的 StandardResult.data 包含 'code'、'close' 等字段

### Requirement: EfinanceGenericHandler 通用命令转发
	ests/test_provider_handlers_extended.py SHALL 验证 EfinanceGenericHandler.execute 对命令绑定的正确转发。

#### Scenario: 命令绑定正确调用上游函数
- **WHEN** 以 command_key='bond.catalog' 构造 EfinanceGenericHandler
- **THEN** handler 调用 efinance.bond.get_all_base_info
- **AND** 上传调用经过网络重试包装

