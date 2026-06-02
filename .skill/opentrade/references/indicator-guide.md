# 指标参考

## 1. 先明确默认值

### CLI 程序真实默认值

当前程序真实默认值是：

```bash
--indicator-level advanced
```

### skill 面向 agent 的推荐值

这个 skill 面向 agent 的推荐值仍然是：

```bash
--indicator-level full
```

理由：

- `full` 更适合一次性拿到更完整的趋势、波动、量价和关键位上下文
- 对 agent 做解释、总结、比较更友好

但必须同时提醒：

- `full` 不是程序真实默认值
- `full` 更重、更慢、更依赖历史回补

## 2. 什么情况下优先 full

适合优先 `full` 的场景：

- 用户要完整技术面解释
- 用户要看支撑阻力、趋势强弱、波动扩张
- 用户要对比多个 observation section
- 用户要让 agent 继续基于结果做二次推理

## 3. 什么情况下降到 advanced 或 basic

优先降级的场景：

- 高频 watch
- 大批量实时列表扫描
- 用户只要轻量字段
- 上游历史回补不稳定
- 用户只做结构化导出，不做指标解释

## 4. 等级理解

### basic

适合快速看基础趋势和动量：

- MA / EMA
- MACD
- RSI
- KDJ
- BOLL
- ATR
- OBV
- volume ratio

### advanced

适合看更完整的趋势与量价关系：

- ROC
- BIAS
- BBI
- PPO
- TRIX
- TSI
- CCI
- Williams %R
- ADX / DI
- Donchian
- Keltner
- NATR
- SuperTrend
- MFI
- PVT
- CMF
- Force Index
- VWAP
- VR
- PSY

### full

适合做最完整的 observation 解读：

- Ichimoku
- Parabolic SAR
- Mass Index
- Pivot Points
- Fibonacci Retracement
- rolling support / resistance
- ADL
- Chaikin Oscillator
- Chaikin Volatility
- EMV

## 5. 对 agent 最常用的解释框架

解释任意指标时，至少覆盖这 4 点：

1. 这个指标看什么
2. 它怎么辅助判断
3. 常见阈值或比较方式
4. 最容易误导的场景

## 6. full 最常提供的额外价值

### 趋势结构

典型指标：

- Ichimoku
- SuperTrend
- Parabolic SAR

常回答的问题：

- 当前偏多还是偏空
- 趋势有没有延续迹象
- 趋势拐点是否开始出现

### 波动与突破

典型指标：

- ATR / NATR
- Donchian
- Keltner
- BOLL
- Chaikin Volatility

常回答的问题：

- 波动是否在放大
- 区间是否在收缩
- 是否存在突破环境

### 量价与资金

典型指标：

- OBV
- MFI
- CMF
- ADL
- PVT
- Force Index
- VWAP

常回答的问题：

- 上涨是否有量能配合
- 资金更偏净流入还是净流出
- 当前价格相对平均成交成本处在何处

### 关键位

典型指标：

- Pivot
- Fibonacci
- support / resistance

常回答的问题：

- 回撤可能看到哪
- 最近区间边界在哪里
- 哪些位置更适合继续观察

## 7. 解释时必须提醒的风险

- observation 里的很多指标来自历史回补增强，不是上游实时接口原生字段
- `full` 结果更依赖历史数据完整性
- 单次事件信号不应直接等同于交易建议
- 多指标同向时只能算“支持性证据变强”，不能算“确定性结论”

## 8. 推荐说法

- “程序真实默认值是 `advanced`，但这个 skill 面向 agent 通常推荐 `full`，因为更适合做完整 observation 解读。”
- “如果你更在意速度、稳定性或 watch 频率，可以把 `full` 降到 `advanced` 或 `basic`。”
- “这些指标很多来自历史回补增强层，不是原始实时接口直接返回的字段。”
