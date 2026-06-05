## Why

上一轮全面的参数级交叉对比已确认 CLI 命令树与 JSON 目录完全一致，但测试覆盖分析揭示出显著的盲区：契约标准化层零直接测试、约 70% 的技术指标算子未独立验证、多个 provider handler 无直接覆盖、且完全没有真实网络集成测试。这些盲区意味着未来对核心模块的任何重构或上游依赖升级都缺乏安全网，回归风险无法在 CI 中被自动发现。

## What Changes

- 新增 contracts.py 的独立单元测试：覆盖 uild_standard_result、
ormalize_contract_mapping、ensure_mapping_has_required_fields、StandardizationError 的核心路径与边界行为
- 新增 indicators/ 子包中被遗漏的 ~20 个指标算子的最小单元测试（每个指标至少验证输出列名与基本类型正确性，关键指标补充手工公式验证）
- 新增 enrichment/indicators.py 的边界测试：空 DataFrame、单行数据、缺失必需列、非 OHLCV 列名等输入的抗崩溃验证
- 新增 equest_schema.py 的独立单元测试：验证 uild_click_options_for_schema 对必填/可选/多值/默认值等字段的正确映射
- 新增 ackends/resolver.py 的独立单元测试：覆盖显式指定、auto、默认回退等后端选择路径
- 新增 enrichment/service.py 的独立单元测试：验证 etch_standard_history_for_request 的调用转发与超时保护
- 扩展 providers.py handler 覆盖：为 AkshareStockPriceLiveHandler、AkshareFundNavHistoryHandler、AkshareStockProfileHandler、AkshareStockPriceHistoryHandler、YfinanceRealtimeHandler、EfinanceGenericHandler 补充最小 mock 测试
- 新增 acade.py 的独立单元测试：覆盖 CommandFacade.invoke 在各后端成功/失败/auto-failover 场景下的行为
- 为 indicators 和 enrichment 模块建立统一的 pytest 参数化 fixture，减少样板代码

## Capabilities

### New Capabilities
- contracts-unit-tests: 为数据契约标准化层（contracts.py）建立完整的独立单元测试，覆盖标准结果构建、映射规范化、必填字段校验、错误路径
- indicators-full-coverage: 为 indicators/ 子包中当前未测的约 20 个技术指标算子补充最小单元测试，每个指标至少验证输出列名与类型正确性
- enrichment-edge-cases: 为 enrichment/indicators.py 的 enrich_history_frame 补充边界输入测试（空 DataFrame、单行、缺列、非标准列名）
- schema-resolver-unit-tests: 为 equest_schema.py 和 ackends/resolver.py 建立独立单元测试，覆盖 schema→Click 选项映射与后端选择逻辑
- provider-handler-gap-coverage: 为 providers.py 中当前未直接测试的 6 个 handler 补充最小 mock 测试
- acade-unit-tests: 为 acade.py 的 CommandFacade.invoke 补充独立单元测试，覆盖各后端成功/失败/auto-failover 场景

### Modified Capabilities
<!-- 本次不修改任何现有 spec 级行为，均为补充测试 -->

## Impact

- **新增文件**: 	ests/test_contracts_unit.py、	ests/test_indicators_full.py、	ests/test_enrichment_edge.py、	ests/test_schema_and_resolver.py、	ests/test_provider_handlers_extended.py、	ests/test_facade_unit.py
- **修改文件**: 	ests/conftest.py（新增共享 pytest fixtures）、	ests/cli_regression_support.py（补充辅助函数，按需）
- **不涉及任何业务逻辑改动**：仅补充测试，不改 efinance_cli/ 下的源代码
- **不新增依赖**：全部使用 pytest + unittest.mock，与现有测试栈一致
