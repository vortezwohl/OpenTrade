<div align="center">
  <h1>OpenTrade</h1>
  <p><strong>终端里的市场数据，专为人与 Agent 设计。</strong></p>
  <p>用一套统一命令树完成证券搜索、行情查看、历史行情查询、数据导出，以及指标信息更丰富的 <code>observation</code> 结构化输出。</p>
  <p>
    <a href="https://www.python.org/"><img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-2F5D8C"></a>
    <a href="https://pypi.org/project/opentrade/"><img alt="PyPI 包" src="https://img.shields.io/badge/PyPI-opentrade-2563EB"></a>
    <a href="https://pypi.org/project/akshare/"><img alt="后端 akshare" src="https://img.shields.io/badge/Backend-akshare-1D4ED8"></a>
    <a href="https://pypi.org/project/efinance/"><img alt="后端 efinance" src="https://img.shields.io/badge/Backend-efinance-B45309"></a>
    <a href="https://pypi.org/project/yfinance/"><img alt="后端 yfinance" src="https://img.shields.io/badge/Backend-yfinance-15803D"></a>
  </p>
  <p>
    <a href="#installation">安装</a> ·
    <a href="#agent-skills">Agent Skills</a> ·
    <a href="#quick-start">快速开始</a> ·
    <a href="#command-tree">命令树</a> ·
    <a href="#output-and-defaults">输出与默认值</a> ·
    <a href="#indicator-support">技术指标支持</a> ·
    <a href="#more-docs">更多文档</a>
  </p>
</div>

<p align="center"><strong><a href="../README.md">English</a> | 简体中文 | <a href="README.zh-TW.md">繁體中文</a></strong></p>

## 安装

安装已发布到 PyPI 的 `opentrade`。安装后可使用 `opentrade` 和 `optr` 两个命令。

```bash
uv add -U opentrade
opentrade --help
```

```bash
pip install -U opentrade
opentrade --help
```

运行环境要求为 Python `3.10+`。

## Agent Skills

OpenTrade 还提供面向 Codex、Claude Code 和其他 Agent 的 skill，用于自动投研工作流。

当你希望 Agent 帮你安装这些 skill 时，只需要直接说：

> Please install skills from `https://github.com/vortezwohl/OpenTrade`, and place them in my global user skill directory.

这些 skill 主要用于自动化股票、基金、债券、期货和更广义市场场景下的投研分析。

## 快速开始

### 1. 搜索

```bash
opentrade search --query AAPL --market US_stock --result-count 5 --format json
```

当你只知道代码、关键字或公司名时，先搜索最稳妥。

### 2. 最新行情

```bash
opentrade quote price latest --symbols AAPL --format json
```

当你希望使用跨后端共享 symbol / ticker 流程时，优先使用共享 `quote` 命令。

### 3. 历史行情

```bash
opentrade quote price history --symbols AAPL --market us_stock --start-date 20250501 --end-date 20250601 --format json
```

需要 K 线、回补、指标或导出时，进入历史命令。

## 命令树

| 命令 | 角色 | 典型用途 |
|---|---|---|
| `search` | 关键字搜索 | 在还不知道精确标识时先找候选标的 |
| `resolve` | 标识解析 | 在需要时把 symbol 解析成 provider 专属 quote ID |
| `quote` | 跨资产共享查询 | 统一访问共享 latest、history、profile |
| `stock` | 股票专项流程 | 行情、快照、资金流、股东、资料 |
| `fund` | 基金专项流程 | 净值、估值、配置、经理、报告 |
| `bond` | 债券专项流程 | 行情、资料、成交、资金流 |
| `futures` | 期货专项流程 | 目录、历史、实时、成交 |
| `market` | 市场级查询 | 实时扫描与市场映射类查询 |
| `watch` | 刷新包装器 | 按固定间隔重复执行支持的命令 |

## 输出与默认值

当前共享命令的真实默认值：

- `--format table`
- `--indicator-level advanced`
- `--view observation`
- `--trace-window 32`
- 省略 `--backend` 时会解析为 `auto`

实用说明：

- `observation` 是默认的公共输出视图。
- 需要未包装结构时使用 `--view raw`。
- 对脚本和 Agent 来说，`json` 通常最合适。
- `full` 比 `advanced` 提供更丰富的指标上下文，但会消耗更多历史回补与计算成本。

## 技术指标支持

技术指标增强是 `opentrade` 的核心能力之一，兼容命令可以输出比原始行情更丰富的市场上下文。

| 等级 | 实际会得到什么 |
|---|---|
| `basic` | 核心趋势与动量指标，如 MA、EMA、MACD、RSI、KDJ、BOLL、ATR、OBV |
| `advanced` | 更广的趋势强度、通道与资金流指标，如 ADX、Donchian、Keltner、SuperTrend、MFI、PVT、CMF、VWAP、VR、PSY |
| `full` | 更完整的结构与市场上下文指标，如 Ichimoku、SAR、Mass Index、Pivot Points、Fibonacci Retracement、支撑阻力、Chaikin Oscillator、Chaikin Volatility、EMV |

代表性的指标家族包括：

- 均线与基础变换
- 趋势与通道指标
- 动量指标
- 成交量与资金流指标
- 波动率指标
- 价格结构指标
- 常见中文技术指标

完整列表和分组请见 [docs/indicator-coverage.md](../docs/indicator-coverage.md)。

## 后端说明

- shared 命令默认走 `auto`，当前一个 backend 失败时，`auto` 可能回退到其他 backend。
- shared `symbols` 不是东方财富 `quote_id`。
- `yfinance` 的分时历史窗口限制较严格，并且在本项目里更偏向单标的语义。
- 某条命令即使在 `auto` 下最终成功，也可能因为所选 backend 的历史回补失败而丢失 enriched observation 字段。

更详细的 backend 约束与排障说明请见 [docs/backend-notes.md](../docs/backend-notes.md)。

## 常见任务

### 搜索并查看

```bash
opentrade search --query NVDA --market US_stock
opentrade quote price latest --symbols NVDA
```

### 查看历史

```bash
opentrade stock price history --symbols AAPL --market us_stock --start-date 20250501 --end-date 20250601 --format json
```

### 循环刷新

```bash
opentrade watch --interval 5 --count 3 quote price latest --symbols AAPL --format json
```

### 导出数据

```bash
opentrade quote price history --symbols AAPL --market us_stock --start-date 20250501 --end-date 20250601 --format csv --output aapl-history.csv
```

## 更多文档

- [技术指标覆盖](../docs/indicator-coverage.md)
- [Observation 示例](../docs/observation-examples.md)
- [后端说明](../docs/backend-notes.md)
- [English README](../README.md)
- [繁體中文 README](README.zh-TW.md)

## 许可证

MIT License。
