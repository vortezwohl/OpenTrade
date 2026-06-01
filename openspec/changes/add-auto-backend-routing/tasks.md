## 0. 当前基线确认

- [x] 0.1 单 backend 命令已完成 `provider-extension` 重分类，见 `archive/2026-05-31-reclassify-single-backend-commands`。
- [x] 0.2 当前共享命令默认 backend 仍为固定 `efinance`，`CommandFacade` / `CommandExecutor` 仍按单 backend 调用执行。
- [x] 0.3 `yfinance` 已完成正式注册，`auto` 后续实现不应再把它当作 optional provider 特殊跳过分支。

## 1. backend 解析模型调整

- [x] 1.1 在 `efinance_cli/models.py` 中为 backend 选择结果增加 `auto` 语义及候选链元数据。
- [x] 1.2 重构 `efinance_cli/backends/resolver.py`，把共享命令默认 backend 从固定 concrete provider 改为 `auto`。
- [x] 1.3 在 resolver 中实现 `akshare -> yfinance -> efinance` 的 auto 候选链构造与支持矩阵过滤。
- [x] 1.4 为 provider-extension 命令实现 `auto` 自动适配所属 provider 的解析规则。

## 2. 统一执行与 failover 主链

- [x] 2.1 重构 `efinance_cli/facade.py`，支持按 auto 候选链依次尝试 concrete backend。
- [x] 2.2 定义可降级错误与立即失败错误的分类规则，并接入 auto 执行主链。
- [x] 2.3 为 auto 全链路失败实现 backend 级错误聚合输出。
- [x] 2.4 在 `efinance_cli/executor.py` 中回写最终命中的 concrete backend，保证后续链路可见。

## 3. enrichment、watch 与 provider-extension 一致性

- [x] 3.1 调整 `efinance_cli/enrichment/service.py`，让历史回补继续使用 auto 最终命中的 concrete backend。
- [x] 3.2 验证 `watch` 模式下每轮刷新都会重新按相同 auto 规则执行。
- [x] 3.3 校正 provider-extension 在未指定 backend 与 `--backend auto` 下的自动适配行为。

## 4. 测试与文档

- [x] 4.1 更新 `tests/test_multi_backend_scaffold.py`，覆盖默认 auto、候选链顺序、provider-extension auto 适配和最终命中 backend。
- [x] 4.2 更新 CLI 回归测试，覆盖 auto 全链路失败、错误聚合和错误 concrete backend 的报错。
- [x] 4.3 更新架构说明与 CLI 使用文档，明确默认 backend 已改为 auto，以及共享命令与 provider-extension 在 auto 下的不同语义。
- [x] 4.4 复查 `add-yfinance-backend-support`，确认 `yfinance` 现已正式注册；后续 auto 候选链应直接按通用“支持矩阵 + provider 可用性”规则处理，而不是继续保留针对 `yfinance` 的特殊跳过分支。
