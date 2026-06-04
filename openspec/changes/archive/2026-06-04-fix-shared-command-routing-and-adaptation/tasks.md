## 1. Shared Command Truth Source And Normalized Schema

- [x] 1.1 将 shared 命令真相源迁入仓库内可版本化的位置，移除 `opentrade/command_catalog.py` 对外部 `.skill` 运行时目录的依赖
- [x] 1.2 为 multi-backend shared 命令定义 provider-neutral 内部字段名，至少覆盖日期、symbol、quote-id、market、timeframe、adjustment 等核心输入语义
- [x] 1.3 调整 `opentrade/request_schema.py` 的字段元数据与校验逻辑，使 shared market 校验基于字段语义而不是字段字面名 `market`
- [x] 1.4 补充或更新 `tests/test_schema_and_resolver.py`，验证 normalized shared 字段、market 校验和 repo 内命令真相源行为

## 2. Provider Request Adaptation

- [x] 2.1 为 history、realtime、profile、search、resolve 等 shared 命令簇建立显式 provider request adaptation helper，减少 `callback(**request_data)` 直通路径
- [x] 2.2 调整 `opentrade/backends/providers.py`，让 efinance、akshare、yfinance 在 shared 命令下优先消费 normalized request，再翻译为 provider-specific kwargs
- [x] 2.3 收敛 shared `market` 与 provider 原生 `fs` 的边界，shared 命令不再直接以 `fs` 作为内部共享字段
- [x] 2.4 收紧 `stock.profile` 的 shared 语义为单标的，并补充可读错误或兼容适配路径
- [x] 2.5 更新 `tests/test_provider_handlers_extended.py`、`tests/test_multi_backend_scaffold.py` 与相关 facade/provider 测试，验证 provider adaptation 的输入与结果语义

## 3. Request-Aware Auto Routing

- [x] 3.1 将 auto 候选规划从静态 resolver 顺序改为基于 normalized request 的请求感知排序
- [x] 3.2 为 auto 路由补充可观测元数据，至少覆盖 planned candidates、attempted candidates、final backend、fallback 使用情况
- [x] 3.3 确保 watch 模式与普通执行模式共享同一套请求感知 auto 规划逻辑
- [x] 3.4 更新 `tests/test_cli_full_regression.py`、`tests/test_facade_unit.py`、`tests/test_multi_backend_scaffold.py`，移除对旧静态候选顺序的硬编码断言，改为验证语义化路由结果

## 4. Execution-Aware Limiting

- [x] 4.1 为 shared 命令定义 `--limit` 策略元数据，区分显示裁剪、可前移执行减载、adapter 轻量抓取三类行为
- [x] 4.2 调整 `opentrade/rendering.py` 与执行链元数据输出，使 display-only limit 与 execution-aware limit 在 raw / regression 输出中可区分
- [x] 4.3 优先为重路径命令簇建立最小可行的执行减载策略，至少覆盖 `market price live` 及一类 quote/futures 重路径命令
- [x] 4.4 补充 `tests/test_rendering_and_metrics_regression.py` 与相关命令测试，验证 `--limit` 的显示层与执行层语义不会再被混淆

## 5. Regression Classification And Test Realignment

- [x] 5.1 重构 `scripts/run_third_full_regression.py` 与 `scripts/run_incremental_full_regression.py` 的失败分类逻辑，至少区分 `sample_mismatch`、`adapter_gap`、`product_defect`、`upstream_instability`
- [x] 5.2 调整真实回归报告结构，保留路由、分类、limit 策略和 final backend 等证据字段，避免把样本错配直接统计成产品缺陷
- [x] 5.3 系统性更新受影响测试集，使测试验证 normalized request、provider adaptation、request-aware auto routing 和 failure classification，而不是固化旧内部字段或旧候选顺序
- [x] 5.4 运行最小自动化回归集，至少覆盖 schema/resolver、provider handlers、facade、rendering、CLI regression、multi-backend scaffold
- [x] 5.5 运行一轮最小真实命令回归子集，验证 A 股 / 美股 / auto / 重路径命令在新分类和新路由下的结果可解释性
