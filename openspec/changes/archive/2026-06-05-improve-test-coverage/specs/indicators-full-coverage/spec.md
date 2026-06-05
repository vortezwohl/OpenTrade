## ADDED Requirements

### Requirement: 所有 indicators 模块导出可调用
	ests/test_indicators_full.py SHALL 验证 efinance_cli.indicators 子包中每个公开的指标函数均可被正常导入和调用，接受标准 Series/DataFrame 输入后返回预期类型的结果。

#### Scenario: 趋势类指标可调用
- **WHEN** 调用 indicators.adx(high, low, close)、indicators.supertrend(high, low, close)、indicators.parabolic_sar(high, low) 等趋势类指标
- **THEN** 每个函数返回 DataFrame，包含预期的标准列名（如 adx 包含 'adx'/'plus_di'/'minus_di'）

#### Scenario: 动量类指标可调用
- **WHEN** 调用 indicators.rsi(close)、indicators.roc(close)、indicators.williams_r(high, low, close)、indicators.cci(high, low, close) 等动量类指标
- **THEN** 每个函数返回 Series 或 DataFrame，包含预期列名

#### Scenario: 成交量类指标可调用
- **WHEN** 调用 indicators.mfi(high, low, close, volume)、indicators.vr(close, volume)、indicators.adl(high, low, close, volume)、indicators.chaikin_osc(high, low, close, volume) 等成交量类指标
- **THEN** 每个函数返回预期类型（Series 或 DataFrame），包含预期列名

#### Scenario: 波动性类指标可调用
- **WHEN** 调用 indicators.atr(high, low, close) 等波动性指标
- **THEN** 返回 Series，长度与输入一致

#### Scenario: 均线类指标可调用
- **WHEN** 调用 indicators.ema(close)、indicators.sma(close) 等均线类指标
- **THEN** 返回 Series，长度与输入一致

### Requirement: 关键指标手工公式验证
	ests/test_indicators_full.py SHALL 对高金融意义的指标进行手工公式验证，确保计算结果与公开公式一致。

#### Scenario: ATR 手工公式验证
- **WHEN** 使用已知 OHLC 样本数据计算 ATR(14)
- **THEN** 结果与按 TR = max(H-L, |H-C_prev|, |L-C_prev|) 公式手动计算的值一致

#### Scenario: RSI 手工公式验证
- **WHEN** 使用已知收盘价序列计算 RSI(14)
- **THEN** 结果处于 0-100 范围且趋势方向与价格走势一致

#### Scenario: ADX 手工公式验证
- **WHEN** 使用已知 OHLC 样本数据计算 ADX(14)
- **THEN** 输出包含 'adx'、'plus_di'、'minus_di' 三列
- **AND** ADX 值处于 0-100 范围

### Requirement: 指标导出列表完整性
	ests/test_indicators_full.py SHALL 验证 efinance_cli.indicators 的 __all__ 导出列表与子包内实际公开函数一致。

#### Scenario: 导出列表无遗漏
- **WHEN** 检查 indicators.__all__ 与子包各模块的公开函数名
- **THEN** __all__ 包含所有在 	rend.py、momentum.py、olume.py、olatility.py、price.py、chinese.py 中定义的公开指标函数
