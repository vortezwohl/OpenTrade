## 1. 命令目录与请求契约骨架

- [x] 1.1 新增后端无关命令目录模块，定义 `CommandDefinition`、命令键、CLI 路径、命令类别和帮助元数据。
- [x] 1.2 为共享命令引入显式请求 schema 模型，覆盖参数名、类型、默认值、取值域、必填约束和帮助文本。
- [x] 1.3 重构命令构建层，使共享命令的 Click 参数来自请求 schema，而不是第三方函数签名反射。
- [x] 1.4 为共享命令帮助页补充 capability 标识、支持 backend 列表和命令类别说明。

## 2. Provider 架构与能力注册

- [x] 2.1 新增 `BackendProvider`、`CapabilityHandler`、`BackendResolver` 和 `CapabilityRegistry` 基础接口与实现骨架。
- [x] 2.2 建立 backend 标识与运行时解析逻辑，支持显式 `--backend` 选择和命令支持矩阵校验。
- [x] 2.3 为 `efinance` 实现首批 provider 骨架，能够注册共享 capability handler 和扩展命令占位。
- [x] 2.4 为 `akshare` 实现首批 provider 骨架，能够注册共享 capability handler 和扩展命令占位。

## 3. 标准结果契约与标准化层

- [x] 3.1 新增按 capability 拆分的标准结果契约模型，至少覆盖搜索、历史行情、资料信息和实时行情。
- [x] 3.2 为首批共享 capability 实现标准化组件，区分核心字段、可选字段、原始字段和扩展字段。
- [x] 3.3 为标准化错误和关键字段缺失建立显式异常或错误结果路径。
- [x] 3.4 调整 raw 输出路径，确保用户仍可查看 provider 原始字段与扩展字段。

## 4. 统一执行骨架重构

- [x] 4.1 引入 `CommandFacade`，把命令请求路由到 backend provider 与 capability handler。
- [x] 4.2 重构执行层，使统一骨架包含请求校验、backend 解析、能力检查、handler 调用、标准化、增强、观察和渲染。
- [x] 4.3 调整 watch 模式，使其复用相同请求对象与 backend 解析路径，而不是旁路命令执行逻辑。
- [x] 4.4 为统一执行骨架补充失败路径测试，覆盖 schema 校验失败、backend 冲突和 capability 不支持场景。

## 5. Enrichment 与 Observation 解耦

- [x] 5.1 为历史回补引入标准补充接口，替换 enrichment 对 `efinance.*.get_quote_history` 的直接依赖。
- [x] 5.2 调整 observation，使其优先消费标准结果契约字段，而不是继续扩张 provider 原始字段别名。
- [ ] 5.3 为首批共享 capability 建立 observation 与 enrichment 的契约级测试。
- [ ] 5.4 明确并实现 provider 原始字段到标准字段的兼容下沉策略，避免兼容逻辑散落在 observation 中。

## 6. 首批共享能力迁移

- [x] 6.1 迁移 `instrument.search` 到新命令目录、请求 schema 和结果契约，并由 `efinance` provider 实现。
- [x] 6.2 为 `instrument.search` 补充 `akshare` handler，并验证双 backend 输出满足搜索结果契约。
- [x] 6.3 迁移 `equity.price.history` 到新骨架，并实现 `efinance` 与 `akshare` 双 backend handler。
- [ ] 6.4 迁移 `equity.profile` 到新骨架，并验证弱行情字段场景下的 observation / enrichment 行为。
- [ ] 6.5 迁移 `fund.nav.history` 到新骨架，并验证标准历史契约、渲染与观察输出。
- [ ] 6.6 在前述能力稳定后，再迁移 `equity.price.live`，并补充性能与默认限流验证。

## 7. Provider 扩展命令

- [ ] 7.1 设计 provider-specific 扩展命令目录结构与帮助展示规则。
- [ ] 7.2 为 `akshare` 增加一组示范性扩展命令组，并接入统一执行骨架。
- [ ] 7.3 为扩展命令补充运行时约束校验，确保错误 provider 下无法调用。
- [ ] 7.4 为未来 `yfinance` provider 预留扩展命令挂载点与可选依赖接入说明。

## 8. 测试、文档与清理

- [x] 8.1 新增 capability 合同测试，验证同一 capability 在 `efinance` 与 `akshare` 下满足相同核心契约。
- [ ] 8.2 新增 provider 层单元测试，覆盖 handler 路由、支持矩阵、标准化异常和扩展命令约束。
- [ ] 8.3 重写 CLI 回归测试，使其基于新命令目录与请求 schema，而不是旧函数驱动模型。
- [ ] 8.4 更新项目文档，说明新命令组织方式、`--backend` 语义、共享命令与扩展命令边界，以及 BREAKING 变更。
- [ ] 8.5 在首批共享能力全部稳定后，清理旧的 `efinance` 函数驱动注册路径和仅为旧模型服务的兼容代码。
