## Context

当前项目已有 7 个测试文件覆盖 CLI 命令树、路由、渲染、observation、重试和后端架构的核心路径。但上一轮深度分析揭示出六个关键盲区，这些盲区中的模块目前完全依赖间接覆盖或根本未覆盖。本设计专注于以最小代价、零业务代码变动的纯测试补充方案消除这些盲区。

### 当前测试分布

| 测试文件 | 覆盖范围 | 
|----------|---------|
| 	est_cli_full_regression.py | CLI 命令树构建、路由、watch 模式、auto-failover、必填参数校验 |
| 	est_multi_backend_scaffold.py | shared/single 命令分离、provider 注册、capability 契约、部分 handler |
| 	est_retry_regression.py | 网络重试签名保持、恢复、超限失败、异常注册表 |
| 	est_enrichment_smoke.py | 三级指标增强的 happy path |
| 	est_indicators_smoke.py | MACD、KDJ、Bollinger、OBV、Pivot Points 五个指标 |
| 	est_observation_smoke.py | 8 种 observation 构建场景 |
| 	est_rendering_and_metrics_regression.py | 4 种输出格式 + VWAP/BIAS 手工公式验证 |

### 待补充的模块

| 模块 | 当前测试状态 | 风险等级 |
|------|-------------|---------|
| contracts.py | 零直接测试 | 高 — 上游数据漂移时无法发现契约失效 |
| indicators/*.py (约 20 个未测) | ~30% 覆盖 | 中 — 数学公式错误只能在集成使用中发现 |
| enrichment/indicators.py | 仅 happy path | 中 — 边界输入可能导致崩溃 |
| equest_schema.py | 零直接测试 | 中 — schema→CLI 映射错误不可见 |
| ackends/resolver.py | 零直接测试 | 中 — 后端选择逻辑变更缺乏保障 |
| enrichment/service.py | 零直接测试 | 低 — 薄转发层 |
| providers.py (6 个未测 handler) | ~40% 覆盖 | 中 — handler 错误行为不可见 |
| acade.py | 隐式覆盖 | 中 — 缺乏直接的行为契约验证 |

## Goals / Non-Goals

**Goals:**
- 为上述 8 个模块建立直接、独立的单元测试
- 每个新增测试文件遵循项目现有风格（unittest + mock，中文注释，cli_regression_support.py 辅助函数）
- 不修改 efinance_cli/ 下的任何业务源代码

**Non-Goals:**
- 不引入真实网络调用的集成测试（需要稳定的测试数据源和网络环境，超出本次范围）
- 不追求 100% 行覆盖率（边界情况按优先级取舍）
- 不新增测试框架依赖（保持 unittest + pytest 运行器，不做迁移）
- 不修改现有测试文件（除非需要提取公共 fixture 到 conftest.py）

## Decisions

### 决策 1：测试文件拆分策略

**选择**：按模块 1:1 新增测试文件，而非扩展现有文件。

**理由**：
- 现有测试文件已按功能域清晰分割（CLI、后端、渲染等）
- 新增测试文件遵循相同命名约定（	est_<module>_<focus>.py）
- 避免现有文件膨胀，便于并行开发和问题定位
- 替代方案（合并到现有文件）：会使 	est_multi_backend_scaffold.py 和 	est_indicators_smoke.py 过大

### 决策 2：indicators 测试策略

**选择**：每个未测指标至少验证"输出类型正确 + 列名符合预期"，关键指标补充手工公式验证。

**理由**：
- 指标是纯函数，输入确定则输出确定
- 类型+列名检查能在极低成本下发现"接口漂移"和"返回值结构错误"
- 手工公式验证针对金融意义较高、风险较大的指标（ATR、RSI、ADX 等）
- 替代方案（每个指标全量公式验证）：工作量大但边际价值递减——数学公式本身的正确性应在上游验证

### 决策 3：provider handler 测试策略

**选择**：为每个未测 handler 建立独立的 mock 测试，验证输入→输出的数据流转，但不 mock 外部 API 细节。

**理由**：
- handler 的核心逻辑是"接收标准化的 request_data→调用上游 API→返回 StandardResult"
- mock 上游 API 返回值即可验证 handler 的数据转换逻辑
- 替代方案（真实 API 调用）：不可重复、受网络波动影响

### 决策 4：contracts.py 测试策略

**选择**：以参数化方式覆盖 uild_standard_result、
ormalize_contract_mapping、ensure_mapping_has_required_fields 的正常路径、缺失字段路径、类型不匹配路径。

**理由**：
- 契约层是数据标准化防线，每个路径都有独立价值
- 参数化减少样板代码

### 决策 5：补充 conftest.py 共享 fixture

**选择**：在 conftest.py 中新增以下 fixture：
- sample_ohlcv_frame() — 标准 OHLCV DataFrame
- sample_history_frame() — 带指标的完整历史 DataFrame
- sample_profile_data() — 标准 profile 数据字典

**理由**：
- 多个测试文件需要相同的样本数据
- 集中管理避免复制粘贴导致的漂移
- 已有 conftest.py 只做了 sys.path 配置，扩建自然

## Risks / Trade-offs

- **[风险] 新增测试可能因为 mock 不准确而变绿但实际行为错误** → 缓解：每个 mock 测试至少验证 1 个可观察的输出结构属性（列名、类型、键名），不完全依赖 mock 的返回值
- **[风险] indicators 测试中手工公式可能有误** → 缓解：手工公式来自公开的金融技术指标定义，对关键指标（ATR、RSI、ADX）额外用 pandas 计算做交叉验证
- **[风险] 测试运行时间显著增加** → 缓解：全部使用内存 DataFrame，不涉及 I/O 或网络，预计总增量 < 5 秒
