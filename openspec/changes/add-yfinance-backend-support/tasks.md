## 0. 当前基线确认

- [x] 0.1 单 backend 命令重分类已归档完成，后续仅由 `yfinance` 支持的命令必须作为 `provider-extension` 建模。
- [x] 0.2 当前 `yfinance` 仍仅存在于 `BackendName` 与 optional provider 占位中，运行时正式注册表尚未接入。

## 1. Provider 接入骨架

- [x] 1.1 在 `efinance_cli/backends/factory.py` 中把 `yfinance` 从 optional provider 升级为正式注册 provider。
- [x] 1.2 在 `efinance_cli/backends/providers.py` 中新增 `yfinance` provider 构建函数与基础 handler 注册表。
- [x] 1.3 为 `yfinance` 增加依赖导入探测与不可用错误路径，避免静默回退到其他 backend。
- [x] 1.4 更新 backend 解析与帮助展示，使 `--backend yfinance` 对支持命令可见且可执行。

## 2. 共享命令支持

- [x] 2.1 为 `instrument.search` 实现 `yfinance.Search` handler，并完成 `search-results` 标准化。
- [x] 2.2 为 `stock.price.history` 与 `quote.price.history` 实现 `Ticker.history()` handler，并完成 `history-bars` 标准化。
- [x] 2.3 为 `quote.price.latest` 以及条件支持的 `stock.price.latest` / `snapshot` 设计 `FastInfo` 优先的快照标准化方案。
- [x] 2.4 为 `stock.profile` 与 `quote.profile` 实现 `Quote.info` / `history_metadata` 组合标准化。
- [x] 2.5 为 `fund.nav.history` 与 `fund.profile` 实现基金历史和 `FundsData` 标准化。
- [x] 2.6 更新共享命令支持矩阵与 provider `supports()` 测试，明确 `yfinance` 支持和不支持的命令面。

## 3. Yahoo 专属扩展能力

- [x] 3.1 设计首批 `yfinance` provider-extension 命令组与 CLI 路径，并确保所有单 backend 命令都按 provider-extension 建模。
- [x] 3.2 至少接入一组高价值 Yahoo 专属能力，例如新闻、期权链或基金持仓画像。
- [x] 3.3 为扩展命令补充标准化输出、帮助说明与错误 backend 约束测试。

## 4. 运行时防护与观察链兼容

- [x] 4.1 为 `YFRateLimitError` 和 Yahoo 侧关键异常增加显式错误收束与用户可读提示。
- [x] 4.2 为 `yfinance` 字段缺失场景补充核心契约保底与 `provider_fields` 保留策略。
- [x] 4.3 调整 enrichment / observation / rendering，使 `yfinance` 标准结果不依赖其他 backend 回补即可稳定渲染。
- [x] 4.4 为 `yfinance` 的 market / symbol 语义差异补充文档与帮助提示。

## 5. 验证与文档

- [x] 5.1 新增 `yfinance` provider 单元测试，覆盖 provider 注册、handler 路由、支持矩阵和标准化失败路径。
- [x] 5.2 新增共享 capability 合同测试，验证 `yfinance` 输出满足搜索、历史、快照与资料面核心契约。
- [x] 5.3 增加可选的 live smoke 验证说明，明确 Yahoo 限流导致的非稳定测试边界。
- [x] 5.4 更新 README / 架构说明 / CLI 文档，说明 `yfinance` 的支持范围、扩展命令和运行时限制。
- [x] 5.5 复查 `add-auto-backend-routing`，确保 `yfinance` 正式注册后能被未来 auto 候选链识别，而不是继续停留在 optional provider 跳过分支。
