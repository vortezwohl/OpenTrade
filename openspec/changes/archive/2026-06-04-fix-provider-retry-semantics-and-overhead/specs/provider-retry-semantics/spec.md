## ADDED Requirements

### Requirement: Provider 级统一重试在耗尽后必须保留最终 provider 异常语义
系统 MUST 在 provider 级统一重试耗尽后，对外抛出最后一次真实 provider 异常，而 SHALL NOT 把无上下文的通用重试异常作为最终失败结果返回给 facade、tests 或调用方。

#### Scenario: yfinance 限流重试耗尽后仍暴露 Yahoo 语义
- **WHEN** `yfinance` 在 provider 执行入口内连续触发已翻译的限流异常并最终耗尽重试
- **THEN** 系统 MUST 以保留 Yahoo 限流语义的 provider 异常结束，而 SHALL NOT 以通用 `MaxRetriesReachedError` 作为最终对外异常

### Requirement: Provider guardrail 异常必须直接透传且不进入网络重试
系统 MUST 允许 provider 标记参数错误、invalid period 等 guardrail 异常为直接透传异常；这些异常 SHALL NOT 被统一网络重试吸收或改写。

#### Scenario: yfinance invalid period 直接失败
- **WHEN** `yfinance` 在 handler 执行中抛出 provider 已识别的 invalid period / `ValueError`
- **THEN** provider 执行入口 MUST 直接把该异常返回上层，而 SHALL NOT 对其执行自动网络重试

### Requirement: akshare 搜索路径必须让可重试网络异常进入统一 provider 重试
系统 MUST 让 `akshare instrument.search` 中属于 provider retry policy 的瞬时网络异常直接上抛到 provider 统一执行入口，而 SHALL NOT 在 handler 内部先把它们吞掉改写为普通聚合错误。

#### Scenario: 搜索目录源出现瞬时网络失败时进入 provider 重试
- **WHEN** `akshare instrument.search` 的某个目录 loader 抛出属于 provider retry policy 的网络异常
- **THEN** handler MUST 让该异常冒泡到 provider 执行入口，以便统一重试机制先完成当前 backend 内部恢复

### Requirement: akshare 搜索的非网络局部目录失败仍可保留聚合行为
系统 MAY 继续在 `akshare instrument.search` 中收集非 retryable 的局部目录失败，并在仍有有效结果时返回聚合后的标准结果；但这类容错 SHALL NOT 吞掉本应进入统一网络重试的异常。

#### Scenario: 单个目录源返回非网络错误但其他目录源成功
- **WHEN** 某个 `akshare` 搜索目录 loader 发生不属于 provider retry policy 的局部失败，且其他 loader 仍成功返回候选数据
- **THEN** 系统 MAY 返回带 `errors` 元数据的搜索结果，同时保持整次请求不因该局部失败直接终止
