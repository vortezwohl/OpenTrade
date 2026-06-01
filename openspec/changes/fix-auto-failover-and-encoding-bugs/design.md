## Context

80 条真实 API 回归测试在三个独立代码路径上触发了确定性的崩溃：

1. **auto 兜底链**: acade.py:is_failover_eligible_error 使用显式白名单判定异常是否可恢复，YFRateLimitError（继承自 Exception 而非 RuntimeError）未被列入，导致 auto 模式试到 yfinance 限流时直接抛出而不再尝试 efinance。
2. **GBK 编码**: executor.py:_emit 调用 click.echo() 输出，在 Windows 中文控制台默认使用 GBK 编码，当 yfinance 返回含特殊 Unicode（如 \ufffd）字符时触发 UnicodeEncodeError。
3. **raw 视图**: executor.py:invoke 在调用 enrich_market_data 前未检查 iew_mode，raw 模式下 _materialize_standard_result 返回的是非 DataFrame 的裸字典，传给增强层后导致 AttributeError: 'str' object has no attribute 'columns'。

三个 bug 均为独立代码路径，互不依赖，可在同一次变更中并行修复。

## Goals / Non-Goals

**Goals:**
- 修复 auto 模式下 yfinance 限流不应阻断后续候选后端的问题
- 修复 Windows GBK 控制台对特殊 Unicode 字符的编码崩溃
- 修复 --view raw 模式下错误地将非 DataFrame 数据传给增强层的问题
- 修复后通过相关回归测试，不引入新失败

**Non-Goals:**
- 不修改 CLI 命令面、参数签名或返回结构
- 不新增依赖
- 不改变 observation 视图的任何行为
- 不扩大 auto 候选链的范围或顺序

## Decisions

### 决策 1: is_failover_eligible_error — 从白名单改黑名单

**选择**: 将判定逻辑从"显式列出可恢复异常"改为"显式列出不可恢复异常（参数/类型错误）+ 默认可恢复"。

**理由**:
- 当前白名单只有 RuntimeError、OSError、KeyError 三类，未来任何新增的网络/外部依赖异常都会被遗漏
- 黑名单只需排除确定不应自动重试的异常：click.ClickException（用户参数错误）、ValueError/TypeError（编程错误）
- KeyError 保留在黑名单外（网络返回 JSON 结构不完整时属于可恢复错误）
- 替代方案（只加 YFRateLimitError 到白名单）：只是头痛医头，下次新 provider 的新异常类型还是会漏

**实现**:
`python
def is_failover_eligible_error(exc: Exception) -> bool:
    # 不可恢复：参数错误、编程错误
    if isinstance(exc, (click.ClickException, ValueError, TypeError)):
        return False
    # 其他所有异常均视为可恢复（网络、限流、超时等）
    return True
`

### 决策 2: GBK 编码 — 在 _emit 层强制 UTF-8

**选择**: 在 executor.py:_emit 中，对 click.echo 调用前将文本做 UTF-8 安全处理，或在 endering.py 的输出函数中统一添加 errors='replace'。

**理由**:
- 不能全局修改 sys.stdout 编码（可能影响其他输出）
- 在渲染层做编码兜底是局部修改，风险最小
- 替代方案（设置 PYTHONUTF8=1 环境变量）：不可靠，不同 Windows 版本行为不同

**实现**: 在 _emit 方法中，调用 click.echo 之前对 text 做一次安全编码：
`python
def _emit(self, request, result):
    text = self._render(request, result)
    # Windows GBK 编码兜底
    try:
        text.encode(sys.stdout.encoding or 'utf-8')
    except UnicodeEncodeError:
        # 无法在控制台编码的字符替换为 ?
        text = text.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(
            sys.stdout.encoding or 'utf-8', errors='replace'
        )
    ...
`

### 决策 3: raw 视图 — 在 invoke 层跳过增强

**选择**: 在 executor.py:invoke 中，当 equest.output.view_mode == 'raw' 时跳过 enrich_market_data 和 uild_observation_output 两个步骤。

**理由**:
- raw 视图的语义就是"原始数据不加工"，跳过增强和 observation 与其语义一致
- 在 invoke 层做判断而非在 enrich_market_data 内部判断，不污染增强层的职责边界
- 替代方案（在 enrich_market_data 内部增加类型判断）：会让增强层承担不必要的视图路由逻辑

## Risks / Trade-offs

- **[风险] 黑名单策略可能让真正不可恢复的错误（如内存不足 ImportError）被错误重试** → 缓解：ImportError 通常在 handler 初始化阶段就触发，不会到达 execute。且当前 auto 候选链只有 3 个后端，最多重试 3 次，不会造成显著开销。
- **[风险] GBK 替换可能丢失关键数据** → 缓解：替换只影响控制台显示，文件输出（--output）仍然使用用户指定的编码（默认 utf-8），不受影响。
- **[风险] raw 视图跳过增强后可能遗漏某些共享元数据** → 缓解：raw 视图的 _materialize_standard_result 已经独立构造了包含 contract_name、raw_payload、metadata 的完整字典，不需要增强层补充。
