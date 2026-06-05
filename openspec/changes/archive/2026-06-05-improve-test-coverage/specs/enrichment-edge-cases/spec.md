## ADDED Requirements

### Requirement: 空 DataFrame 输入不崩溃
	ests/test_enrichment_edge.py SHALL 验证 enrich_history_frame 在接收到空 DataFrame 时优雅处理，不抛出未捕获异常。

#### Scenario: 空 DataFrame 输入
- **WHEN** 调用 enrich_history_frame(empty_dataframe, 'basic')
- **THEN** 不抛出异常
- **AND** 返回一个 DataFrame

### Requirement: 单行数据输入不崩溃
	ests/test_enrichment_edge.py SHALL 验证 enrich_history_frame 在接收到仅有一行数据的 DataFrame 时正常处理。

#### Scenario: 单行 DataFrame 输入
- **WHEN** 调用 enrich_history_frame(single_row_dataframe, 'full')
- **THEN** 不抛出异常
- **AND** 返回的 DataFrame 仍包含基础列

### Requirement: 缺失必需列时合理降级
	ests/test_enrichment_edge.py SHALL 验证 enrich_history_frame 在输入 DataFrame 缺少 OHLCV 中的某些列时的行为。

#### Scenario: 缺少 '成交量' 列
- **WHEN** 调用 enrich_history_frame 并传入不含 '成交量' 列的 DataFrame
- **THEN** 不抛出异常
- **AND** 依赖于成交量的指标列（如 OBV、MFI）不存在于输出中

#### Scenario: 仅含 '收盘' 列
- **WHEN** 调用 enrich_history_frame 并传入仅含 '收盘' 和 '日期' 的 DataFrame
- **THEN** 基于收盘价的指标（MA、EMA、RSI）正常计算
- **AND** 依赖 OHLC 的指标（ATR、KDJ、Bollinger）不存在

### Requirement: 非标准列名输入被兼容
	ests/test_enrichment_edge.py SHALL 验证 enrich_history_frame 在输入 DataFrame 使用英文列名（如 'open'/'close' 而非 '开盘'/'收盘'）时的行为。

#### Scenario: 英文 OHLCV 列名
- **WHEN** 传入含 'open'、'high'、'low'、'close'、'volume' 列的 DataFrame
- **THEN** 行为与中文列名输入一致
