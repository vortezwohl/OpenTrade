## 1. Provider 请求边界治理

- [x] 1.1 梳理 `facade.py` 到 `providers.py` 的 execution limit 传递链路，建立统一的 request sanitization 入口，确保内部控制字段不会直接进入第三方 callback kwargs。
- [x] 1.2 仅为明确支持 provider-side 减载的命令保留显式 execution limit 消费路径，并补充 metadata 断言，区分“仅显示裁剪”和“provider-request 已减载”。
- [x] 1.3 为 `stock holders latest-count --limit`、`stock ipo latest --limit`、`fund catalog --limit`、`bond catalog --limit`、`futures catalog --limit` 补定向测试，验证不再出现 `unexpected keyword argument '__runtime_limit__'`。

## 2. Auto failover 错误分类

- [x] 2.1 在 facade / provider 边界引入可解释的错误分类，区分本地契约错误、provider 执行失败、provider 响应错误与远端限流/网络故障。
- [x] 2.2 将 `auto` 的是否继续切换逻辑改为基于分类后的错误语义，而不是直接依赖原始 `TypeError`、`ValueError`、`RuntimeError` 等异常类型。
- [x] 2.3 补充 `test_facade_unit.py` 与相关回归测试，覆盖“rate limit 继续 failover”“本地契约错误立即停止”“全部 provider failure 时聚合报错”三类场景。

## 3. Provider 兼容性护栏

- [x] 3.1 在 efinance 相关 adapter 中为 `stock leaderboard daily`、`stock holders latest-count` 等共享日期字段增加 `YYYYMMDD` 到 provider 真实格式的归一化，同时兼容已带连字符的日期输入。
- [x] 3.2 为 `fund profile`、`bond flow today` 等已证实的上游坏返回路径增加 guardrail，把第三方内部崩溃稳定归类为 provider failure，而不是用户输入错误。
- [x] 3.3 补充 provider handler 测试，验证显式 backend 会暴露稳定失败分类，`auto` 模式会在这些 guardrail 场景下继续记录并尝试后续 backend。

## 4. 回归脚本与报告语义校正

- [x] 4.1 更新真实回归脚本样本，修正共享命令参数样本与失败归类规则，使脚本能够区分本地 bug、provider failure 和上游不可用。
- [x] 4.2 运行最小真实回归子集，至少覆盖 `stock holders latest-count --limit`、`stock leaderboard daily`、`fund profile`、`bond flow today`、相关 auto 样本，并记录新的 trace / 分类行为。
- [x] 4.3 更新测试结论文档或回归结果归档，明确本次 change 修复了哪些本地边界问题、哪些失败仍归因于第三方 provider 或远端真实不可用。
