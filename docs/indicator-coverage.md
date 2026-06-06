# Indicator Coverage

This page records the broader indicator surface exposed by `opentrade` when compatible commands enable indicator enrichment.

## Levels

| Level | Typical use | Representative fields |
|---|---|---|
| `basic` | Lightweight trend and momentum review | `ma5`, `ma10`, `ma20`, `ema12`, `ema26`, `macd_dif`, `macd_dea`, `rsi14`, `kdj_k`, `kdj_d`, `boll_upper`, `boll_lower`, `atr14`, `obv` |
| `advanced` | Richer screening, structure review, and money-flow inspection | `supertrend`, `plus_di`, `minus_di`, `adx`, `mfi14`, `pvt`, `cmf20`, `vwap`, `vr`, `psy`, `donchian_upper`, `keltner_upper`, `natr14` |
| `full` | Deep technical review and research-style context building | `ichimoku_cloud`, `parabolic_sar`, `mass_index`, `pivot_points`, `fibonacci_retracement`, `rolling_support_resistance`, `chaikin_oscillator`, `chaikin_volatility`, `ease_of_movement` |

## Major Families

### Moving averages and base transforms

`sma`, `ema`, `rma`, `wma`, `dema`, `tema`, `trima`, `hma`, `zlema`, `highest`, `lowest`, `median_price`, `typical_price`, `true_range`

### Trend and channel indicators

`macd`, `bollinger_bands`, `donchian_channel`, `keltner_channel`, `moving_average_envelope`, `aroon_indicator`, `dmi`, `adx`, `supertrend`, `parabolic_sar`, `ichimoku_cloud`

### Momentum indicators

`momentum`, `roc`, `rsi`, `stochastic_oscillator`, `kdj`, `cci`, `williams_r`, `trix`, `tsi`, `ultimate_oscillator`, `dpo`, `ppo`

### Volume and money-flow indicators

`obv`, `accumulation_distribution`, `chaikin_money_flow`, `chaikin_oscillator`, `mfi`, `vwap`, `force_index`, `ease_of_movement`, `price_volume_trend`, `volume_ratio`

### Volatility indicators

`atr`, `natr`, `historical_volatility`, `chaikin_volatility`, `mass_index`

### Price-structure indicators

`pivot_points`, `fibonacci_retracement`, `rolling_support_resistance`

### Common Chinese-market technical indicators

`bias`, `bbi`, `psy`, `vr`, `mtm`, `dma`, `brar`, `cr`, `emv`, `asi`

## Notes

- The exact fields returned depend on command type, available history depth, and selected `indicator-level`.
- Indicator output provides probabilistic context, not guaranteed trading conclusions.
- `full` is the richest mode, but it is also the heaviest and most dependent on successful history backfill.