## 1. 契约与标识语义收敛

- [x] 1.1 统一 shared `symbol`、`symbols` 与 provider-native identifier 的边界，收敛请求归一化后的唯一字段来源
- [x] 1.2 修复 `quote.*` 主路径仍读取 `quote_id`、`quote_ids` 旧字段名的问题，确保 planner、facade、adapter 只消费 normalized contract
- [x] 1.3 按真实 provider 能力更新 capability matrix 与 compatibility guardrails，明确单标的、多标的与市场语义限制

## 2. Provider Adapter 修复

- [x] 2.1 将 `efinance` 的 `quote.price.latest` 接入 `symbol -> quote_id` 显式翻译链路，禁止错误 passthrough
- [x] 2.2 将 `efinance` 的 `quote.profile` 接入 `symbol -> quote_id` 显式翻译链路，并在无法翻译时抛出可读 contract error
- [x] 2.3 将 `yfinance` 的 A 股六码到 Yahoo ticker 翻译接入历史、实时、资料主路径，并对不支持场景显式拒绝
- [x] 2.4 修正 `akshare` 相关搜索适配中的基金结果字段映射与 truthfulness 元数据，避免共享搜索结果语义失真

## 3. Auto 路由与执行入口对齐

- [x] 3.1 让 `plan_auto_backend_candidates()` 在排序前接入 truthfulness filtering，并改为读取 normalized `quote.*` 字段
- [x] 3.2 校准 auto candidate chain、`attempted_candidates`、`final_backend` 等 metadata，使其与真实候选规划和 failover 行为一致
- [x] 3.3 统一 facade 与 provider execution entry 的 contract failure 传播语义，确保 auto 与显式 backend 路径行为一致

## 4. 测试与编码整治

- [x] 4.1 为 `efinance quote.*` 标识翻译、`yfinance` A 股 ticker 翻译、单标的限制补充回归测试
- [x] 4.2 为 truthful candidate filtering、旧字段名禁用、candidate metadata 一致性补充契约测试
- [x] 4.3 修复本次触达关键 provider 与 contract 文件的 UTF-8 without BOM 编码和中文乱码问题，并完成必要验证