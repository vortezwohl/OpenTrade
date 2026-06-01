## 1. 修复 auto 兜底链断裂

- [ ] 1.1 修改 acade.py 的 is_failover_eligible_error 函数：从白名单策略改为黑名单策略，仅排除 click.ClickException、ValueError、TypeError
- [ ] 1.2 更新 	ests/test_facade_unit.py 中 	est_auto_all_candidates_fail 的异常类型以匹配新行为
- [ ] 1.3 新增测试：验证 yfinance 限流异常（YFRateLimitError→RuntimeError）可被正确 failover
- [ ] 1.4 验证：stock price latest --backend auto 能在 yfinance 不可用时自动切换到 efinance

## 2. 修复 Windows GBK 编码崩溃

- [ ] 2.1 修改 executor.py 的 _emit 方法：在 click.echo 前对文本做编码安全检查，不可编码字符替换为 ?
- [ ] 2.2 修改 endering.py 的 ender_value 函数：添加 errors='replace' 参数到编码相关调用
- [ ] 2.3 新增测试：构造含特殊 Unicode 字符的模拟输出，验证不再抛 UnicodeEncodeError
- [ ] 2.4 验证：--output 写入文件时使用用户指定的编码，不做替换

## 3. 修复 --view raw 模式崩溃

- [ ] 3.1 修改 executor.py 的 invoke 方法：当 iew_mode == 'raw' 时跳过 enrich_market_data 和 uild_observation_output
- [ ] 3.2 新增测试：验证 --view raw 模式下不调用增强层，直接返回原始字典
- [ ] 3.3 验证：--view observation 模式不受影响，仍正常走增强和 observation 管线
- [ ] 3.4 验证：stock price history --symbols 000001 --view raw 不再崩溃

## 4. 回归验证

- [ ] 4.1 运行全部现有测试确认无回归：pytest tests/ -v --ignore=tests/test_multi_backend_scaffold.py
- [ ] 4.2 运行真实 API 回归脚本中的关键用例验证修复效果
- [ ] 4.3 更新测试结论文档 docs/20260601-测试结论.html 补充修复后的对比数据
