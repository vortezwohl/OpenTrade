## 1. 修复 auto 兜底链断裂

- [x] 1.1 修改 `facade.py` 的 `is_failover_eligible_error` 函数：从白名单策略改为黑名单策略，仅排除 `click.ClickException`、`ValueError`、`TypeError`
- [x] 1.2 更新 `tests/test_facade_unit.py` 中相关 failover 断言以匹配新行为
- [x] 1.3 新增测试：验证 yfinance 限流异常（`YFRateLimitError`）可被正确 failover
- [x] 1.4 验证：`stock price latest --backend auto` 与 `quote price latest --backend auto` 能在 yfinance 不可用时自动切换到 efinance

## 2. 修复 Windows GBK 编码崩溃

- [x] 2.1 修改 `executor.py` 的 `_emit` 方法：在 `click.echo` 前对文本做编码安全检查，不可编码字符替换为 `?`
- [x] 2.2 将编码兜底收敛在 `_emit` 层，不改动 `rendering.py` 的纯渲染职责
- [x] 2.3 新增测试：构造含特殊 Unicode 字符的模拟输出，验证不再抛 `UnicodeEncodeError`
- [x] 2.4 验证：`--output` 写入文件时使用用户指定的编码，不做替换

## 3. 修复 `--view raw` 模式崩溃

- [x] 3.1 修改 `executor.py` 的 `invoke` 方法：当 `view_mode == "raw"` 时跳过 `enrich_market_data` 和 `build_observation_output`
- [x] 3.2 新增测试：验证 `--view raw` 模式下不调用增强层，直接返回原始字典
- [x] 3.3 验证：`--view observation` 模式不受影响，仍正常走增强和 observation 管线
- [x] 3.4 验证：`stock price history --symbols 000001 --view raw` 不再崩溃

## 4. 回归验证

- [x] 4.1 运行定向回归：`62 passed`（`test_facade_unit.py`、`test_executor_regression.py`、`test_cli_full_regression.py`、`test_contracts_unit.py`、`test_enrichment_edge.py`、`test_schema_and_resolver.py`、`test_provider_handlers_extended.py`）
- [x] 4.2 运行真实 API 关键用例验证修复效果：`stock price latest --backend auto`、`quote price latest --backend auto`、`stock price history --view raw`
- [x] 4.3 更新测试结论文档 `docs/20260601-测试结论.html` 补充修复后的对比数据
