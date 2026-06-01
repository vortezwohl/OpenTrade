## Why

80 条真实 API 回归测试揭示了 3 个影响用户体验和系统可靠性的代码缺陷：auto 后端兜底链在碰到 Yahoo 限流时断裂、Windows 控制台对特殊 Unicode 字符 GBK 编码崩溃、以及 --view raw 模式下错误地将字符串传给增强层导致 AttributeError。这三个问题都在实际调用中直接触发了命令失败，必须在下一版中修复。

## What Changes

- **修复 auto 兜底链断裂**: 将 is_failover_eligible_error 的策略从白名单改为黑名单，或者将 YFRateLimitError 显式加入可恢复异常列表。当 auto 模式依次尝试 akshare→yfinance→efinance 时，yfinance 的限流错误应被视作可恢复，不应阻断 efinance 的尝试。
- **修复 Windows GBK 编码崩溃**: 在输出写入环节（endering.py 或 executor.py 的输出处理）显式指定 encoding='utf-8' 并设置 errors='replace'，或判断当前运行环境并做编码兜底，避免 yfinance 返回的特殊 Unicode 字符导致控制台崩溃。
- **修复 --view raw 模式崩溃**: 在 executor.py 的 invoke 方法或 enrichment/service.py 的 enrich_market_data 函数中增加类型判断：当请求为 aw 视图模式时，跳过指标增强层，直接将原始结果传递给渲染层。

## Capabilities

### New Capabilities
- ix-auto-failover-yfinance-ratelimit: 修复 auto 后端兜底链在 yfinance 限流时无法继续尝试下一候选后端的问题
- ix-gbk-encoding-crash: 修复 Windows 控制台 GBK 编码器在遇到 yfinance 返回的特殊 Unicode 字符时崩溃的问题
- ix-raw-view-attribute-error: 修复 --view raw 模式下错误地将字符串传入增强层导致 AttributeError 的问题

### Modified Capabilities
<!-- 行为修正，不属于 spec 级需求变更 -->

## Impact

- **修改文件**:
  - efinance_cli/facade.py — is_failover_eligible_error 函数
  - efinance_cli/executor.py — invoke 方法的 raw 视图分支
  - efinance_cli/rendering.py — 输出编码处理
- **不涉及接口变更**: 所有修改均为内部行为修正，CLI 命令面、参数和返回结构不变
- **不新增依赖**
