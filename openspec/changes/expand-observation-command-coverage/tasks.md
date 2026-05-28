## 1. Multi-History 扩展

- [ ] 1.1 将 `fund get-quote-history-multi` 纳入 observation 命令覆盖范围。
- [ ] 1.2 复查并补齐 `dict[str, DataFrame] -> dict[str, ObservationPayload]` 的组装与渲染回归测试。
- [ ] 1.3 为 multi-history observation 补充 CLI 命令级测试，覆盖 table/json/csv/tsv 四种格式。

## 2. Single-Row 扩展

- [ ] 2.1 设计并实现 single-row observation assembler，支持增强后 `Series` 结果转换为 observation payload。
- [ ] 2.2 为 `stock get-quote-snapshot` 接入 observation，并验证 latest_quote、current_metrics、trace_points、recent_events 区块。
- [ ] 2.3 为 `stock get-base-info`、`bond get-base-info`、`common get-base-info` 接入 observation，并明确“弱 latest_quote”行为。
- [ ] 2.4 为 single-row observation 补充回归测试，覆盖 code 提取、历史回补和 latest_quote 缺省字段场景。

## 3. Realtime-List 扩展

- [ ] 3.1 设计并实现 realtime-list observation assembler，输出多 source observation 结果。
- [ ] 3.2 为 `stock get-realtime-quotes`、`bond get-realtime-quotes`、`futures get-realtime-quotes` 接入 observation。
- [ ] 3.3 为 realtime-list observation 增加默认限流与 grouped table 约束。
- [ ] 3.4 为 `fund get-realtime-increase-rate` 与 `common get-realtime-quotes-by-fs` 制定后续接入策略，并决定是否首批实现。

## 4. 多格式渲染与契约

- [ ] 4.1 明确 multi-source observation 在 table 下的 grouped boxed layout 规则。
- [ ] 4.2 明确 multi-source observation 在 json/csv/tsv 下的 long-form 契约与 source 标识规则。
- [ ] 4.3 为多 source observation 的 table/json/csv/tsv 输出补充回归测试。

## 5. 文档与上线策略

- [ ] 5.1 更新 CLI 文档，记录第二批 observation 支持命令和优先级。
- [ ] 5.2 记录 single-row 弱 latest_quote 和 realtime-list 默认限流约束。
- [ ] 5.3 记录第二批扩展的上线顺序、回退方式与未纳入命令范围的边界说明。
